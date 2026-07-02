# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    GithubCredentialProfileSerializer,
    GithubManagedRepositorySerializer,
    GithubRepositoryBranchSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.db.models import GithubCredentialProfile, GithubManagedRepository, GithubRepositoryBranch, Workspace
from plane.integrations.github import (
    GitHubAPIError,
    sync_github_app_repositories,
    sync_repository_branches,
    verify_github_token,
)
from plane.license.utils.encryption import decrypt_data


class WorkspaceGithubCredentialEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug, credential_id=None):
        queryset = GithubCredentialProfile.objects.filter(workspace__slug=slug)
        if credential_id:
            credential = queryset.get(pk=credential_id)
            return Response(GithubCredentialProfileSerializer(credential).data, status=status.HTTP_200_OK)
        return Response(GithubCredentialProfileSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = GithubCredentialProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.save(workspace=workspace)
        return Response(GithubCredentialProfileSerializer(credential).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug, credential_id):
        credential = GithubCredentialProfile.objects.get(workspace__slug=slug, pk=credential_id)
        serializer = GithubCredentialProfileSerializer(credential, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        credential = serializer.save()
        return Response(GithubCredentialProfileSerializer(credential).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, credential_id):
        credential = GithubCredentialProfile.objects.get(workspace__slug=slug, pk=credential_id)
        if GithubManagedRepository.objects.filter(credential_profile=credential).exists():
            return Response(
                {"error": "Credential profile is still used by one or more repositories."},
                status=status.HTTP_409_CONFLICT,
            )
        credential.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceGithubCredentialVerifyEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug, credential_id):
        credential = GithubCredentialProfile.objects.get(workspace__slug=slug, pk=credential_id)
        try:
            verify_github_token(decrypt_data(credential.token_encrypted))
            credential.status = GithubCredentialProfile.Status.ACTIVE
            credential.last_verified_at = timezone.now()
            credential.last_error = None
        except GitHubAPIError as exc:
            credential.status = GithubCredentialProfile.Status.INVALID
            credential.last_error = str(exc)
        credential.save(update_fields=["status", "last_verified_at", "last_error", "updated_at"])
        return Response(GithubCredentialProfileSerializer(credential).data, status=status.HTTP_200_OK)


class WorkspaceGithubRepositoryEndpoint(BaseAPIView):
    def _queryset(self, slug):
        return (
            GithubManagedRepository.objects.filter(workspace__slug=slug)
            .select_related("credential_profile")
            .annotate(branch_count=Count("branches", filter=Q(branches__deleted_at__isnull=True)))
        )

    def _validate_credential(self, slug, credential_profile_id):
        if not credential_profile_id:
            return None
        return GithubCredentialProfile.objects.get(workspace__slug=slug, pk=credential_profile_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, repository_id=None):
        workspace = Workspace.objects.get(slug=slug)
        sync_github_app_repositories(workspace.id)
        queryset = self._queryset(slug)
        if repository_id:
            repository = queryset.get(pk=repository_id)
            return Response(GithubManagedRepositorySerializer(repository).data, status=status.HTTP_200_OK)
        return Response(GithubManagedRepositorySerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        if request.data.get("source") == GithubManagedRepository.Source.GITHUB_APP:
            return Response(
                {"error": "GitHub App repositories are synced automatically."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        credential_profile_id = request.data.get("credential_profile_id")
        self._validate_credential(slug, credential_profile_id)
        serializer = GithubManagedRepositorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            repository = serializer.save(workspace=workspace)
        except IntegrityError:
            return Response({"error": "Repository already exists."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(GithubManagedRepositorySerializer(repository).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug, repository_id):
        repository = GithubManagedRepository.objects.get(workspace__slug=slug, pk=repository_id)
        if "credential_profile_id" in request.data:
            self._validate_credential(slug, request.data.get("credential_profile_id"))
        serializer = GithubManagedRepositorySerializer(repository, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        repository = serializer.save()
        return Response(GithubManagedRepositorySerializer(repository).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, repository_id):
        repository = GithubManagedRepository.objects.get(workspace__slug=slug, pk=repository_id)
        if repository.issue_agent_tasks.exists():
            return Response(
                {"error": "Repository is used by one or more agent tasks."},
                status=status.HTTP_409_CONFLICT,
            )
        repository.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceGithubRepositorySyncBranchesEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug, repository_id):
        repository = GithubManagedRepository.objects.get(workspace__slug=slug, pk=repository_id)
        repository = sync_repository_branches(repository)
        queryset = (
            GithubManagedRepository.objects.filter(pk=repository.pk)
            .annotate(branch_count=Count("branches", filter=Q(branches__deleted_at__isnull=True)))
            .first()
        )
        return Response(GithubManagedRepositorySerializer(queryset).data, status=status.HTTP_200_OK)


class WorkspaceGithubRepositoryBranchesEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, repository_id):
        repository = GithubManagedRepository.objects.get(workspace__slug=slug, pk=repository_id)
        branches = GithubRepositoryBranch.objects.filter(repository=repository).order_by("-is_default", "name")
        return Response(
            {"results": GithubRepositoryBranchSerializer(branches, many=True).data},
            status=status.HTTP_200_OK,
        )
