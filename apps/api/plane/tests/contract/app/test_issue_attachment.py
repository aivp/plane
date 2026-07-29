# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import FileAsset, Issue, Project, ProjectMember, User, Workspace, WorkspaceMember


@pytest.fixture
def project(workspace, create_user):
    project = Project.objects.create(name="Attachment Project", identifier="ATT", workspace=workspace)
    ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


@pytest.fixture
def issue(project):
    return Issue.objects.create(name="Attachment issue", project=project)


@pytest.fixture
def uploaded_attachment(workspace, project, issue, create_user):
    return FileAsset.objects.create(
        attributes={"name": "preview.png", "type": "image/png", "size": 1024},
        asset=f"{workspace.id}/preview.png",
        size=1024,
        workspace=workspace,
        project=project,
        issue=issue,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        is_uploaded=True,
    )


@pytest.fixture
def uploaded_html_attachment(workspace, project, issue, create_user):
    return FileAsset.objects.create(
        attributes={"name": "preview.html", "type": "text/html", "size": 1024},
        asset=f"{workspace.id}/preview.html",
        size=1024,
        workspace=workspace,
        project=project,
        issue=issue,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        is_uploaded=True,
    )


@pytest.fixture
def non_project_member_client(db, workspace):
    unique_id = uuid4().hex[:8]
    user = User.objects.create(
        email=f"attachment-outsider-{unique_id}@plane.so",
        username=f"attachment_outsider_{unique_id}",
        first_name="Attachment",
        last_name="Outsider",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.contract
@pytest.mark.django_db
class TestIssueAttachmentDisposition:
    def get_collection_url(self, workspace, project, issue):
        return (
            f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/"
            f"issues/{issue.id}/attachments/"
        )

    def get_url(self, workspace, project, issue, attachment):
        return (
            f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/"
            f"issues/{issue.id}/attachments/{attachment.id}/"
        )

    def get_preview_url(self, workspace, project, issue, attachment):
        return f"{self.get_url(workspace, project, issue, attachment)}preview/"

    def test_html_attachment_can_start_upload(self, session_client, workspace, project, issue):
        url = self.get_collection_url(workspace, project, issue)

        with patch(
            "plane.app.views.issue.attachment.S3Storage.generate_presigned_post",
            return_value={"url": "https://storage.example.com", "fields": {}},
        ):
            response = session_client.post(
                url,
                {"name": "report.html", "type": "text/html", "size": 1024},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["attachment"]["attributes"] == {
            "name": "report.html",
            "type": "text/html",
            "size": 1024,
        }

    @pytest.mark.parametrize(
        "query_string,expected_disposition",
        [
            ("", "attachment"),
            ("?disposition=inline", "inline"),
            ("?disposition=download", "attachment"),
        ],
    )
    def test_single_attachment_get_uses_allowed_content_disposition(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_attachment,
        query_string,
        expected_disposition,
    ):
        url = f"{self.get_url(workspace, project, issue, uploaded_attachment)}{query_string}"

        with patch(
            "plane.app.views.issue.attachment.S3Storage.generate_presigned_url",
            return_value="https://storage.example.com/preview.png",
        ) as mock_generate_presigned_url:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_302_FOUND
        mock_generate_presigned_url.assert_called_once_with(
            object_name=uploaded_attachment.asset.name,
            disposition=expected_disposition,
            filename=uploaded_attachment.attributes["name"],
        )

    def test_html_attachment_cannot_be_served_inline(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        url = f"{self.get_url(workspace, project, issue, uploaded_html_attachment)}?disposition=inline"

        with patch(
            "plane.app.views.issue.attachment.S3Storage.generate_presigned_url",
            return_value="https://storage.example.com/preview.html",
        ) as mock_generate_presigned_url:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_302_FOUND
        mock_generate_presigned_url.assert_called_once_with(
            object_name=uploaded_html_attachment.asset.name,
            disposition="attachment",
            filename=uploaded_html_attachment.attributes["name"],
        )

    def test_html_attachment_preview_returns_sanitized_plain_text(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        with patch(
            "plane.app.views.issue.attachment.S3Storage.download_file_content",
            return_value=b'<h1>Report</h1><script>alert("xss")</script>',
        ):
            response = session_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["Content-Type"] == "text/plain; charset=utf-8"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.content.decode("utf-8") == "<h1>Report</h1>"

    def test_non_html_attachment_cannot_use_html_preview(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_attachment,
    ):
        url = self.get_preview_url(workspace, project, issue, uploaded_attachment)

        with patch("plane.app.views.issue.attachment.S3Storage.download_file_content") as mock_download:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_download.assert_not_called()

    def test_html_preview_rejects_attachments_larger_than_five_mebibytes(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        uploaded_html_attachment.size = 5 * 1024 * 1024 + 1
        uploaded_html_attachment.save(update_fields=["size"])
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        with patch("plane.app.views.issue.attachment.S3Storage.download_file_content") as mock_download:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        mock_download.assert_not_called()

    def test_html_preview_rejects_storage_content_larger_than_five_mebibytes(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        uploaded_html_attachment.size = 5 * 1024 * 1024
        uploaded_html_attachment.save(update_fields=["size"])
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        with patch(
            "plane.app.views.issue.attachment.S3Storage.download_file_content",
            return_value=b"x" * (5 * 1024 * 1024 + 1),
        ) as mock_download:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        mock_download.assert_called_once_with(
            uploaded_html_attachment.asset.name,
            max_bytes=5 * 1024 * 1024,
        )

    def test_unuploaded_html_attachment_cannot_be_previewed(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        uploaded_html_attachment.is_uploaded = False
        uploaded_html_attachment.save(update_fields=["is_uploaded"])
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        response = session_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_html_preview_returns_bad_gateway_when_storage_read_fails(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        with patch(
            "plane.app.views.issue.attachment.S3Storage.download_file_content",
            return_value=None,
        ):
            response = session_client.get(url)

        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_html_preview_returns_bad_gateway_when_storage_read_raises(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        with patch(
            "plane.app.views.issue.attachment.S3Storage.download_file_content",
            side_effect=OSError("storage disconnected"),
        ):
            response = session_client.get(url)

        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_non_project_member_cannot_read_html_preview(
        self,
        non_project_member_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
    ):
        url = self.get_preview_url(workspace, project, issue, uploaded_html_attachment)

        with patch("plane.app.views.issue.attachment.S3Storage.download_file_content") as mock_download:
            response = non_project_member_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        mock_download.assert_not_called()

    def test_html_preview_does_not_cross_project_scope(
        self,
        session_client,
        workspace,
        project,
        issue,
        uploaded_html_attachment,
        create_user,
    ):
        other_project = Project.objects.create(
            name="Other Attachment Project",
            identifier="OAP",
            workspace=workspace,
        )
        ProjectMember.objects.create(project=other_project, member=create_user, role=20)
        url = (
            f"/api/assets/v2/workspaces/{workspace.slug}/projects/{other_project.id}/"
            f"issues/{issue.id}/attachments/{uploaded_html_attachment.id}/preview/"
        )

        with patch("plane.app.views.issue.attachment.S3Storage.download_file_content") as mock_download:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_download.assert_not_called()

    def test_html_preview_does_not_cross_workspace_scope(
        self,
        session_client,
        issue,
        uploaded_html_attachment,
        create_user,
    ):
        unique_id = uuid4().hex[:8]
        other_workspace = Workspace.objects.create(
            name="Other Attachment Workspace",
            owner=create_user,
            slug=f"other-attachment-{unique_id}",
        )
        WorkspaceMember.objects.create(workspace=other_workspace, member=create_user, role=20)
        other_project = Project.objects.create(
            name="Other Workspace Project",
            identifier="OWP",
            workspace=other_workspace,
        )
        ProjectMember.objects.create(project=other_project, member=create_user, role=20)
        url = (
            f"/api/assets/v2/workspaces/{other_workspace.slug}/projects/{other_project.id}/"
            f"issues/{issue.id}/attachments/{uploaded_html_attachment.id}/preview/"
        )

        with patch("plane.app.views.issue.attachment.S3Storage.download_file_content") as mock_download:
            response = session_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_download.assert_not_called()
