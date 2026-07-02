# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import AgentIssueClaimAPIEndpoint, AgentIssueListAPIEndpoint, AgentTaskUpdateAPIEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/agent/issues/",
        AgentIssueListAPIEndpoint.as_view(http_method_names=["get"]),
        name="agent-issue-list",
    ),
    path(
        "workspaces/<str:slug>/agent/issues/<uuid:issue_id>/claim/",
        AgentIssueClaimAPIEndpoint.as_view(http_method_names=["post"]),
        name="agent-issue-claim",
    ),
    path(
        "workspaces/<str:slug>/agent/issues/<uuid:issue_id>/",
        AgentTaskUpdateAPIEndpoint.as_view(http_method_names=["patch"]),
        name="agent-issue-update",
    ),
]
