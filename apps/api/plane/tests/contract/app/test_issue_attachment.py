# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import FileAsset, Issue, Project, ProjectMember


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


@pytest.mark.contract
@pytest.mark.django_db
class TestIssueAttachmentDisposition:
    def get_url(self, workspace, project, issue, attachment):
        return (
            f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/"
            f"issues/{issue.id}/attachments/{attachment.id}/"
        )

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
