# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status

from plane.db.models import User, WorkspaceMember, WorkspaceUserPreference


@pytest.mark.contract
class TestWorkspaceUserPreferenceAPI:
    @pytest.mark.django_db
    def test_patch_sidebar_preferences_updates_authenticated_user_only(self, session_client, workspace, create_user):
        unique_id = uuid4().hex[:8]
        other_user = User.objects.create(
            email=f"other-{unique_id}@plane.so",
            username=f"other_user_{unique_id}",
            first_name="Other",
            last_name="User",
        )
        WorkspaceMember.objects.create(workspace=workspace, member=other_user, role=20)

        current_user_preference = WorkspaceUserPreference.objects.create(
            workspace=workspace,
            user=create_user,
            key=WorkspaceUserPreference.UserPreferenceKeys.VIEWS,
            is_pinned=False,
            sort_order=65535,
        )
        other_user_preference = WorkspaceUserPreference.objects.create(
            workspace=workspace,
            user=other_user,
            key=WorkspaceUserPreference.UserPreferenceKeys.VIEWS,
            is_pinned=False,
            sort_order=75535,
        )

        url = reverse("workspace-user-preference", kwargs={"slug": workspace.slug})
        response = session_client.patch(
            url,
            [
                {
                    "key": WorkspaceUserPreference.UserPreferenceKeys.VIEWS,
                    "is_pinned": True,
                    "sort_order": 12345,
                }
            ],
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        current_user_preference.refresh_from_db()
        other_user_preference.refresh_from_db()

        assert current_user_preference.is_pinned is True
        assert current_user_preference.sort_order == 12345
        assert other_user_preference.is_pinned is False
        assert other_user_preference.sort_order == 75535
