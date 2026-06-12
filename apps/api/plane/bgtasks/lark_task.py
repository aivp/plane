# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from typing import Any

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from plane.db.models import Account, LarkEvent, LarkNotificationOutbox, LarkSyncRun, Workspace
from plane.integrations.lark.client import LarkAPIClient, get_lark_configuration
from plane.integrations.lark.sync import LarkContactSyncService


CONTACT_EVENT_PREFIXES = ("contact.user.", "contact.department.")


@shared_task
def lark_sync_workspace(sync_run_id, role=None):
    sync_run = LarkSyncRun.objects.select_related("workspace").get(pk=sync_run_id)
    service = LarkContactSyncService(
        workspace=sync_run.workspace,
        role=role or get_lark_configuration().default_workspace_role,
    )
    service.sync_full(sync_run)
    return str(sync_run.id)


def _schedule_default_workspace_sync() -> str | None:
    config = get_lark_configuration()
    if not (config.is_enabled and config.auto_sync_enabled and config.default_workspace_slug):
        return None

    workspace = Workspace.objects.filter(slug=config.default_workspace_slug).first()
    if not workspace:
        return None

    sync_run = LarkSyncRun.objects.create(
        workspace=workspace,
        sync_type=LarkSyncRun.SyncType.INCREMENTAL,
        status=LarkSyncRun.Status.PENDING,
    )
    lark_sync_workspace.delay(str(sync_run.id), config.default_workspace_role)
    return sync_run.job_id


@shared_task
def lark_process_events(limit=100):
    processed = 0
    event_ids = list(
        LarkEvent.objects.filter(status__in=[LarkEvent.Status.PENDING, LarkEvent.Status.FAILED])
        .filter(attempts__lt=5)
        .order_by("received_at")
        .values_list("id", flat=True)[:limit]
    )

    for event_id in event_ids:
        with transaction.atomic():
            event = LarkEvent.objects.select_for_update().get(pk=event_id)
            event.status = LarkEvent.Status.PROCESSING
            event.attempts += 1
            event.save(update_fields=["status", "attempts", "updated_at"])

        try:
            if event.event_type.startswith(CONTACT_EVENT_PREFIXES):
                _schedule_default_workspace_sync()
            event.status = LarkEvent.Status.PROCESSED
            event.processed_at = timezone.now()
            event.last_error = ""
            processed += 1
        except Exception as exc:
            event.status = LarkEvent.Status.FAILED
            event.last_error = str(exc)
        finally:
            event.save(update_fields=["status", "processed_at", "last_error", "updated_at"])

    return processed


def _lark_receive_id(account: Account | None) -> tuple[str, str]:
    metadata = (account.metadata or {}) if account else {}
    if metadata.get("union_id"):
        return str(metadata.get("union_id")), "union_id"
    if metadata.get("open_id"):
        return str(metadata.get("open_id")), "open_id"
    if account and account.provider_account_id:
        provider_account_id = str(account.provider_account_id)
        return provider_account_id, "open_id" if provider_account_id.startswith("ou_") else "union_id"
    return "", ""


def _card_div(content: str) -> dict:
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": content,
        },
    }


def _card_action(url: str, label: str) -> dict:
    return {
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": label,
                },
                "url": url,
                "type": "primary",
            }
        ],
    }


def _interactive_card(title: str, elements: list[dict]) -> dict:
    return {
        "config": {
            "wide_screen_mode": True,
        },
        "header": {
            "template": "blue",
            "title": {
                "tag": "plain_text",
                "content": title,
            },
        },
        "elements": elements or [_card_div(title)],
    }


def _structured_card_elements(card: dict[str, Any], url: str) -> list[dict]:
    elements = []
    summary = card.get("summary")
    if summary:
        elements.append(_card_div(f"**{summary}**"))

    details = card.get("details") if isinstance(card.get("details"), list) else []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        label = detail.get("label")
        value = detail.get("value")
        if not label or not value:
            continue
        elements.append(_card_div(f"**{label}**：{value}"))

    if url:
        elements.append(_card_action(str(url), str(card.get("action_label") or "在 Plane 中打开")))

    return elements


def _legacy_card_elements(payload: dict[str, Any], url: str) -> list[dict]:
    elements = []
    message = payload.get("message") or ""
    if message:
        elements.append(_card_div(str(message)))
    if url:
        elements.append(_card_action(str(url), "Open in Plane"))
    return elements


def _outbox_card(outbox: LarkNotificationOutbox) -> dict:
    payload = outbox.payload or {}
    url = payload.get("url") or ""
    card = payload.get("card")

    if isinstance(card, dict):
        title = str(card.get("title") or payload.get("title") or "Plane notification")
        elements = _structured_card_elements(card, str(url))
        if elements:
            return _interactive_card(title, elements)

    title = str(payload.get("title") or "Plane notification")
    return _interactive_card(title, _legacy_card_elements(payload, str(url)))


@shared_task
def lark_send_pending_notifications(limit=100):
    config = get_lark_configuration()
    if not (config.is_enabled and config.notifications_enabled):
        return 0

    client = LarkAPIClient(config)
    now = timezone.now()
    outbox_ids = list(
        LarkNotificationOutbox.objects.filter(status__in=[LarkNotificationOutbox.Status.PENDING, LarkNotificationOutbox.Status.FAILED])
        .filter(attempts__lt=5)
        .filter(next_retry_at__isnull=True)
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
    retry_ids = list(
        LarkNotificationOutbox.objects.filter(status__in=[LarkNotificationOutbox.Status.PENDING, LarkNotificationOutbox.Status.FAILED])
        .filter(attempts__lt=5, next_retry_at__lte=now)
        .order_by("next_retry_at")
        .values_list("id", flat=True)[: max(limit - len(outbox_ids), 0)]
    )

    sent = 0
    for outbox_id in outbox_ids + retry_ids:
        with transaction.atomic():
            outbox = LarkNotificationOutbox.objects.select_for_update().get(pk=outbox_id)
            outbox.status = LarkNotificationOutbox.Status.SENDING
            outbox.attempts += 1
            outbox.save(update_fields=["status", "attempts", "updated_at"])

        try:
            payload = outbox.payload or {}
            receive_id = payload.get("receive_id")
            receive_id_type = payload.get("receive_id_type")

            if not receive_id or not receive_id_type:
                account = Account.objects.filter(provider="lark", user=outbox.recipient_user).first()
                receive_id, receive_id_type = _lark_receive_id(account)

            if not receive_id or not receive_id_type:
                outbox.status = LarkNotificationOutbox.Status.SKIPPED
                outbox.last_error = "Receiver has no Feishu account binding"
            else:
                client.send_message(
                    receive_id=receive_id,
                    receive_id_type=receive_id_type,
                    msg_type="interactive",
                    content=_outbox_card(outbox),
                )
                outbox.status = LarkNotificationOutbox.Status.SENT
                outbox.sent_at = timezone.now()
                outbox.last_error = ""
                outbox.next_retry_at = None
                sent += 1
        except Exception as exc:
            outbox.last_error = str(exc)
            if outbox.attempts >= 5:
                outbox.status = LarkNotificationOutbox.Status.DEAD
            else:
                outbox.status = LarkNotificationOutbox.Status.FAILED
                outbox.next_retry_at = timezone.now() + timedelta(minutes=min(2**outbox.attempts, 60))
        finally:
            outbox.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "last_error",
                    "next_retry_at",
                    "updated_at",
                ]
            )

    return sent
