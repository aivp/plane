# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.shortcuts import get_object_or_404

# Third party imports
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

# Module imports
from .. import BaseViewSet
from plane.app.permissions import ROLE, ProjectLitePermission, allow_permission
from plane.app.serializers import ProjectMemberLiteSerializer
from plane.app.serializers.issue import IssueSubscriberCreateSerializer, IssueSubscriberSerializer
from plane.db.models import Issue, IssueSubscriber, ProjectMember


class IssueSubscriberViewSet(BaseViewSet):
    serializer_class = IssueSubscriberSerializer
    model = IssueSubscriber

    permission_classes = [ProjectLitePermission]

    def get_visible_issue(self, *, editable=False):
        manager = Issue.issue_objects if editable else Issue.objects
        issues = (
            manager.select_related("project")
            .only("id", "created_by_id", "workspace_id", "project__workspace_id", "project__guest_view_all_features")
            .filter(
                workspace__slug=self.workspace_slug,
                project_id=self.project_id,
                project__deleted_at__isnull=True,
                workspace__deleted_at__isnull=True,
            )
        )
        issue = get_object_or_404(issues, pk=self.kwargs["issue_id"])
        if not issue.get_subscription_members().filter(member=self.request.user).exists():
            raise PermissionDenied("You are not allowed to view this issue.")
        return issue

    def list(self, request, slug, project_id, issue_id):
        self.get_visible_issue()
        members = ProjectMember.objects.filter(
            workspace__slug=slug, project_id=project_id, is_active=True
        ).select_related("member")
        serializer = ProjectMemberLiteSerializer(members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def subscriber_ids(self, request, slug, project_id, issue_id):
        issue = self.get_visible_issue()
        visible_members = issue.get_subscription_members().values("member_id")
        subscriber_ids = issue.issue_subscribers.filter(
            project_id=project_id, subscriber__is_bot=False, subscriber_id__in=visible_members
        ).values_list("subscriber_id", flat=True)
        return Response(list(subscriber_ids))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, issue_id):
        issue = self.get_visible_issue(editable=True)
        serializer = IssueSubscriberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscriber_id = serializer.validated_data["subscriber"]
        eligible = issue.get_subscription_members().filter(
            member_id=subscriber_id, member__is_bot=False, role__in=[ROLE.ADMIN.value, ROLE.MEMBER.value]
        )
        if not eligible.exists():
            raise ValidationError({"subscriber": "Select an active project member or administrator."})
        subscription, created = issue.issue_subscribers.get_or_create(
            project=issue.project, subscriber_id=subscriber_id
        )
        return Response(
            self.get_serializer(subscription).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, issue_id, subscriber_id):
        issue = self.get_visible_issue(editable=True)
        issue.issue_subscribers.filter(
            project_id=project_id,
            subscriber_id=subscriber_id,
            subscriber__is_bot=False,
            subscriber_id__in=issue.get_subscription_members().values("member_id"),
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def subscribe(self, request, slug, project_id, issue_id):
        issue = self.get_visible_issue()
        subscription, created = issue.issue_subscribers.get_or_create(project=issue.project, subscriber=request.user)
        if not created:
            return Response(
                {"message": "User already subscribed to the issue."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(subscription).data, status=status.HTTP_201_CREATED)

    def unsubscribe(self, request, slug, project_id, issue_id):
        issue = self.get_visible_issue()
        issue.issue_subscribers.filter(project_id=project_id, subscriber=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def subscription_status(self, request, slug, project_id, issue_id):
        issue = self.get_visible_issue()
        subscribed = issue.issue_subscribers.filter(project_id=project_id, subscriber=request.user).exists()
        return Response({"subscribed": subscribed}, status=status.HTTP_200_OK)
