# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from django.utils import timezone

from plane.bgtasks.issue_activities_task import create_issue_activity


def test_create_issue_activity_tracks_v1_assignees_key():
    """MCP/v1 work item creation sends assignees, not assignee_ids."""
    assignee_id = str(uuid4())
    issue_id = str(uuid4())
    project_id = str(uuid4())
    workspace_id = str(uuid4())
    actor_id = str(uuid4())
    issue_activities = []
    created_activity = mock.Mock()

    with (
        mock.patch(
            "plane.bgtasks.issue_activities_task.Issue.objects.get",
            return_value=SimpleNamespace(created_at=timezone.now(), created_by_id=actor_id),
        ),
        mock.patch(
            "plane.bgtasks.issue_activities_task.IssueActivity.objects.create",
            return_value=created_activity,
        ),
        mock.patch("plane.bgtasks.issue_activities_task.track_assignees") as mocked_track_assignees,
    ):
        create_issue_activity(
            requested_data=json.dumps({"name": "Created through MCP", "assignees": [assignee_id]}),
            current_instance=None,
            issue_id=issue_id,
            project_id=project_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            issue_activities=issue_activities,
            epoch=1,
        )

    created_activity.save.assert_called_once_with(update_fields=["created_at", "actor_id"])
    mocked_track_assignees.assert_called_once()
    assert mocked_track_assignees.call_args.args[0]["assignees"] == [assignee_id]
