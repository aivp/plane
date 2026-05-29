# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from typing import Any

from django.db import IntegrityError

from plane.db.models import Account, LarkNotificationOutbox, Notification
from plane.integrations.lark.client import get_lark_configuration


logger = logging.getLogger("plane.integrations.lark")


def _notification_url(notification: Notification, public_base_url: str) -> str:
    if not public_base_url:
        return ""

    base_url = public_base_url.rstrip("/")
    data = notification.data or {}
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
    data = notification.data or {}
    issue = data.get("issue") or {}
    if issue.get("name"):
        return str(issue.get("name"))
    return "Plane notification"


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
