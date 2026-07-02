# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import re
from typing import Any

from plane.db.models import IssueAgentTask


def agent_task_payload(task: IssueAgentTask | None) -> dict[str, Any] | None:
    if task is None:
        return None
    repository = task.repository
    return {
        "id": task.id,
        "status": task.status,
        "repository": (
            {
                "id": repository.id,
                "full_name": repository.full_name,
                "html_url": repository.html_url,
            }
            if repository
            else None
        ),
        "base_branch": task.base_branch,
        "work_branch": task.work_branch,
        "pr_url": task.pr_url,
        "last_error": task.last_error,
    }


def append_agent_task_payload(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issue_ids = [item.get("id") for item in items if item.get("id")]
    if not issue_ids:
        return items

    tasks = {
        task.issue_id: agent_task_payload(task)
        for task in IssueAgentTask.objects.filter(issue_id__in=issue_ids)
        .select_related("repository")
        .order_by("issue_id")
    }
    for item in items:
        item["agent_task"] = tasks.get(item.get("id"))
    return items


def make_agent_work_branch(project_identifier: str, sequence_id: int, title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    slug = slug[:48] or "work-item"
    return f"ai/{project_identifier}-{sequence_id}-{slug}"
