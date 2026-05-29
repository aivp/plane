# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone

from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.bgtasks.lark_task import lark_sync_workspace
from plane.db.models import LarkSyncRun, Workspace, WorkspaceMember
from plane.integrations.lark.client import LarkAPIError, get_lark_configuration
from plane.integrations.lark.sync import LarkContactSyncService, sanitize_workspace_role


def _get_workspace(slug: str) -> Workspace:
    return Workspace.objects.get(slug=slug)


def _sync_run_payload(sync_run: LarkSyncRun) -> dict:
    return {
        "id": str(sync_run.id),
        "job_id": sync_run.job_id,
        "sync_type": sync_run.sync_type,
        "status": sync_run.status,
        "users_seen": sync_run.users_seen,
        "users_created": sync_run.users_created,
        "users_updated": sync_run.users_updated,
        "members_added": sync_run.members_added,
        "members_deactivated": sync_run.members_deactivated,
        "users_skipped": sync_run.users_skipped,
        "error": sync_run.error,
        "started_at": sync_run.started_at,
        "completed_at": sync_run.completed_at,
        "created_at": sync_run.created_at,
    }


class WorkspaceLarkContactsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        config = get_lark_configuration()
        if not (config.is_enabled and config.is_configured):
            return Response({"error": "Feishu integration is not configured"}, status=status.HTTP_400_BAD_REQUEST)

        limit = request.GET.get("limit", 500)
        try:
            limit = min(max(int(limit), 1), 1000)
        except (TypeError, ValueError):
            limit = 500

        try:
            contacts = LarkContactSyncService(_get_workspace(slug), role=config.default_workspace_role).list_contacts(
                search=request.GET.get("search"),
                limit=limit,
            )
            return Response({"contacts": contacts}, status=status.HTTP_200_OK)
        except LarkAPIError as exc:
            return Response({"error": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)


class WorkspaceLarkSyncEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        config = get_lark_configuration()
        if not (config.is_enabled and config.is_configured):
            return Response({"error": "Feishu integration is not configured"}, status=status.HTTP_400_BAD_REQUEST)

        role = sanitize_workspace_role(request.data.get("role", config.default_workspace_role))
        requester_role = WorkspaceMember.objects.get(workspace__slug=slug, member=request.user, is_active=True).role
        if role > requester_role:
            return Response({"error": "Cannot assign a role higher than your own"}, status=status.HTTP_400_BAD_REQUEST)

        sync_run = LarkSyncRun.objects.create(
            workspace=_get_workspace(slug),
            sync_type=LarkSyncRun.SyncType.FULL,
            status=LarkSyncRun.Status.PENDING,
        )
        lark_sync_workspace.delay(str(sync_run.id), role)
        return Response(_sync_run_payload(sync_run), status=status.HTTP_202_ACCEPTED)


class WorkspaceLarkSyncRunsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        sync_runs = LarkSyncRun.objects.filter(workspace__slug=slug).order_by("-created_at")[:20]
        return Response({"sync_runs": [_sync_run_payload(sync_run) for sync_run in sync_runs]}, status=status.HTTP_200_OK)


class WorkspaceLarkImportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        config = get_lark_configuration()
        if not (config.is_enabled and config.is_configured):
            return Response({"error": "Feishu integration is not configured"}, status=status.HTTP_400_BAD_REQUEST)

        user_ids = request.data.get("user_ids") or []
        user_id_type = request.data.get("user_id_type", "open_id")
        if user_id_type not in ["open_id", "union_id", "user_id"]:
            return Response({"error": "user_id_type is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(user_ids, list) or not user_ids:
            return Response({"error": "user_ids must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST)
        if len(user_ids) > 100:
            return Response({"error": "Cannot import more than 100 users at once"}, status=status.HTTP_400_BAD_REQUEST)

        role = sanitize_workspace_role(request.data.get("role", config.default_workspace_role))
        requester_role = WorkspaceMember.objects.get(workspace__slug=slug, member=request.user, is_active=True).role
        if role > requester_role:
            return Response({"error": "Cannot assign a role higher than your own"}, status=status.HTTP_400_BAD_REQUEST)

        sync_run = LarkSyncRun.objects.create(
            workspace=_get_workspace(slug),
            sync_type=LarkSyncRun.SyncType.IMPORT,
            status=LarkSyncRun.Status.RUNNING,
            started_at=timezone.now(),
        )
        try:
            stats = LarkContactSyncService(_get_workspace(slug), role=role).import_users(
                [str(item) for item in user_ids],
                user_id_type=user_id_type,
                role=role,
            )
            sync_run.users_seen = stats["users_seen"]
            sync_run.users_created = stats["users_created"]
            sync_run.users_updated = stats["users_updated"]
            sync_run.members_added = stats["members_added"] + stats["members_reactivated"]
            sync_run.users_skipped = stats["users_skipped"]
            sync_run.status = LarkSyncRun.Status.SUCCEEDED
            sync_run.completed_at = timezone.now()
            sync_run.save(
                update_fields=[
                    "users_seen",
                    "users_created",
                    "users_updated",
                    "members_added",
                    "users_skipped",
                    "status",
                    "completed_at",
                    "updated_at",
                ]
            )
            return Response({"sync_run": _sync_run_payload(sync_run), "stats": stats}, status=status.HTTP_200_OK)
        except LarkAPIError as exc:
            sync_run.status = LarkSyncRun.Status.FAILED
            sync_run.error = str(exc)
            sync_run.completed_at = timezone.now()
            sync_run.save(update_fields=["status", "error", "completed_at", "updated_at"])
            return Response({"error": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            sync_run.status = LarkSyncRun.Status.FAILED
            sync_run.error = str(exc)
            sync_run.completed_at = timezone.now()
            sync_run.save(update_fields=["status", "error", "completed_at", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
