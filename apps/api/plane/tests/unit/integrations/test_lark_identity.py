# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Account, User
from plane.integrations.lark.identity import is_placeholder_email, stable_lark_identity, sync_lark_user_identity
from plane.tests.factories import UserFactory


def _lark_user(**overrides):
    payload = {
        "open_id": "ou_open_1",
        "union_id": "on_union_1",
        "user_id": "f1",
        "name": "Feishu User",
        "email": "",
        "enterprise_email": "",
        "avatar": {"avatar_72": "https://example.com/avatar.png"},
        "status": {"is_activated": True},
    }
    payload.update(overrides)
    return payload


@pytest.mark.unit
class TestLarkIdentity:
    def test_stable_identity_prefers_union_id(self):
        assert stable_lark_identity({"open_id": "ou_open_1", "union_id": "on_union_1"}) == "on_union_1"

    @pytest.mark.django_db
    def test_sync_without_email_creates_placeholder_user(self):
        result = sync_lark_user_identity(_lark_user(), source="contact_sync")

        assert result.created_user is True
        assert result.account.provider == "lark"
        assert result.account.provider_account_id == "on_union_1"
        assert is_placeholder_email(result.user.email)
        assert result.user.display_name == "Feishu User"

    @pytest.mark.django_db
    def test_sync_updates_placeholder_email_when_real_email_appears(self):
        first_result = sync_lark_user_identity(_lark_user(), source="contact_sync")

        second_result = sync_lark_user_identity(
            _lark_user(email="real.user@example.com"),
            source="oauth",
            token_data={"access_token": "user-token"},
        )

        assert second_result.user.id == first_result.user.id
        assert second_result.user.email == "real.user@example.com"
        assert second_result.user.is_email_verified is True
        assert second_result.account.access_token == "user-token"
        assert User.objects.count() == 1
        assert Account.objects.count() == 1

    @pytest.mark.django_db
    def test_sync_merges_existing_real_email_without_using_email_as_identity(self):
        existing_user = UserFactory(email="real.user@example.com")

        result = sync_lark_user_identity(_lark_user(email="real.user@example.com"), source="oauth")

        assert result.user.id == existing_user.id
        assert result.created_user is False
        assert result.account.provider_account_id == "on_union_1"
        assert result.account.metadata["open_id"] == "ou_open_1"

    @pytest.mark.django_db
    def test_sync_can_disallow_new_user_creation(self):
        with pytest.raises(ValueError, match="existing Plane user"):
            sync_lark_user_identity(_lark_user(), source="oauth", allow_create_user=False)

        assert User.objects.count() == 0
        assert Account.objects.count() == 0

    @pytest.mark.django_db
    def test_sync_upgrades_open_id_account_to_union_id(self):
        user = UserFactory(email="legacy@example.com")
        account = Account.objects.create(
            user=user,
            provider="lark",
            provider_account_id="ou_open_1",
            access_token="",
        )

        result = sync_lark_user_identity(_lark_user(email="legacy@example.com"), source="contact_sync")

        account.refresh_from_db()
        assert result.account.id == account.id
        assert account.provider_account_id == "on_union_1"
