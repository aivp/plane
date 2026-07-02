# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import AgentTaskClaimAPIEndpoint, AgentTaskUpdateAPIEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/agent/tasks/claim/",
        AgentTaskClaimAPIEndpoint.as_view(http_method_names=["post"]),
        name="agent-task-claim",
    ),
    path(
        "workspaces/<str:slug>/agent/tasks/<uuid:task_id>/",
        AgentTaskUpdateAPIEndpoint.as_view(http_method_names=["patch"]),
        name="agent-task-update",
    ),
]
