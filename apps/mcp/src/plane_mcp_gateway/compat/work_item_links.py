"""保留链接的旧字段及列表返回格式。"""

from typing import Any

from plane.models.work_items import (
    CreateWorkItemLink,
    PaginatedWorkItemLinkResponse,
    UpdateWorkItemLink,
    WorkItemLink,
)
from plane_mcp.tools import workitem_link

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.resources import resource_handler

workitem_link_action = resource_handler(workitem_link)


def list_work_item_links(
    project_id: str,
    work_item_id: str,
    params: dict[str, Any] | None = None,
) -> list[WorkItemLink]:
    """
    List links for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        params: Optional query parameters as a dictionary

    Returns:
        List of WorkItemLink objects
    """
    # 将原始查询参数传给 SDK，只返回链接数组。
    client, workspace_slug = get_plane_client_context()
    response: PaginatedWorkItemLinkResponse = client.work_items.links.list(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        params=params,
    )
    return response.results


def retrieve_work_item_link(
    project_id: str,
    work_item_id: str,
    link_id: str,
) -> WorkItemLink:
    """
    Retrieve a specific link for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        link_id: UUID of the link

    Returns:
        WorkItemLink object
    """
    # 将旧标识参数绑定到指定资源的读取操作。
    return workitem_link_action(
        "retrieve", project_id=project_id, workitem_id=work_item_id, link_id=link_id
    )


def create_work_item_link(
    project_id: str,
    work_item_id: str,
    url: str,
) -> WorkItemLink:
    """
    Create a link for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        url: URL of the link

    Returns:
        Created WorkItemLink object
    """
    # 用调用方提供的 URL 建立工作项链接。
    client, workspace_slug = get_plane_client_context()

    data = CreateWorkItemLink(url=url)

    return client.work_items.links.create(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        data=data,
    )


def update_work_item_link(
    project_id: str,
    work_item_id: str,
    link_id: str,
    url: str | None = None,
) -> WorkItemLink:
    """
    Update a link for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        link_id: UUID of the link
        url: Updated URL of the link

    Returns:
        Updated WorkItemLink object
    """
    # 按旧可空 URL 参数构造链接更新请求。
    client, workspace_slug = get_plane_client_context()

    data = UpdateWorkItemLink(url=url)

    return client.work_items.links.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        link_id=link_id,
        data=data,
    )


def delete_work_item_link(
    project_id: str,
    work_item_id: str,
    link_id: str,
) -> None:
    """
    Delete a link for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        link_id: UUID of the link
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    workitem_link_action(
        "delete", project_id=project_id, workitem_id=work_item_id, link_id=link_id
    )
