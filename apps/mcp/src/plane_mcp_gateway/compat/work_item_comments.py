"""保留 comment_json、可空 access 和旧评论模型，列表返回评论数组。"""

from typing import Any, get_args

from plane.models.enums import AccessEnum
from plane.models.work_items import (
    CreateWorkItemComment,
    PaginatedWorkItemCommentResponse,
    UpdateWorkItemComment,
)
from plane.models.work_items import WorkItemComment as SDKComment
from plane_mcp.tools import workitem_comment
from pydantic import create_model

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.resources import resource_handler

workitem_comment_action = resource_handler(workitem_comment)


# 保持旧输出 schema，后端实际返回的扩展字段仍通过 SDK 的 extra=allow 透传。
WorkItemComment = create_model(
    "WorkItemComment",
    __config__=SDKComment.model_config,
    __doc__=SDKComment.__doc__,
    **{
        key: (field.annotation, field)
        for key, field in SDKComment.model_fields.items()
        if key != "parent"
    },
)


def _legacy_comment(comment: SDKComment) -> WorkItemComment:
    # SDK 0.3.1 为缺失的 parent 补 null；只用服务端提供的字段还原旧模型。
    return WorkItemComment.model_validate(comment.model_dump(exclude_unset=True))


def list_work_item_comments(
    project_id: str,
    work_item_id: str,
    params: dict[str, Any] | None = None,
) -> list[WorkItemComment]:
    """
    List comments for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        params: Optional query parameters as a dictionary

    Returns:
        List of WorkItemComment objects
    """
    # 仅返回评论数组，按旧模型保留服务端扩展字段。
    client, workspace_slug = get_plane_client_context()
    response: PaginatedWorkItemCommentResponse = client.work_items.comments.list(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        params=params,
    )
    return [_legacy_comment(comment) for comment in response.results]


def retrieve_work_item_comment(
    project_id: str,
    work_item_id: str,
    comment_id: str,
) -> WorkItemComment:
    """
    Retrieve a specific comment for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        comment_id: UUID of the comment

    Returns:
        WorkItemComment object
    """
    # 将旧标识参数绑定到指定资源的读取操作。
    client, workspace_slug = get_plane_client_context()
    comment = client.work_items.comments.retrieve(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        comment_id=comment_id,
    )
    return _legacy_comment(comment)


def create_work_item_comment(
    project_id: str,
    work_item_id: str,
    comment_html: str | None = None,
    comment_json: dict[str, Any] | None = None,
    access: str | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
) -> WorkItemComment:
    """
    Create a comment for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        comment_html: Comment content in HTML format
        comment_json: Comment content in JSON format
        access: Access level for the comment (INTERNAL or EXTERNAL)
        external_source: External system source name
        external_id: External system identifier

    Returns:
        Created WorkItemComment object
    """
    # 旧版允许传 comment_json，并支持可见范围筛选。
    client, workspace_slug = get_plane_client_context()

    # Validate access against allowed literal values
    validated_access: AccessEnum | None = (
        access if access in get_args(AccessEnum) else None  # type: ignore[assignment]
    )

    data = CreateWorkItemComment(
        comment_html=comment_html,
        comment_json=comment_json,
        access=validated_access,
        external_source=external_source,
        external_id=external_id,
    )

    comment = client.work_items.comments.create(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        data=data,
    )
    return _legacy_comment(comment)


def update_work_item_comment(
    project_id: str,
    work_item_id: str,
    comment_id: str,
    comment_html: str | None = None,
    comment_json: dict[str, Any] | None = None,
    access: str | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
) -> WorkItemComment:
    """
    Update a comment for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        comment_id: UUID of the comment
        comment_html: Comment content in HTML format
        comment_json: Comment content in JSON format
        access: Access level for the comment (INTERNAL or EXTERNAL)
        external_source: External system source name
        external_id: External system identifier

    Returns:
        Updated WorkItemComment object
    """
    # 保留旧评论正文和访问范围的参数类型。
    client, workspace_slug = get_plane_client_context()

    # Validate access against allowed literal values
    validated_access: AccessEnum | None = (
        access if access in get_args(AccessEnum) else None  # type: ignore[assignment]
    )

    data = UpdateWorkItemComment(
        comment_html=comment_html,
        comment_json=comment_json,
        access=validated_access,
        external_source=external_source,
        external_id=external_id,
    )

    comment = client.work_items.comments.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        comment_id=comment_id,
        data=data,
    )
    return _legacy_comment(comment)


def delete_work_item_comment(
    project_id: str,
    work_item_id: str,
    comment_id: str,
) -> None:
    """
    Delete a comment for a work item.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        comment_id: UUID of the comment
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    workitem_comment_action(
        "delete", project_id=project_id, workitem_id=work_item_id, comment_id=comment_id
    )
