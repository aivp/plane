# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueAgentTaskSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import GithubManagedRepository, GithubRepositoryBranch, Issue, IssueAgentTask, ProjectMember, WorkspaceMember


def _is_project_or_workspace_admin(request, slug, project_id):
    return WorkspaceMember.objects.filter(
        workspace__slug=slug,
        member=request.user,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists() or ProjectMember.objects.filter(
        workspace__slug=slug,
        project_id=project_id,
        member=request.user,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists()


def _validate_repository_branch(slug, repository_id, base_branch):
    repository = GithubManagedRepository.objects.get(workspace__slug=slug, pk=repository_id)
    if not GithubRepositoryBranch.objects.filter(repository=repository, name=base_branch).exists():
        raise ValueError("Base branch does not exist in the selected repository.")
    return repository


class IssueAgentTaskEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        task = (
            IssueAgentTask.objects.filter(workspace__slug=slug, project_id=project_id, issue_id=issue_id)
            .select_related("repository")
            .first()
        )
        if not task:
            return Response(None, status=status.HTTP_200_OK)
        return Response(IssueAgentTaskSerializer(task).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def put(self, request, slug, project_id, issue_id):
        return self._upsert(request, slug, project_id, issue_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, issue_id):
        return self._upsert(request, slug, project_id, issue_id, partial=True)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, issue_id):
        task = IssueAgentTask.objects.filter(workspace__slug=slug, project_id=project_id, issue_id=issue_id).first()
        if not task:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if task.status == IssueAgentTask.Status.RUNNING:
            return Response({"error": "Running agent tasks cannot be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        if task.status == IssueAgentTask.Status.COMPLETED:
            return Response({"error": "Completed agent tasks cannot be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        task.status = IssueAgentTask.Status.CANCELLED
        task.save(update_fields=["status", "updated_at"])
        return Response(IssueAgentTaskSerializer(task).data, status=status.HTTP_200_OK)

    def _upsert(self, request, slug, project_id, issue_id, partial=False):
        issue = Issue.objects.get(workspace__slug=slug, project_id=project_id, pk=issue_id)
        task = IssueAgentTask.objects.filter(issue=issue).select_related("repository").first()

        repository_id = request.data.get("repository_id", task.repository_id if task else None)
        base_branch = request.data.get("base_branch", task.base_branch if task else None)
        next_status = request.data.get("status", IssueAgentTask.Status.PENDING)

        if not repository_id or not base_branch:
            return Response(
                {"error": "repository_id and base_branch are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if next_status != IssueAgentTask.Status.PENDING:
            return Response(
                {"error": "Users can only queue agent tasks with pending status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if task and task.status == IssueAgentTask.Status.RUNNING:
            return Response(
                {"error": "Running agent tasks cannot be changed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if task and task.status == IssueAgentTask.Status.COMPLETED and next_status == IssueAgentTask.Status.PENDING:
            if not _is_project_or_workspace_admin(request, slug, project_id):
                return Response(
                    {"error": "Only admins can reset a completed agent task."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            repository = _validate_repository_branch(slug, repository_id, base_branch)
        except (GithubManagedRepository.DoesNotExist, ValueError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if task is None:
            task = IssueAgentTask.objects.create(
                issue=issue,
                project=issue.project,
                workspace=issue.workspace,
                repository=repository,
                base_branch=base_branch,
                status=IssueAgentTask.Status.PENDING,
            )
        else:
            if task.status == IssueAgentTask.Status.FAILED and next_status == IssueAgentTask.Status.PENDING:
                task.retry_count += 1
                task.last_error = None
            if task.status == IssueAgentTask.Status.COMPLETED and next_status == IssueAgentTask.Status.PENDING:
                task.pr_url = None
                task.work_branch = None
                task.completed_at = None
                task.last_error = None
            task.repository = repository
            task.base_branch = base_branch
            task.status = next_status
            task.save()

        return Response(IssueAgentTaskSerializer(task).data, status=status.HTTP_200_OK)
