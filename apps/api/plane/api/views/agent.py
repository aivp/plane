# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.serializers import IssueActivitySerializer, IssueCommentSerializer
from plane.api.views.base import BaseAPIView
from plane.bgtasks.notification_task import notifications
from plane.db.models import APIToken, IssueActivity, IssueAgentTask, IssueComment, IssueSubscriber, WorkspaceMember
from plane.utils.agent_task import make_agent_work_branch


def _issue_comment_queryset():
    return (
        IssueComment.objects.select_related("actor", "issue", "project", "workspace")
        .prefetch_related("comment_reactions__actor")
        .order_by("created_at")
    )


def _task_response(task):
    issue = task.issue
    repository = task.repository
    return {
        "issue": {
            "id": issue.id,
            "project_id": issue.project_id,
            "sequence_id": issue.sequence_id,
            "name": issue.name,
            "description_html": issue.description_html,
            "assignee_ids": list(issue.assignees.values_list("id", flat=True)),
            "comments": IssueCommentSerializer(issue.issue_comments.all(), many=True).data,
        },
        "status": task.status,
        "repository": {
            "id": repository.id,
            "full_name": repository.full_name,
            "html_url": repository.html_url,
        },
        "base_branch": task.base_branch,
        "work_branch": task.work_branch,
    }


def _get_agent_api_token(token, slug):
    api_token = APIToken.objects.select_related("workspace", "user").filter(token=token, is_active=True).first()
    if not api_token:
        return None

    if api_token.is_service:
        if api_token.workspace_id and api_token.workspace.slug == slug:
            return api_token
        return None

    if WorkspaceMember.objects.filter(workspace__slug=slug, member_id=api_token.user_id, is_active=True).exists():
        return api_token

    return None


def _responsible_user_ids(task):
    assignee_ids = list(task.issue.assignees.values_list("id", flat=True))
    if assignee_ids:
        return assignee_ids
    if task.issue.project.project_lead_id:
        return [task.issue.project.project_lead_id]
    if task.issue.created_by_id:
        return [task.issue.created_by_id]
    return []


def _notify_agent_task_update(api_token, task):
    epoch = int(timezone.now().timestamp())
    if task.status == IssueAgentTask.Status.COMPLETED:
        comment = "completed the Agent task"
        new_value = task.pr_url or task.status
    else:
        comment = "marked the Agent task as failed"
        new_value = task.last_error or task.status

    activity = IssueActivity.objects.create(
        issue_id=task.issue_id,
        actor_id=api_token.user_id,
        verb="updated",
        field="agent_task",
        old_value=None,
        new_value=new_value,
        comment=comment,
        project_id=task.project_id,
        workspace_id=task.workspace_id,
        epoch=epoch,
    )

    for user_id in _responsible_user_ids(task):
        IssueSubscriber.objects.get_or_create(
            issue_id=task.issue_id,
            subscriber_id=user_id,
            project_id=task.project_id,
            workspace_id=task.workspace_id,
        )

    notifications.delay(
        type="issue.activity.updated",
        issue_id=str(task.issue_id),
        actor_id=str(api_token.user_id),
        project_id=str(task.project_id),
        subscriber=False,
        issue_activities_created=json.dumps(
            IssueActivitySerializer([activity], many=True).data,
            cls=DjangoJSONEncoder,
        ),
        requested_data=json.dumps({}),
        current_instance=json.dumps({}),
    )


class AgentTaskClaimAPIEndpoint(BaseAPIView):
    def post(self, request, slug):
        api_token = _get_agent_api_token(request.auth, slug)
        if not api_token:
            return Response({"error": "Token is not allowed for this workspace."}, status=status.HTTP_403_FORBIDDEN)

        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response({"error": "agent_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = int(request.data.get("limit", 1) or 1)
        except (TypeError, ValueError):
            return Response({"error": "limit must be a number."}, status=status.HTTP_400_BAD_REQUEST)
        limit = max(1, min(limit, 10))
        claimed_tasks = []
        now = timezone.now()

        with transaction.atomic():
            tasks = (
                IssueAgentTask.objects.select_for_update(skip_locked=True)
                .filter(
                    workspace__slug=slug,
                    status=IssueAgentTask.Status.PENDING,
                    repository__isnull=False,
                )
                .exclude(base_branch="")
                .select_related("issue", "issue__project", "repository")
                .prefetch_related(Prefetch("issue__issue_comments", queryset=_issue_comment_queryset()))
                .order_by("created_at")[:limit]
            )
            for task in tasks:
                if not task.work_branch:
                    task.work_branch = make_agent_work_branch(
                        task.issue.project.identifier,
                        task.issue.sequence_id,
                        task.issue.name,
                    )
                task.status = IssueAgentTask.Status.RUNNING
                task.claimed_by = agent_id
                task.claimed_at = now
                task.started_at = now
                task.save(
                    update_fields=[
                        "work_branch",
                        "status",
                        "claimed_by",
                        "claimed_at",
                        "started_at",
                        "updated_at",
                    ]
                )
                claimed_tasks.append(task)

        return Response({"results": [_task_response(task) for task in claimed_tasks]}, status=status.HTTP_200_OK)


class AgentTaskUpdateAPIEndpoint(BaseAPIView):
    def patch(self, request, slug, issue_id):
        api_token = _get_agent_api_token(request.auth, slug)
        if not api_token:
            return Response({"error": "Token is not allowed for this workspace."}, status=status.HTTP_403_FORBIDDEN)

        task = (
            IssueAgentTask.objects.filter(workspace__slug=slug, issue_id=issue_id)
            .select_related("issue", "issue__project", "project", "repository")
            .prefetch_related(Prefetch("issue__issue_comments", queryset=_issue_comment_queryset()))
            .first()
        )
        if not task:
            return Response({"error": "Issue agent state not found."}, status=status.HTTP_404_NOT_FOUND)

        if task.status == IssueAgentTask.Status.COMPLETED:
            return Response({"error": "Issue agent state is already completed."}, status=status.HTTP_409_CONFLICT)

        if task.status != IssueAgentTask.Status.RUNNING:
            return Response({"error": "Issue agent state is not running."}, status=status.HTTP_409_CONFLICT)

        agent_id = request.data.get("agent_id")
        if agent_id and task.claimed_by and agent_id != task.claimed_by:
            return Response({"error": "Issue is claimed by another agent."}, status=status.HTTP_409_CONFLICT)

        next_status = request.data.get("status")
        if next_status not in [IssueAgentTask.Status.COMPLETED, IssueAgentTask.Status.FAILED]:
            return Response({"error": "status must be completed or failed."}, status=status.HTTP_400_BAD_REQUEST)

        if next_status == IssueAgentTask.Status.COMPLETED:
            pr_url = request.data.get("pr_url")
            if not pr_url:
                return Response({"error": "pr_url is required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                URLValidator()(pr_url)
            except ValidationError:
                return Response({"error": "pr_url is invalid."}, status=status.HTTP_400_BAD_REQUEST)

            task.status = IssueAgentTask.Status.COMPLETED
            task.pr_url = pr_url
            task.work_branch = request.data.get("work_branch") or task.work_branch
            task.last_error = None
            task.completed_at = timezone.now()
        else:
            last_error = request.data.get("last_error")
            if not last_error:
                return Response({"error": "last_error is required."}, status=status.HTTP_400_BAD_REQUEST)
            task.status = IssueAgentTask.Status.FAILED
            task.last_error = last_error
            task.completed_at = None

        task.save()
        _notify_agent_task_update(api_token, task)
        return Response(_task_response(task), status=status.HTTP_200_OK)
