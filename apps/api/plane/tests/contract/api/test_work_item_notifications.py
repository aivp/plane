# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, User, WorkspaceMember


@pytest.fixture
def project(db, workspace, create_user):
    """Create a test project with the API token user as an admin."""
    project = Project.objects.create(
        name="MCP Notification Project",
        identifier=f"MCP{uuid4().hex[:4].upper()}",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


@pytest.fixture
def assignee(db, workspace, project):
    """Create a project member that can be assigned to work items."""
    unique_id = uuid4().hex[:8]
    user = User.objects.create(
        email=f"assignee-{unique_id}@plane.so",
        username=f"assignee_{unique_id}",
        first_name="Assign",
        last_name="Me",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(project=project, member=user, role=15, is_active=True)
    return user


@pytest.mark.contract
class TestWorkItemNotificationDispatch:
    """Contract tests for v1 work item activity notification dispatch."""

    def get_work_item_list_url(self, workspace_slug, project_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/"

    def get_work_item_detail_url(self, workspace_slug, project_id, work_item_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{work_item_id}/"

    @pytest.mark.django_db
    def test_create_work_item_dispatches_notification_activity(
        self, api_key_client, workspace, project, assignee
    ):
        url = self.get_work_item_list_url(workspace.slug, project.id)
        payload = {
            "name": "Created through MCP",
            "assignees": [str(assignee.id)],
        }

        with (
            mock.patch("plane.api.views.issue.issue_activity") as mocked_issue_activity,
            mock.patch("plane.api.views.issue.model_activity"),
        ):
            response = api_key_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED, f"Got {response.status_code}: {response.data!r}"
        mocked_issue_activity.delay.assert_called_once()
        assert mocked_issue_activity.delay.call_args.kwargs["type"] == "issue.activity.created"
        assert mocked_issue_activity.delay.call_args.kwargs["notification"] is True

    @pytest.mark.django_db
    def test_update_work_item_assignee_dispatches_notification_activity(
        self, api_key_client, workspace, project, create_user, assignee
    ):
        issue = Issue.objects.create(
            name="Existing MCP work item",
            project=project,
            created_by=create_user,
        )
        url = self.get_work_item_detail_url(workspace.slug, project.id, issue.id)
        payload = {"assignees": [str(assignee.id)]}

        with (
            mock.patch("plane.api.views.issue.issue_activity") as mocked_issue_activity,
            mock.patch("plane.api.views.issue.model_activity"),
        ):
            response = api_key_client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK, f"Got {response.status_code}: {response.data!r}"
        mocked_issue_activity.delay.assert_called_once()
        assert mocked_issue_activity.delay.call_args.kwargs["type"] == "issue.activity.updated"
        assert mocked_issue_activity.delay.call_args.kwargs["notification"] is True
