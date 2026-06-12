# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
from collections.abc import Iterable
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from plane.db.models import Account, LarkSyncRun, LarkWorkspaceMemberExclusion, Workspace, WorkspaceMember
from plane.integrations.lark.client import LarkAPIClient
from plane.integrations.lark.identity import normalize_lark_user, stable_lark_identity, sync_lark_user_identity


ALLOWED_WORKSPACE_ROLES = {5, 15, 20}
CONTACT_CACHE_TTL_SECONDS = 600


def sanitize_workspace_role(value: Any, default: int = 15) -> int:
    try:
        role = int(value)
    except (TypeError, ValueError):
        return default
    return role if role in ALLOWED_WORKSPACE_ROLES else default


def is_active_lark_user(lark_user: dict[str, Any]) -> bool:
    status = lark_user.get("status") or {}
    if not isinstance(status, dict):
        return True

    inactive_keys = ["is_frozen", "is_resigned", "is_exited", "is_deleted"]
    if any(bool(status.get(key)) for key in inactive_keys):
        return False
    if status.get("is_activated") is False:
        return False
    return True


def exclude_lark_workspace_member_from_sync(workspace_member: WorkspaceMember, *, reason: str) -> None:
    LarkWorkspaceMemberExclusion.objects.update_or_create(
        workspace_id=workspace_member.workspace_id,
        user_id=workspace_member.member_id,
        is_active=True,
        defaults={
            "reason": reason,
            "excluded_at": timezone.now(),
        },
    )


class LarkContactSyncService:
    def __init__(self, workspace: Workspace, *, role: int = 15, client: LarkAPIClient | None = None):
        self.workspace = workspace
        self.client = client or LarkAPIClient()
        self.role = sanitize_workspace_role(role)

    def _iter_department_tree(self, department_ids: Iterable[str]) -> Iterable[str]:
        seen = set()
        queue = [department_id for department_id in department_ids if department_id]
        if not queue:
            queue = ["0"]

        while queue:
            department_id = queue.pop(0)
            if department_id in seen:
                continue
            seen.add(department_id)
            yield department_id

            page_token = None
            while True:
                data = self.client.list_department_children(department_id, page_token=page_token)
                for item in data.get("items", []):
                    child_id = item.get("open_department_id") or item.get("department_id")
                    if child_id and child_id not in seen:
                        queue.append(str(child_id))
                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")

    def _iter_department_users(self, department_id: str) -> Iterable[dict[str, Any]]:
        page_token = None
        while True:
            data = self.client.list_department_users(department_id, page_token=page_token)
            for item in data.get("items", []):
                yield item
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

    def iter_visible_contacts(self) -> Iterable[dict[str, Any]]:
        scopes = self.client.list_contact_scopes()
        scopes = scopes.get("scope", scopes)
        emitted = set()

        for user_id in scopes.get("user_ids", []) or []:
            raw_user = self.client.get_user(str(user_id), user_id_type="open_id")
            normalized = normalize_lark_user(raw_user)
            identity = stable_lark_identity(normalized)
            if identity and identity not in emitted:
                emitted.add(identity)
                yield raw_user

        department_ids = scopes.get("department_ids", []) or []
        for department_id in self._iter_department_tree([str(item) for item in department_ids]):
            for raw_user in self._iter_department_users(department_id):
                normalized = normalize_lark_user(raw_user)
                identity = stable_lark_identity(normalized)
                if identity and identity not in emitted:
                    emitted.add(identity)
                    yield raw_user

    def _contacts_cache_key(self, *, search: str, limit: int) -> str:
        version_key = f"integrations:lark:contacts-version:{self.workspace_id}"
        version = cache.get(version_key) or "0"
        raw_key = f"{self.client.config.client_id}:{self.workspace_id}:{version}:{search}:{limit}"
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"integrations:lark:contacts:{digest}"

    @property
    def workspace_id(self):
        return self.workspace.id

    def invalidate_contacts_cache(self) -> None:
        cache.set(f"integrations:lark:contacts-version:{self.workspace_id}", timezone.now().timestamp(), timeout=None)

    def _list_external_contacts(self, *, search_value: str, limit: int) -> list[dict[str, Any]]:
        cache_key = self._contacts_cache_key(search=search_value, limit=limit)
        cached_contacts = cache.get(cache_key)
        if cached_contacts is not None:
            return cached_contacts

        contacts = []
        for raw_user in self.iter_visible_contacts():
            normalized = normalize_lark_user(raw_user)
            identity = stable_lark_identity(normalized)
            if not identity:
                continue

            haystack = " ".join(
                [
                    normalized.get("display_name", ""),
                    normalized.get("email", ""),
                    normalized.get("enterprise_email", ""),
                    normalized.get("employee_no", ""),
                    normalized.get("open_id", ""),
                    normalized.get("union_id", ""),
                ]
            ).lower()
            if search_value and search_value not in haystack:
                continue

            contacts.append(normalized)
            if len(contacts) >= limit:
                break

        cache.set(cache_key, contacts, timeout=CONTACT_CACHE_TTL_SECONDS)
        return contacts

    def _workspace_member_map(self, contacts: list[dict[str, Any]]) -> dict[str, WorkspaceMember]:
        identity_candidates: set[str] = set()
        candidates_by_contact = []
        for contact in contacts:
            candidates = []
            for value in [stable_lark_identity(contact), contact.get("union_id"), contact.get("open_id")]:
                if value and value not in candidates:
                    candidates.append(value)
                    identity_candidates.add(value)
            candidates_by_contact.append(candidates)

        accounts = {
            account.provider_account_id: account
            for account in Account.objects.filter(provider="lark", provider_account_id__in=identity_candidates)
        }
        user_ids = {account.user_id for account in accounts.values()}
        workspace_members = {
            workspace_member.member_id: workspace_member
            for workspace_member in WorkspaceMember.objects.filter(workspace=self.workspace, member_id__in=user_ids)
        }

        member_by_identity = {}
        for contact, candidates in zip(contacts, candidates_by_contact):
            for candidate in candidates:
                account = accounts.get(candidate)
                workspace_member = workspace_members.get(account.user_id) if account else None
                if workspace_member:
                    identity = stable_lark_identity(contact)
                    if identity:
                        member_by_identity[identity] = workspace_member
                    break
        return member_by_identity

    def list_contacts(self, *, search: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        search_value = (search or "").strip().lower()
        external_contacts = self._list_external_contacts(search_value=search_value, limit=limit)
        workspace_members = self._workspace_member_map(external_contacts)

        contacts = []
        for normalized in external_contacts:
            identity = stable_lark_identity(normalized)
            if not identity:
                continue

            workspace_member = workspace_members.get(identity)

            contacts.append(
                {
                    "open_id": normalized.get("open_id"),
                    "union_id": normalized.get("union_id"),
                    "user_id": normalized.get("user_id"),
                    "employee_no": normalized.get("employee_no"),
                    "name": normalized.get("display_name"),
                    "email": normalized.get("email"),
                    "avatar": normalized.get("avatar"),
                    "status": normalized.get("status"),
                    "is_active": is_active_lark_user(normalized),
                    "is_imported": bool(workspace_member and workspace_member.is_active),
                    "workspace_role": workspace_member.role if workspace_member else None,
                }
            )

        return contacts

    def _active_excluded_user_ids(self) -> set[str]:
        return {
            str(user_id)
            for user_id in LarkWorkspaceMemberExclusion.objects.filter(
                workspace=self.workspace,
                is_active=True,
            ).values_list("user_id", flat=True)
        }

    def _clear_member_exclusion(self, user_id) -> None:
        LarkWorkspaceMemberExclusion.objects.filter(
            workspace=self.workspace,
            user_id=user_id,
            is_active=True,
        ).update(is_active=False, updated_at=timezone.now())

    def _ensure_workspace_member(
        self,
        user_id,
        *,
        role: int,
        excluded_user_ids: set[str] | None = None,
    ) -> tuple[bool, bool, bool]:
        with transaction.atomic():
            workspace_member = WorkspaceMember.objects.select_for_update().filter(
                workspace=self.workspace,
                member_id=user_id,
            ).first()
            if workspace_member:
                if not workspace_member.is_active and excluded_user_ids and str(user_id) in excluded_user_ids:
                    return False, False, True

                was_inactive = not workspace_member.is_active
                workspace_member.is_active = True
                if was_inactive:
                    workspace_member.role = role
                workspace_member.save(update_fields=["is_active", "role", "updated_at"])
                return False, was_inactive, False

            if excluded_user_ids and str(user_id) in excluded_user_ids:
                return False, False, True

            WorkspaceMember.objects.create(workspace=self.workspace, member_id=user_id, role=role)
            return True, False, False

    def _deactivate_missing_members(self, seen_user_ids: set[str]) -> int:
        if self.client.config.offboarding_policy != "deactivate_workspace_member":
            return 0
        if not seen_user_ids:
            return 0

        queryset = WorkspaceMember.objects.filter(
            workspace=self.workspace,
            member__accounts__provider="lark",
            is_active=True,
        )
        queryset = queryset.exclude(member_id__in=seen_user_ids)
        return queryset.update(is_active=False, updated_at=timezone.now())

    def sync_full(self, sync_run: LarkSyncRun) -> LarkSyncRun:
        sync_run.status = LarkSyncRun.Status.RUNNING
        sync_run.started_at = timezone.now()
        sync_run.error = ""
        sync_run.save(update_fields=["status", "started_at", "error", "updated_at"])

        seen_user_ids = set()
        excluded_user_ids = self._active_excluded_user_ids()
        try:
            for raw_user in self.iter_visible_contacts():
                sync_run.users_seen += 1
                normalized = normalize_lark_user(raw_user)
                if not stable_lark_identity(normalized):
                    sync_run.users_skipped += 1
                    continue

                result = sync_lark_user_identity(raw_user, source="contact_sync")
                seen_user_ids.add(str(result.user.id))
                if result.created_user:
                    sync_run.users_created += 1
                else:
                    sync_run.users_updated += 1

                if not is_active_lark_user(normalized):
                    workspace_member = WorkspaceMember.objects.filter(
                        workspace=self.workspace,
                        member=result.user,
                        is_active=True,
                    ).first()
                    if workspace_member:
                        workspace_member.is_active = False
                        workspace_member.save(update_fields=["is_active", "updated_at"])
                        sync_run.members_deactivated += 1
                    continue

                created, reactivated, skipped = self._ensure_workspace_member(
                    result.user.id,
                    role=self.role,
                    excluded_user_ids=excluded_user_ids,
                )
                if skipped:
                    sync_run.users_skipped += 1
                    continue
                if created or reactivated:
                    sync_run.members_added += 1

            sync_run.members_deactivated += self._deactivate_missing_members(seen_user_ids)
            sync_run.status = LarkSyncRun.Status.SUCCEEDED
        except Exception as exc:
            sync_run.status = LarkSyncRun.Status.FAILED
            sync_run.error = str(exc)
            raise
        finally:
            sync_run.completed_at = timezone.now()
            sync_run.save(
                update_fields=[
                    "status",
                    "users_seen",
                    "users_created",
                    "users_updated",
                    "members_added",
                    "members_deactivated",
                    "users_skipped",
                    "error",
                    "completed_at",
                    "updated_at",
                ]
            )

        return sync_run

    def import_users(self, user_ids: list[str], *, user_id_type: str = "open_id", role: int | None = None) -> dict[str, int]:
        role = sanitize_workspace_role(role, default=self.role)
        stats = {
            "users_seen": 0,
            "users_created": 0,
            "users_updated": 0,
            "members_added": 0,
            "members_reactivated": 0,
            "users_skipped": 0,
        }

        for user_id in user_ids:
            stats["users_seen"] += 1
            raw_user = self.client.get_user(str(user_id), user_id_type=user_id_type)
            normalized = normalize_lark_user(raw_user)
            if not stable_lark_identity(normalized) or not is_active_lark_user(normalized):
                stats["users_skipped"] += 1
                continue

            result = sync_lark_user_identity(raw_user, source="manual_import")
            if result.created_user:
                stats["users_created"] += 1
            else:
                stats["users_updated"] += 1

            self._clear_member_exclusion(result.user.id)
            created, reactivated, _ = self._ensure_workspace_member(result.user.id, role=role)
            if created:
                stats["members_added"] += 1
            if reactivated:
                stats["members_reactivated"] += 1

        return stats
