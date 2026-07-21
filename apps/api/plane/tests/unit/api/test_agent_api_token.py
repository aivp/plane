# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4
from types import SimpleNamespace

import pytest

from plane.api.views.agent import _get_agent_api_token, _task_response
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
    other_user = User.objects.create(
        email="agent-non-member@example.com",
        username="agent-non-member",
        first_name="Agent",
        last_name="Non Member",
    )
    token = APIToken.objects.create(
        user=other_user,
        is_service=False,
        token="plane_api_personal_non_member_token",
    )

    assert _get_agent_api_token(token.token, agent_workspace.slug) is None


def test_agent_api_response_uses_issue_id_without_task_id():
    task = SimpleNamespace(
        id="agent-task-id",
        status="running",
        base_branch="main",
        work_branch="ai/WEB-1-fix-login",
        issue=SimpleNamespace(
            id="issue-id",
            project_id="project-id",
            sequence_id=1,
            name="Fix login",
            description_html="<p>...</p>",
            assignees=SimpleNamespace(values_list=lambda *args, **kwargs: ["user-id"]),
            issue_comments=SimpleNamespace(all=lambda: []),
        ),
        repository=SimpleNamespace(
            id="repository-id",
            full_name="aidong/plane",
            html_url="https://github.com/aidong/plane",
        ),
    )

    response = _task_response(task)

    assert "task_id" not in response
    assert response["issue"]["id"] == "issue-id"
    assert response["issue"]["comments"] == []
    assert response["status"] == "running"
