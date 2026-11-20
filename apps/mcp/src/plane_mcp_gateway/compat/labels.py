"""保留标签列表、分页字典与可空更新字段。"""

from typing import Any

from plane.models.labels import CreateLabel, Label, PaginatedLabelResponse, UpdateLabel
from plane_mcp.tools import label

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.resources import resource_handler

label_action = resource_handler(label)


def list_labels(
    project_id: str,
    params: dict[str, Any] | None = None,
) -> list[Label]:
    """
    List all labels in a project.

    Args:
        project_id: UUID of the project
        params: Optional query parameters as a dictionary

    Returns:
        List of Label objects
    """
    # 透传旧分页字典，调用方直接读取标签数组。
    client, workspace_slug = get_plane_client_context()
    response: PaginatedLabelResponse = client.labels.list(
        workspace_slug=workspace_slug, project_id=project_id, params=params
    )
    return response.results


def create_label(
    project_id: str,
    name: str,
    color: str | None = None,
    description: str | None = None,
    parent: str | None = None,
    sort_order: float | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
) -> Label:
    """
    Create a new label.

    Args:
        project_id: UUID of the project
        name: Label name
        color: Label color (hex color code)
        description: Label description
        parent: UUID of the parent label (for nested labels)
        sort_order: Sort order for the label
        external_source: External system source name
        external_id: External system identifier

    Returns:
        Created Label object
    """
    # 保留父标签、排序值及外部系统标识。
    client, workspace_slug = get_plane_client_context()

    data = CreateLabel(
        name=name,
        color=color,
        description=description,
        parent=parent,
        sort_order=sort_order,
        external_source=external_source,
        external_id=external_id,
    )

    return client.labels.create(
        workspace_slug=workspace_slug, project_id=project_id, data=data
    )


def retrieve_label(project_id: str, label_id: str) -> Label:
    """
    Retrieve a label by ID.

    Args:
        project_id: UUID of the project
        label_id: UUID of the label

    Returns:
        Label object
    """
    # 将旧标识参数绑定到指定资源的读取操作。
    return label_action("retrieve", project_id=project_id, label_id=label_id)


def update_label(
    project_id: str,
    label_id: str,
    name: str | None = None,
    color: str | None = None,
    description: str | None = None,
    parent: str | None = None,
    sort_order: float | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
) -> Label:
    """
    Update a label by ID.

    Args:
        project_id: UUID of the project
        label_id: UUID of the label
        name: Label name
        color: Label color (hex color code)
        description: Label description
        parent: UUID of the parent label (for nested labels)
        sort_order: Sort order for the label
        external_source: External system source name
        external_id: External system identifier

    Returns:
        Updated Label object
    """
    # 保留零排序值和显式传入的文本。
    client, workspace_slug = get_plane_client_context()

    data = UpdateLabel(
        name=name,
        color=color,
        description=description,
        parent=parent,
        sort_order=sort_order,
        external_source=external_source,
        external_id=external_id,
    )

    return client.labels.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        label_id=label_id,
        data=data,
    )


def delete_label(project_id: str, label_id: str) -> None:
    """
    Delete a label by ID.

    Args:
        project_id: UUID of the project
        label_id: UUID of the label
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    label_action("delete", project_id=project_id, label_id=label_id)
