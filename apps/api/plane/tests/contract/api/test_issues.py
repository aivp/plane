# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueAssignee, Project, ProjectMember, State


@pytest.fixture
def project(db, workspace, create_user):
    """Create a test project with the requesting user as an active member."""
    project = Project.objects.create(
        name="Test Project",
        identifier="TP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        role=20,  # Admin
        is_active=True,
    )
    return project


@pytest.fixture
def state(db, workspace, project):
    return State.objects.create(
        name="Todo",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )


@pytest.fixture
def issue(db, workspace, project, state, create_user):
    return Issue.objects.create(
        name="Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=create_user,
    )


@pytest.mark.contract
class TestIssueListOrderByInjection:
    """Regression tests for GHSA-p885-6jpg-cr2p on the work-item list
    endpoint: GET /api/v1/workspaces/{slug}/projects/{project_id}/issues/.

    The raw ``order_by`` query parameter fell through the endpoint's hardcoded
    branch logic to ``issue_queryset.order_by(order_by_param)``, letting an
    attacker order by sensitive related columns (blind oracle) or crash the
    endpoint with an unknown field (HTTP 500). The fix sanitizes the parameter
    against ISSUE_ORDER_BY_ALLOWLIST before the branch logic runs.
    """

    def get_url(self, workspace_slug, project_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

    @pytest.mark.django_db
    def test_invalid_order_by_does_not_500(self, api_key_client, workspace, project, issue):
        """Unknown field used to raise FieldError → HTTP 500; now sanitized to
        the safe default and returns 200 (DoS half of the advisory)."""
        url = self.get_url(workspace.slug, project.id)
        response = api_key_client.get(url, {"order_by": "not_a_field"})

        assert response.status_code == status.HTTP_200_OK, f"Got {response.status_code}: {response.data!r}"

    @pytest.mark.django_db
    def test_relational_order_by_injection_does_not_500(self, api_key_client, workspace, project, issue):
        """Ordering by a related-table column (``created_by__password``) used to
        reach ``.order_by()`` raw, forming a blind ordering oracle. It is now
        neutralized to the safe default. (Deterministic neutralization is
        asserted in tests/unit/utils/test_order_by_sanitize.py.)"""
        url = self.get_url(workspace.slug, project.id)
        response = api_key_client.get(url, {"order_by": "created_by__password"})

        assert response.status_code == status.HTTP_200_OK, f"Got {response.status_code}: {response.data!r}"

    @pytest.mark.django_db
    def test_legitimate_order_by_still_works(self, api_key_client, workspace, project, issue):
        """A valid, allowlisted ordering value continues to return 200 —
        the sanitizer must not break legitimate ordering."""
        url = self.get_url(workspace.slug, project.id)

        for value in ["-created_at", "priority", "state__group", "sequence_id"]:
            response = api_key_client.get(url, {"order_by": value})
            assert response.status_code == status.HTTP_200_OK, (
                f"order_by={value!r} got {response.status_code}: {response.data!r}"
            )


@pytest.mark.contract
class TestIssueListPQL:
    """Contract coverage for the PQL query used by Plane MCP clients."""

    def get_url(self, workspace_slug, project_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/"

    @pytest.mark.django_db
    def test_filters_current_users_open_work_items(
        self,
        api_key_client,
        workspace,
        project,
        state,
        issue,
        create_user,
    ):
        IssueAssignee.objects.create(issue=issue, assignee=create_user, project=project)
        closed_state = State.objects.create(
            name="Done",
            project=project,
            workspace=workspace,
            group="completed",
        )
        closed_issue = Issue.objects.create(
            name="Closed assigned issue",
            workspace=workspace,
            project=project,
            state=closed_state,
            created_by=create_user,
        )
        IssueAssignee.objects.create(issue=closed_issue, assignee=create_user, project=project)
        Issue.objects.create(
            name="Open unassigned issue",
            workspace=workspace,
            project=project,
            state=state,
            created_by=create_user,
        )

        response = api_key_client.get(
            self.get_url(workspace.slug, project.id),
            {"pql": "assignee = currentUser() AND stateGroup IN openStates()"},
        )

        assert response.status_code == status.HTTP_200_OK, f"Got {response.status_code}: {response.data!r}"
        assert {str(item["id"]) for item in response.data["results"]} == {str(issue.id)}

    @pytest.mark.django_db
    def test_rejects_non_allowlisted_field(self, api_key_client, workspace, project):
        response = api_key_client.get(
            self.get_url(workspace.slug, project.id),
            {"pql": 'created_by__password = "secret"'},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported PQL field" in response.data["pql"]
        assert response.data["failed_pql"] == 'created_by__password = "secret"'

    @pytest.mark.django_db
    def test_rejects_more_than_five_conditions(self, api_key_client, workspace, project):
        response = api_key_client.get(
            self.get_url(workspace.slug, project.id),
            {
                "pql": (
                    'priority = "high" OR priority = "urgent" OR priority = "medium" '
                    'OR priority = "low" OR priority = "none" OR title ~ "overflow"'
                )
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "at most 5 conditions" in response.data["pql"]


@pytest.mark.contract
class TestWorkItemAttachmentUpload:
    @pytest.mark.django_db
    def test_html_attachment_can_start_upload(self, api_key_client, workspace, project, issue):
        url = (
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/"
            f"work-items/{issue.id}/attachments/"
        )

        with patch(
            "plane.api.views.issue.S3Storage.generate_presigned_post",
            return_value={"url": "https://storage.example.com", "fields": {}},
        ):
            response = api_key_client.post(
                url,
                {"name": "report.htm", "type": "text/html", "size": 1024},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["attachment"]["attributes"]["type"] == "text/html"
