# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import re
from html import unescape
from typing import Any

from django.db import IntegrityError
from django.utils.html import strip_tags

from plane.db.models import Account, LarkNotificationOutbox, Notification
from plane.integrations.lark.client import get_lark_configuration


logger = logging.getLogger("plane.integrations.lark")

MENTION_COMPONENT_RE = re.compile(
    r'<mention-component\b[^>]*\blabel="([^"]*)"[^>]*>.*?</mention-component>',
    re.IGNORECASE | re.DOTALL,
)
WHITESPACE_RE = re.compile(r"\s+")
BLANK_VALUES = {"", "none", "null", "undefined"}

FIELD_LABELS = {
    "assignees": "负责人",
    "attachment": "附件",
    "archived_at": "归档状态",
    "blocked_by": "阻塞来源",
    "blocking": "阻塞关系",
    "comment": "评论",
    "cycles": "周期",
    "description": "描述",
    "duplicate": "重复任务",
    "estimate_time": "预估时间",
    "issue": "任务",
    "labels": "标签",
    "link": "链接",
    "modules": "模块",
    "name": "标题",
    "parent": "父任务",
    "priority": "优先级",
    "relates_to": "关联任务",
    "start_date": "开始日期",
    "state": "状态",
    "target_date": "截止日期",
}
PRIORITY_LABELS = {
    "urgent": "紧急",
    "high": "高",
    "medium": "中",
    "low": "低",
    "none": "无",
}
VERB_LABELS = {
    "created": "创建了",
    "deleted": "删除了",
    "removed": "移除了",
    "restored": "恢复了",
    "updated": "更新了",
}


def _notification_url(notification: Notification, public_base_url: str) -> str:
    if not public_base_url:
        return ""

    base_url = public_base_url.rstrip("/")
    data = notification.data if isinstance(notification.data, dict) else {}
    issue = data.get("issue") or {}
    project = notification.project

    if notification.entity_name == "issue" and project and notification.entity_identifier:
        return (
            f"{base_url}/{notification.workspace.slug}/projects/{project.id}/issues/"
            f"{notification.entity_identifier}"
        )

    if issue.get("id") and project:
        return f"{base_url}/{notification.workspace.slug}/projects/{project.id}/issues/{issue.get('id')}"

    return f"{base_url}/{notification.workspace.slug}"


def _notification_title(notification: Notification) -> str:
    if notification.title:
        return str(notification.title)
    if notification.message_stripped:
        return str(notification.message_stripped)
    data = notification.data if isinstance(notification.data, dict) else {}
    issue = data.get("issue") or {}
    if issue.get("name"):
        return str(issue.get("name"))
    return "Plane notification"


def _clean_value(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if text.lower() in BLANK_VALUES:
        return ""
    return text


def _plain_text(value: Any, limit: int = 160) -> str:
    text = _clean_value(value)
    if not text:
        return ""

    text = MENTION_COMPONENT_RE.sub(r"\1", text)
    text = strip_tags(text)
    text = unescape(text)
    text = WHITESPACE_RE.sub(" ", text).strip()

    if len(text) > limit:
        return f"{text[: limit - 3].rstrip()}..."
    return text


def _field_label(field: str) -> str:
    if field.startswith("estimate_"):
        return "预估"
    return FIELD_LABELS.get(field, field.replace("_", " "))


def _display_value(value: Any, *, field: str = "", limit: int = 120) -> str:
    text = _plain_text(value, limit=limit)
    if field == "priority":
        return PRIORITY_LABELS.get(text.lower(), text)
    return text


def _format_change(old_value: Any, new_value: Any, *, field: str = "", limit: int = 120) -> str:
    old_text = _display_value(old_value, field=field, limit=limit)
    new_text = _display_value(new_value, field=field, limit=limit)

    if old_text and new_text:
        return f"{old_text} -> {new_text}"
    if new_text:
        return f"设置为 {new_text}"
    if old_text:
        return f"移除 {old_text}"
    return ""


def _actor_name(notification: Notification) -> str:
    try:
        actor = notification.triggered_by
    except Exception:
        actor = None

    if not actor:
        return "有人"

    if getattr(actor, "is_bot", False) and getattr(actor, "first_name", ""):
        return str(actor.first_name)

    return (
        _plain_text(getattr(actor, "display_name", ""), limit=60)
        or _plain_text(getattr(actor, "full_name", ""), limit=60)
        or _plain_text(getattr(actor, "email", ""), limit=60)
        or "有人"
    )


def _is_mention_notification(notification: Notification) -> bool:
    sender = _clean_value(notification.sender)
    message = _plain_text(notification.message_stripped or notification.message, limit=160).lower()
    return sender.endswith(":mentioned") or "mentioned you" in message


def _issue_display(issue: dict[str, Any], notification: Notification) -> str:
    issue_name = _plain_text(issue.get("name") or _notification_title(notification), limit=120)
    identifier = _plain_text(issue.get("identifier"), limit=24)
    sequence_id = _plain_text(issue.get("sequence_id"), limit=24)
    issue_key = f"{identifier}-{sequence_id}" if identifier and sequence_id else ""

    if issue_key and issue_name:
        return f"{issue_key} {issue_name}"
    return issue_key or issue_name


def _project_display(notification: Notification) -> str:
    project = notification.project
    if not project:
        return ""
    return _plain_text(getattr(project, "name", ""), limit=80)


def _comment_content(activity: dict[str, Any]) -> str:
    return _plain_text(activity.get("issue_comment") or activity.get("new_value"), limit=180)


def _collection_action(field: str, old_value: Any, new_value: Any) -> tuple[str, str]:
    label = _field_label(field)
    old_text = _display_value(old_value, limit=100)
    new_text = _display_value(new_value, limit=100)
    value = new_text or old_text

    if new_text and not old_text:
        return f"添加了{label}", f"{label}：{value}"
    if old_text and not new_text:
        return f"移除了{label}", f"{label}：{value}"
    return f"更新了{label}", _format_change(old_text, new_text, limit=100)


def _activity_summary(notification: Notification, activity: dict[str, Any]) -> tuple[str, str]:
    if not activity:
        return "", ""

    field = _clean_value(activity.get("field"))
    verb = _clean_value(activity.get("verb")) or "updated"
    old_value = activity.get("old_value")
    new_value = activity.get("new_value")

    if _is_mention_notification(notification):
        location = "评论" if field == "comment" else "任务描述" if field == "description" else _field_label(field)
        content = _comment_content(activity)
        return "提及了你", f"{location}：{content}" if content else f"位置：{location}"

    if field in {"", "None"}:
        return "创建了任务并分配给你", ""
    if field == "issue" and verb == "deleted":
        return "删除了任务", ""
    if field == "state":
        return "更新了状态", _format_change(old_value, new_value, field=field, limit=80)
    if field == "name":
        return "更新了标题", _format_change(old_value, new_value, limit=100)
    if field == "description":
        content = _display_value(new_value, limit=180)
        return "更新了描述", f"描述：{content}" if content else "描述已更新"
    if field == "priority":
        return "更新了优先级", _format_change(old_value, new_value, field=field, limit=80)
    if field in {"start_date", "target_date"}:
        label = _field_label(field)
        new_text = _display_value(new_value, limit=60)
        old_text = _display_value(old_value, limit=60)
        if new_text:
            return f"设置了{label}", f"{label}：{new_text}"
        return f"移除了{label}", f"{label}：{old_text}" if old_text else ""
    if field in {"assignees", "labels", "parent", "cycles", "modules", "link", "attachment"}:
        return _collection_action(field, old_value, new_value)
    if field == "comment":
        content = _comment_content(activity)
        if verb == "deleted":
            return "删除了评论", ""
        action = "更新了评论" if verb == "updated" else "发表了评论"
        return action, f"评论：{content}" if content else ""
    if field == "archived_at":
        if _clean_value(new_value).lower() == "restore" or verb == "restored":
            return "恢复了任务", ""
        return "归档了任务", ""

    label = _field_label(field)
    action = f"{VERB_LABELS.get(verb, '更新了')}{label}"
    return action, _format_change(old_value, new_value, field=field, limit=100)


def _notification_card(notification: Notification) -> dict[str, Any]:
    data = notification.data if isinstance(notification.data, dict) else {}
    issue = data.get("issue") if isinstance(data.get("issue"), dict) else {}
    activity = data.get("issue_activity") if isinstance(data.get("issue_activity"), dict) else {}
    actor = _actor_name(notification)
    action, change = _activity_summary(notification, activity)

    details = []
    task = _issue_display(issue, notification)
    project = _project_display(notification)
    state = _display_value(issue.get("state_name"), limit=80)

    if task:
        details.append({"label": "任务", "value": task})
    if project:
        details.append({"label": "项目", "value": project})
    if actor:
        details.append({"label": "触发人", "value": actor})
    if change:
        details.append({"label": "变化", "value": change})
    if state:
        details.append({"label": "当前状态", "value": state})

    if not details:
        fallback = _plain_text(notification.message_stripped or _notification_title(notification), limit=180)
        if fallback:
            details.append({"label": "内容", "value": fallback})

    return {
        "title": "Plane 任务通知",
        "summary": f"{actor} {action}" if action else _notification_title(notification),
        "details": details,
        "action_label": "在 Plane 中打开",
    }


def _recipient_from_account(account: Account | None) -> tuple[str, str]:
    metadata: dict[str, Any] = (account.metadata or {}) if account else {}
    if metadata.get("union_id"):
        return str(metadata.get("union_id")), "union_id"
    if metadata.get("open_id"):
        return str(metadata.get("open_id")), "open_id"
    if account and account.provider_account_id:
        provider_account_id = str(account.provider_account_id)
        return provider_account_id, "open_id" if provider_account_id.startswith("ou_") else "union_id"
    return "", ""


def enqueue_lark_notifications(notifications: list[Notification]) -> None:
    if not notifications:
        return

    try:
        config = get_lark_configuration()
        if not (config.is_enabled and config.notifications_enabled):
            return

        outbox_items = []
        for notification in notifications:
            account = Account.objects.filter(provider="lark", user=notification.receiver).first()
            receive_id, receive_id_type = _recipient_from_account(account)
            status = LarkNotificationOutbox.Status.PENDING if receive_id else LarkNotificationOutbox.Status.SKIPPED
            last_error = "" if receive_id else "Receiver has no Feishu account binding"

            outbox_items.append(
                LarkNotificationOutbox(
                    workspace=notification.workspace,
                    notification=notification,
                    recipient_user=notification.receiver,
                    event_key=f"notification:{notification.id}:lark",
                    message_type="issue_notification",
                    status=status,
                    last_error=last_error,
                    payload={
                        "notification_id": str(notification.id),
                        "workspace_id": str(notification.workspace_id),
                        "workspace_slug": notification.workspace.slug,
                        "project_id": str(notification.project_id) if notification.project_id else None,
                        "entity_name": notification.entity_name,
                        "entity_identifier": str(notification.entity_identifier)
                        if notification.entity_identifier
                        else None,
                        "title": _notification_title(notification),
                        "message": str(notification.message_stripped or ""),
                        "url": _notification_url(notification, config.public_base_url),
                        "card": _notification_card(notification),
                        "receive_id": receive_id,
                        "receive_id_type": receive_id_type,
                    },
                )
            )

        LarkNotificationOutbox.objects.bulk_create(outbox_items, batch_size=100, ignore_conflicts=True)
    except IntegrityError:
        logger.exception("Failed to enqueue Feishu notification outbox items")
    except Exception:
        logger.exception("Unexpected Feishu notification enqueue failure")
