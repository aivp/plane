# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4
from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import APIToken, FileAsset, Project, ProjectMember, User


def create_uploaded_asset(
    workspace,
    create_user,
    project=None,
    name="preview.png",
    asset_type="image/png",
):
    return FileAsset.objects.create(
        attributes={"name": name, "type": asset_type, "size": 1024},
        asset=f"{workspace.id}/{uuid4().hex}-{name}",
        size=1024,
        workspace=workspace,
        project=project,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        is_uploaded=True,
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestGenericAssetAPIEndpoint:
    """Contract tests for /api/v1/workspaces/{slug}/assets/{asset_id}/."""

    def get_url(self, workspace_slug, asset_id):
        return f"/api/v1/workspaces/{workspace_slug}/assets/{asset_id}/"

    def test_get_uploaded_workspace_asset_returns_presigned_download_url(self, api_key_client, workspace, create_user):
        asset = create_uploaded_asset(workspace=workspace, create_user=create_user)

        with patch(
            "plane.api.views.asset.S3Storage.generate_presigned_url",
            return_value="https://storage.example.com/presigned-preview.png",
        ) as mock_generate_presigned_url:
            response = api_key_client.get(self.get_url(workspace.slug, asset.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "asset_id": str(asset.id),
            "asset_url": "https://storage.example.com/presigned-preview.png",
            "asset_name": "preview.png",
            "asset_type": "image/png",
        }
        mock_generate_presigned_url.assert_called_once_with(
            object_name=asset.asset.name,
            filename=asset.attributes["name"],
            disposition="inline",
        )

    def test_get_project_asset_returns_presigned_download_url_for_project_member(
        self, api_key_client, workspace, create_user
    ):
        project = Project.objects.create(name="Asset Project", identifier="AST", workspace=workspace)
        ProjectMember.objects.create(project=project, member=create_user, role=20)
        asset = create_uploaded_asset(workspace=workspace, create_user=create_user, project=project)

        with patch(
            "plane.api.views.asset.S3Storage.generate_presigned_url",
            return_value="https://storage.example.com/project-preview.png",
        ) as mock_generate_presigned_url:
            response = api_key_client.get(self.get_url(workspace.slug, asset.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["asset_url"] == "https://storage.example.com/project-preview.png"
        mock_generate_presigned_url.assert_called_once_with(
            object_name=asset.asset.name,
            filename=asset.attributes["name"],
            disposition="inline",
        )

    def test_get_script_capable_asset_forces_attachment_disposition(self, api_key_client, workspace, create_user):
        asset = create_uploaded_asset(
            workspace=workspace,
            create_user=create_user,
            name="diagram.svg",
            asset_type="image/svg+xml",
        )

        with patch(
            "plane.api.views.asset.S3Storage.generate_presigned_url",
            return_value="https://storage.example.com/diagram.svg",
        ) as mock_generate_presigned_url:
            response = api_key_client.get(self.get_url(workspace.slug, asset.id))

        assert response.status_code == status.HTTP_200_OK
        mock_generate_presigned_url.assert_called_once_with(
            object_name=asset.asset.name,
            filename="diagram.svg",
            disposition="attachment",
        )

    def test_get_project_asset_rejects_non_project_member(self, api_key_client, workspace, create_user):
        project = Project.objects.create(name="Private Asset Project", identifier="PAP", workspace=workspace)
        asset = create_uploaded_asset(workspace=workspace, create_user=create_user, project=project)

        with patch("plane.api.views.asset.S3Storage.generate_presigned_url") as mock_generate_presigned_url:
            response = api_key_client.get(self.get_url(workspace.slug, asset.id))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {"error": "You are not allowed to download this asset"}
        mock_generate_presigned_url.assert_not_called()

    def test_get_workspace_asset_rejects_non_workspace_member(self, api_client, workspace, create_user):
        outsider_id = uuid4().hex[:8]
        outsider = User.objects.create(
            email=f"outsider-{outsider_id}@plane.so",
            username=f"outsider_{outsider_id}",
            first_name="Out",
            last_name="Sider",
        )
        outsider_token = APIToken.objects.create(
            user=outsider,
            label="Outsider API Token",
            token=f"test-outsider-token-{outsider_id}",
        )
        api_client.credentials(HTTP_X_API_KEY=outsider_token.token)
        asset = create_uploaded_asset(workspace=workspace, create_user=create_user)

        with patch("plane.api.views.asset.S3Storage.generate_presigned_url") as mock_generate_presigned_url:
            response = api_client.get(self.get_url(workspace.slug, asset.id))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert str(response.data["detail"]) == "You do not have permission to perform this action."
        mock_generate_presigned_url.assert_not_called()
