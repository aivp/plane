# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace

import pytest
from django.core.cache import cache

from plane.db.models import Account, LarkSyncRun, LarkWorkspaceMemberExclusion, WorkspaceMember
from plane.integrations.lark.identity import sync_lark_user_identity
from plane.integrations.lark.sync import LarkContactSyncService, exclude_lark_workspace_member_from_sync
from plane.tests.factories import WorkspaceFactory, WorkspaceMemberFactory


def _lark_user(**overrides):
    payload = {
        "open_id": "ou_open_1",
        "union_id": "on_union_1",
        "user_id": "f1",
        "name": "Feishu User",
        "email": "feishu.user@example.com",
        "enterprise_email": "",
        "avatar": {"avatar_72": "https://example.com/avatar.png"},
        "status": {"is_activated": True},
    }
    payload.update(overrides)
    return payload


class FakeLarkClient:
    def __init__(self, users):
        self.users = users
        self.config = SimpleNamespace(
            client_id="test-client",
            offboarding_policy="deactivate_workspace_member",
        )
        self.department_user_calls = 0

    def list_contact_scopes(self):
        return {"scope": {"department_ids": ["0"], "user_ids": []}}

    def list_department_children(self, department_id, *, page_token=None):
        return {"items": [], "has_more": False}

    def list_department_users(self, department_id, *, page_token=None):
        self.department_user_calls += 1
        return {"items": self.users, "has_more": False}

    def get_user(self, user_id, *, user_id_type="open_id"):
        return next(user for user in self.users if user[user_id_type] == user_id)


@pytest.mark.unit
class TestLarkContactSync:
    @pytest.mark.django_db
    def test_manual_removal_records_exclusion_even_without_lark_account(self):
        cache.clear()
        workspace_member = WorkspaceMemberFactory(role=15, is_active=False)

        exclude_lark_workspace_member_from_sync(
            workspace_member,
            reason=LarkWorkspaceMemberExclusion.Reason.MANUAL_REMOVED,
        )

        assert LarkWorkspaceMemberExclusion.objects.filter(
            workspace=workspace_member.workspace,
            user=workspace_member.member,
            is_active=True,
        ).exists()

    @pytest.mark.django_db
    def test_list_contacts_caches_feishu_snapshot_and_keeps_workspace_status_fresh(self):
        cache.clear()
        workspace_member = WorkspaceMemberFactory(role=15)
        Account.objects.create(
            user=workspace_member.member,
            provider="lark",
            provider_account_id="on_union_1",
            access_token="",
        )
        client = FakeLarkClient([_lark_user()])
        service = LarkContactSyncService(workspace_member.workspace, client=client)

        first_contacts = service.list_contacts(limit=500)
        workspace_member.is_active = False
        workspace_member.save(update_fields=["is_active", "updated_at"])
        second_contacts = service.list_contacts(limit=500)

        assert client.department_user_calls == 1
        assert first_contacts[0]["is_imported"] is True
        assert second_contacts[0]["is_imported"] is False

    @pytest.mark.django_db
    def test_full_sync_does_not_reactivate_manually_excluded_workspace_member(self):
        cache.clear()
        workspace = WorkspaceFactory()
        result = sync_lark_user_identity(_lark_user(), source="contact_sync")
        workspace_member = WorkspaceMember.objects.create(
            workspace=workspace,
            member=result.user,
            role=15,
            is_active=False,
        )
        LarkWorkspaceMemberExclusion.objects.create(
            workspace=workspace,
            user=result.user,
            reason=LarkWorkspaceMemberExclusion.Reason.MANUAL_REMOVED,
        )
        sync_run = LarkSyncRun.objects.create(workspace=workspace)

        LarkContactSyncService(workspace, client=FakeLarkClient([_lark_user()])).sync_full(sync_run)

        workspace_member.refresh_from_db()
        sync_run.refresh_from_db()
        assert workspace_member.is_active is False
        assert sync_run.users_skipped == 1
        assert sync_run.members_added == 0

    @pytest.mark.django_db
    def test_manual_import_clears_member_exclusion_and_reactivates_member(self):
        cache.clear()
        workspace = WorkspaceFactory()
        result = sync_lark_user_identity(_lark_user(), source="contact_sync")
        workspace_member = WorkspaceMember.objects.create(
            workspace=workspace,
            member=result.user,
            role=15,
            is_active=False,
        )
        LarkWorkspaceMemberExclusion.objects.create(
            workspace=workspace,
            user=result.user,
            reason=LarkWorkspaceMemberExclusion.Reason.MANUAL_REMOVED,
        )

        stats = LarkContactSyncService(workspace, client=FakeLarkClient([_lark_user()])).import_users(["ou_open_1"])

        workspace_member.refresh_from_db()
        assert workspace_member.is_active is True
        assert stats["members_reactivated"] == 1
        assert not LarkWorkspaceMemberExclusion.objects.filter(
            workspace=workspace,
            user=result.user,
            is_active=True,
        ).exists()
