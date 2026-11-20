"""保留项目分页默认值和旧功能开关，固定每个工具可以执行的操作。"""

from typing import get_args

from plane.models.enums import TimezoneEnum
from plane.models.projects import (
    CreateProject,
    PaginatedProjectLiteResponse,
    PaginatedProjectMemberResponse,
    Project,
    UpdateProject,
)
from plane.models.query_params import MemberListQueryParams, ProjectLiteListQueryParams
from plane_mcp.tools import project

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.resources import resource_handler

project_action = resource_handler(project)


def list_projects(
    cursor: str | None = None,
    per_page: int | None = None,
    order_by: str | None = None,
) -> PaginatedProjectLiteResponse:
    """
    List projects in a workspace (lite, paginated).

    Trimmed fields: id, identifier, name, description, emoji, icon_prop,
    cover_image, cover_image_url, archived_at. For full detail use retrieve_project.

    Args:
        cursor: Prior response's next_cursor; omit for first page.
        per_page: Results per page (1-1000, default 1000).
        order_by: Sort field; prefix '-' for descending.

    Returns:
        Paginated envelope: results + total_count, next_cursor,
        next_page_results (page again while next_page_results is true).
    """
    # 不设置 per_page，让 Plane 保留既有的默认页长。
    client, workspace_slug = get_plane_client_context()

    params = ProjectLiteListQueryParams(
        cursor=cursor, per_page=per_page, order_by=order_by, include_archived=False
    )

    return client.projects.list_lite(workspace_slug=workspace_slug, params=params)


def create_project(
    name: str,
    identifier: str,
    description: str | None = None,
    project_lead: str | None = None,
    default_assignee: str | None = None,
    emoji: str | None = None,
    cover_image: str | None = None,
    module_view: bool | None = None,
    cycle_view: bool | None = None,
    issue_views_view: bool | None = None,
    page_view: bool | None = None,
    intake_view: bool | None = None,
    guest_view_all_features: bool | None = None,
    archive_in: int | None = None,
    close_in: int | None = None,
    timezone: str | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    is_issue_type_enabled: bool | None = None,
) -> Project:
    """
    Create a new project.

    Args:
        workspace_slug: The workspace slug identifier
        name: Project name
        identifier: Project identifier (e.g., "MP" for "My Project")
        description: Project description
        project_lead: UUID of the project lead user
        default_assignee: UUID of the default assignee user
        emoji: Emoji for the project
        cover_image: Cover image URL or asset ID
        module_view: Enable module view
        cycle_view: Enable cycle view
        issue_views_view: Enable issue views view
        page_view: Enable page view
        intake_view: Enable intake view
        guest_view_all_features: Allow guests to view all features
        archive_in: Days until auto-archive
        close_in: Days until auto-close
        timezone: Project timezone
        external_source: External system source name
        external_id: External system identifier
        is_issue_type_enabled: Enable issue types

    Returns:
        Created Project object
    """
    # 把旧版独立的功能开关传给 SDK，包括显式关闭的开关。
    client, workspace_slug = get_plane_client_context()

    # Validate timezone against allowed literal values
    validated_timezone: TimezoneEnum | None = (
        timezone if timezone in get_args(TimezoneEnum) else None  # type: ignore[assignment]
    )

    data = CreateProject(
        name=name,
        identifier=identifier,
        description=description,
        project_lead=project_lead,
        default_assignee=default_assignee,
        emoji=emoji,
        cover_image=cover_image,
        module_view=module_view,
        cycle_view=cycle_view,
        issue_views_view=issue_views_view,
        page_view=page_view,
        intake_view=intake_view,
        guest_view_all_features=guest_view_all_features,
        archive_in=archive_in,
        close_in=close_in,
        timezone=validated_timezone,
        external_source=external_source,
        external_id=external_id,
        is_issue_type_enabled=is_issue_type_enabled,
    )

    return client.projects.create(workspace_slug=workspace_slug, data=data)


def retrieve_project(project_id: str) -> Project:
    """
    Retrieve a project by ID.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project

    Returns:
        Project object
    """
    # 将旧标识参数绑定到指定资源的读取操作。
    return project_action("retrieve", project_id=project_id)


def update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    project_lead: str | None = None,
    default_assignee: str | None = None,
    identifier: str | None = None,
    emoji: str | None = None,
    cover_image: str | None = None,
    network: int | None = None,
    module_view: bool | None = None,
    cycle_view: bool | None = None,
    issue_views_view: bool | None = None,
    page_view: bool | None = None,
    intake_view: bool | None = None,
    guest_view_all_features: bool | None = None,
    archive_in: int | None = None,
    close_in: int | None = None,
    timezone: str | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    is_issue_type_enabled: bool | None = None,
    is_time_tracking_enabled: bool | None = None,
    default_state: str | None = None,
    estimate: str | None = None,
) -> Project:
    """
    Update a project by ID.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
        name: Project name
        description: Project description
        project_lead: UUID of the project lead user
        default_assignee: UUID of the default assignee user
        identifier: Project identifier
        emoji: Emoji for the project
        cover_image: Cover image URL or asset ID
        network: Project visibility (0=secret, 2=public)
        module_view: Enable module view
        cycle_view: Enable cycle view
        issue_views_view: Enable issue views view
        page_view: Enable page view
        intake_view: Enable intake view
        guest_view_all_features: Allow guests to view all features
        archive_in: Days until auto-archive
        close_in: Days until auto-close
        timezone: Project timezone
        external_source: External system source name
        external_id: External system identifier
        is_issue_type_enabled: Enable issue types
        is_time_tracking_enabled: Enable time tracking
        default_state: UUID of the default state
        estimate: Estimate configuration

    Returns:
        Updated Project object
    """
    # 保留旧版网络类型校验和可空的项目开关。
    if network is not None and network not in {0, 2}:
        raise ValueError("network must be 0 (secret) or 2 (public)")

    client, workspace_slug = get_plane_client_context()

    # Validate timezone against allowed literal values
    validated_timezone: TimezoneEnum | None = (
        timezone if timezone in get_args(TimezoneEnum) else None  # type: ignore[assignment]
    )

    data = UpdateProject(
        name=name,
        description=description,
        project_lead=project_lead,
        default_assignee=default_assignee,
        identifier=identifier,
        emoji=emoji,
        cover_image=cover_image,
        network=network,
        module_view=module_view,
        cycle_view=cycle_view,
        issue_views_view=issue_views_view,
        page_view=page_view,
        intake_view=intake_view,
        guest_view_all_features=guest_view_all_features,
        archive_in=archive_in,
        close_in=close_in,
        timezone=validated_timezone,
        external_source=external_source,
        external_id=external_id,
        is_issue_type_enabled=is_issue_type_enabled,
        is_time_tracking_enabled=is_time_tracking_enabled,
        default_state=default_state,
        estimate=estimate,
    )

    return client.projects.update(
        workspace_slug=workspace_slug, project_id=project_id, data=data
    )


def delete_project(project_id: str) -> None:
    """
    Delete a project by ID.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    project_action("delete", project_id=project_id)


def manage_project_archive(project_id: str, archive: bool) -> None:
    """
    Archive or unarchive a project.

    Archived projects are hidden from active project lists but not deleted.
    All work items, cycles, and modules are preserved.

    Args:
        project_id: UUID of the project
        archive: True to archive the project, False to unarchive it
    """
    # 把旧版布尔开关映射为归档或恢复。
    project_action("archive" if archive else "unarchive", project_id=project_id)


def get_project_members(
    project_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
    role_slug: str | None = None,
    is_active: bool | None = None,
    is_bot: bool | None = None,
    cursor: str | None = None,
    per_page: int | None = 100,
    order_by: str | None = None,
) -> PaginatedProjectMemberResponse:
    """
    List members of a project (filterable, paginated).

    Optional filters first_name/last_name/email/display_name (case-insensitive
    contains), role_slug (exact), is_active, is_bot — combined with AND.

    Args:
        project_id: UUID of the project.
        cursor: Prior response's next_cursor; omit for first page.
        per_page: Results per page (1-1000, default 100).
        order_by: Sort field; prefix '-' for descending.

    Returns:
        Paginated envelope: results (members incl. role, role_slug,
        is_active, is_bot) + total_count, next_cursor, next_page_results.
    """
    # 保留成员过滤条件和每页 100 条的默认值。
    client, workspace_slug = get_plane_client_context()
    params = MemberListQueryParams(
        first_name=first_name,
        last_name=last_name,
        email=email,
        display_name=display_name,
        role_slug=role_slug,
        is_active=is_active,
        is_bot=is_bot,
        cursor=cursor,
        per_page=per_page,
        order_by=order_by,
    )
    return client.projects.get_members_lite(
        workspace_slug=workspace_slug, project_id=project_id, params=params
    )
