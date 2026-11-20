"""保留活动查询的原始分页字典，返回活动数组。"""

from typing import Any

from plane.models.work_items import PaginatedWorkItemActivityResponse, WorkItemActivity
from plane_mcp.tools import workitem_activity

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.resources import resource_handler

workitem_activity_action = resource_handler(workitem_activity)


def list_work_item_activities(
    project_id: str,
    work_item_id: str,
    params: dict[str, Any] | None = None,
) -> list[WorkItemActivity]:
    """
    List activities for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        params: Optional query parameters as a dictionary

    Returns:
        List of WorkItemActivity objects
    """
    # 调用方按旧约定直接读取活动数组。
    client, workspace_slug = get_plane_client_context()
    response: PaginatedWorkItemActivityResponse = client.work_items.activities.list(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        params=params,
    )
    return response.results


def retrieve_work_item_activity(
    project_id: str,
    work_item_id: str,
    activity_id: str,
) -> WorkItemActivity:
    """
    Retrieve a specific activity for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        activity_id: UUID of the activity

    Returns:
        WorkItemActivity object
    """
    # 将旧标识参数绑定到指定资源的读取操作。
    return workitem_activity_action(
        "retrieve",
        project_id=project_id,
        workitem_id=work_item_id,
        activity_id=activity_id,
    )
