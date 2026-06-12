# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .base import BaseModel


def generate_lark_job_id():
    return uuid.uuid4().hex


class LarkEvent(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=255, db_index=True)
    tenant_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lark Event"
        verbose_name_plural = "Lark Events"
        db_table = "lark_events"
        ordering = ("-received_at",)
        indexes = [
            models.Index(fields=["status", "event_type"]),
            models.Index(fields=["tenant_key", "received_at"]),
        ]


class LarkSyncRun(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    class SyncType(models.TextChoices):
        FULL = "full", "Full"
        INCREMENTAL = "incremental", "Incremental"
        IMPORT = "import", "Import"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="lark_sync_runs")
    job_id = models.CharField(max_length=64, unique=True, default=generate_lark_job_id)
    sync_type = models.CharField(max_length=32, choices=SyncType.choices, default=SyncType.FULL)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    users_seen = models.PositiveIntegerField(default=0)
    users_created = models.PositiveIntegerField(default=0)
    users_updated = models.PositiveIntegerField(default=0)
    members_added = models.PositiveIntegerField(default=0)
    members_deactivated = models.PositiveIntegerField(default=0)
    users_skipped = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Lark Sync Run"
        verbose_name_plural = "Lark Sync Runs"
        db_table = "lark_sync_runs"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["sync_type", "created_at"]),
        ]


class LarkWorkspaceMemberExclusion(BaseModel):
    class Reason(models.TextChoices):
        MANUAL_REMOVED = "manual_removed", "Manual removed"
        MEMBER_LEFT = "member_left", "Member left"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="lark_member_exclusions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lark_workspace_member_exclusions",
    )
    reason = models.CharField(max_length=32, choices=Reason.choices, default=Reason.MANUAL_REMOVED)
    is_active = models.BooleanField(default=True, db_index=True)
    excluded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Lark Workspace Member Exclusion"
        verbose_name_plural = "Lark Workspace Member Exclusions"
        db_table = "lark_workspace_member_exclusions"
        ordering = ("-excluded_at",)
        indexes = [
            models.Index(fields=["workspace", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="lark_member_exclusion_unique_active_workspace_user",
            )
        ]


class LarkNotificationOutbox(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        DEAD = "dead", "Dead"
        SKIPPED = "skipped", "Skipped"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="lark_notification_outbox")
    notification = models.ForeignKey(
        "db.Notification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lark_outbox_items",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lark_notification_outbox",
    )
    event_key = models.CharField(max_length=255, unique=True, db_index=True)
    message_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lark Notification Outbox"
        verbose_name_plural = "Lark Notification Outbox"
        db_table = "lark_notification_outbox"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["workspace", "recipient_user"]),
        ]
