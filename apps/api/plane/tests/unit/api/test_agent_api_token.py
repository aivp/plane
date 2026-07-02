# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest

from plane.api.views.agent import _get_agent_api_token
from plane.db.models import APIToken, User, Workspace, WorkspaceMember


@pytest.fixture
def agent_workspace(create_user):
    slug = f"agent-workspace-{uuid4().hex[:8]}"
    workspace = Workspace.objects.create(name="Agent Workspace", owner=create_user, slug=slug)
    WorkspaceMember.objects.create(workspace=workspace, member=create_user, role=20)
    return workspace


@pytest.mark.django_db
def test_agent_api_allows_workspace_service_token(create_user, agent_workspace):
    token = APIToken.objects.create(
        user=create_user,
        workspace=agent_workspace,
        is_service=True,
        token="plane_api_service_token",
    )

    assert _get_agent_api_token(token.token, agent_workspace.slug) == token


@pytest.mark.django_db
def test_agent_api_allows_personal_token_for_workspace_member(create_user, agent_workspace):
    token = APIToken.objects.create(
        user=create_user,
        is_service=False,
        token="plane_api_personal_member_token",
    )

    assert _get_agent_api_token(token.token, agent_workspace.slug) == token


@pytest.mark.django_db
def test_agent_api_rejects_personal_token_for_non_member(create_user, agent_workspace):
    other_user = User.objects.create(email="agent-non-member@example.com", first_name="Agent", last_name="Non Member")
    token = APIToken.objects.create(
        user=other_user,
        is_service=False,
        token="plane_api_personal_non_member_token",
    )

    assert _get_agent_api_token(token.token, agent_workspace.slug) is None
