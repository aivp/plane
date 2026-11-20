"""保留 active/archived 两套查询、周期成员操作及其返回类型。"""

from typing import Annotated, Any

from plane.errors.errors import HttpError
from plane.models.cycles import (
    CreateCycle,
    Cycle,
    PaginatedArchivedCycleResponse,
    PaginatedCycleLiteResponse,
    PaginatedCycleWorkItemResponse,
    UpdateCycle,
)
from plane.models.enums import CycleStatusEnum
from plane.models.query_params import (
    CycleLiteListQueryParams,
    LiteListQueryParams,
    WorkItemQueryParams,
)
from plane_mcp.toolkit import envelope
from plane_mcp.tools import cycle
from pydantic import Field

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.pql_help import PQL_FIELD_HINT, query_error
from plane_mcp_gateway.compat.resources import resource_handler

cycle_action = resource_handler(cycle)


def list_cycles(
    project_id: str,
    archived: bool = False,
    status: CycleStatusEnum | None = None,
    cursor: str | None = None,
    per_page: int | None = None,
    order_by: str | None = None,
) -> PaginatedCycleLiteResponse | PaginatedArchivedCycleResponse:
    """
    List cycles in a project. Active (non-archived) cycles by default.

    Args:
        project_id: UUID of the project
        archived: Set True to list archived cycles instead of active ones.
        status: Filter active cycles by status — "current" (running now),
            "upcoming" (starts later), "completed" (ended), "draft" (no dates),
            or "incomplete" (not yet finished). Ignored when archived is True.
        cursor: Pagination cursor from a previous response's next_cursor
            (form "{per_page}:{page}:{offset}"). Omit for the first page.
        per_page: Number of results per page (1-1000, default and max 1000).
        order_by: Field to order results by. Prefix with '-' for descending.

    Returns:
        Paginated envelope: results (lite cycles) + total_count,
        next_cursor, next_page_results.
    """
    # 归档列表和活动周期列表使用不同的 SDK 查询模型。
    client, workspace_slug = get_plane_client_context()
    if archived:
        params = LiteListQueryParams(
            cursor=cursor, per_page=per_page, order_by=order_by
        )
        return client.cycles.list_archived(
            workspace_slug=workspace_slug,
            project_id=project_id,
            params=params.model_dump(exclude_none=True),
        )
    params = CycleLiteListQueryParams(
        cursor=cursor, per_page=per_page, order_by=order_by, status=status
    )
    return client.cycles.list_lite(
        workspace_slug=workspace_slug, project_id=project_id, params=params
    )


def create_cycle(
    project_id: str,
    name: str,
    owned_by: str,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    timezone: str | None = None,
) -> Cycle:
    """
    Create a new cycle.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
        name: Cycle name
        owned_by: UUID of the user who owns the cycle
        description: Cycle description
        start_date: Cycle start date (ISO 8601 format)
        end_date: Cycle end date (ISO 8601 format)
        external_source: External system source name
        external_id: External system identifier
        timezone: Cycle timezone

    Returns:
        Created Cycle object
    """
    # 创建周期时保留负责人、起止日期和时区。
    client, workspace_slug = get_plane_client_context()

    data = CreateCycle(
        name=name,
        owned_by=owned_by,
        description=description,
        start_date=start_date,
        end_date=end_date,
        external_source=external_source,
        external_id=external_id,
        timezone=timezone,
        project_id=project_id,
    )

    return client.cycles.create(
        workspace_slug=workspace_slug, project_id=project_id, data=data
    )


def retrieve_cycle(project_id: str, cycle_id: str) -> Cycle:
    """
    Retrieve a cycle by ID.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
        cycle_id: UUID of the cycle

    Returns:
        Cycle object
    """
    # 将旧标识参数绑定到指定资源的读取操作。
    return cycle_action("retrieve", project_id=project_id, cycle_id=cycle_id)


def update_cycle(
    project_id: str,
    cycle_id: str,
    name: str | None = None,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    owned_by: str | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    timezone: str | None = None,
) -> Cycle:
    """
    Update a cycle by ID.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
        cycle_id: UUID of the cycle
        name: Cycle name
        description: Cycle description
        start_date: Cycle start date (ISO 8601 format)
        end_date: Cycle end date (ISO 8601 format)
        owned_by: UUID of the user who owns the cycle
        external_source: External system source name
        external_id: External system identifier
        timezone: Cycle timezone

    Returns:
        Updated Cycle object
    """
    # 按旧参数构造周期更新模型。
    client, workspace_slug = get_plane_client_context()

    data = UpdateCycle(
        name=name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        owned_by=owned_by,
        external_source=external_source,
        external_id=external_id,
        timezone=timezone,
    )

    return client.cycles.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        cycle_id=cycle_id,
        data=data,
    )


def delete_cycle(project_id: str, cycle_id: str) -> None:
    """
    Delete a cycle by ID.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
        cycle_id: UUID of the cycle
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    cycle_action("delete", project_id=project_id, cycle_id=cycle_id)


def manage_cycle_work_items(
    project_id: str,
    cycle_id: str,
    add_ids: list[str] | None = None,
    remove_ids: list[str] | None = None,
) -> None:
    """
    Add or remove work items on a cycle in a single call.

    At least one of add_ids or remove_ids must be provided.

    Args:
        project_id: UUID of the project
        cycle_id: UUID of the cycle
        add_ids: UUIDs of work items to add to the cycle
        remove_ids: UUIDs of work items to remove from the cycle
    """
    # 同时增删时按旧顺序执行，移除操作逐项发送。
    if not add_ids and not remove_ids:
        raise ValueError("At least one of add_ids or remove_ids must be provided.")
    client, workspace_slug = get_plane_client_context()
    if add_ids:
        client.cycles.add_work_items(
            workspace_slug=workspace_slug,
            project_id=project_id,
            cycle_id=cycle_id,
            issue_ids=add_ids,
        )
    if remove_ids:
        for work_item_id in remove_ids:
            client.cycles.remove_work_item(
                workspace_slug=workspace_slug,
                project_id=project_id,
                cycle_id=cycle_id,
                work_item_id=work_item_id,
            )


def list_cycle_work_items(
    project_id: str,
    cycle_id: str,
    pql: Annotated[str | None, Field(description=PQL_FIELD_HINT)] = None,
    order_by: str | None = None,
    per_page: int | None = None,
    cursor: str | None = None,
    expand: str | None = None,
    fields: str | None = None,
) -> dict[str, Any]:
    """
    List work items in a cycle with optional PQL filtering.

    Args:
        project_id: UUID of the project
        cycle_id: UUID of the cycle
        pql: PQL filter expression. See field description for syntax.
            Omit to list all items in the cycle.
        order_by: Field to sort by; prefix with `-` for descending.
        per_page: Results per page, 1-100 (default 25).
        cursor: Pagination cursor from a previous response's `next_cursor`.
        expand: Comma-separated related fields to expand.
        fields: Comma-separated sparse fieldset.

    Returns:
        Paginated envelope with results, total_count, next_cursor, prev_cursor.
    """
    # 保留分页结果和旧工具名对应的 PQL 错误提示。
    client, workspace_slug = get_plane_client_context()
    params = WorkItemQueryParams(
        pql=pql,
        order_by=order_by,
        per_page=per_page,
        cursor=cursor,
        expand=expand,
        fields=fields,
    )
    try:
        response: PaginatedCycleWorkItemResponse = client.cycles.list_work_items(
            workspace_slug=workspace_slug,
            project_id=project_id,
            cycle_id=cycle_id,
            params=params,
        )
    except HttpError as exc:
        return query_error("list_cycle_work_items", pql, exc)
    return envelope(response)


def transfer_cycle_work_items(
    project_id: str,
    cycle_id: str,
    new_cycle_id: str,
) -> None:
    """
    Transfer work items from one cycle to another.

    Args:
        workspace_slug: The workspace slug identifier
        project_id: UUID of the project
        cycle_id: UUID of the source cycle
        new_cycle_id: UUID of the target cycle to transfer issues to
    """
    # 固定为周期转移操作，两端周期均由调用方指定。
    cycle_action(
        "transfer_workitems",
        project_id=project_id,
        cycle_id=cycle_id,
        new_cycle_id=new_cycle_id,
    )


def manage_cycle_archive(project_id: str, cycle_id: str, archive: bool) -> bool:
    """
    Archive or unarchive a cycle.

    Plane requires the cycle end_date to be in the past before archiving.
    When archive=True, this tool automatically sets end_date to today if
    the cycle is still active (end_date is missing or in the future),
    then archives it.

    Args:
        project_id: UUID of the project
        cycle_id: UUID of the cycle
        archive: True to archive the cycle, False to unarchive it

    Returns:
        True if the operation completed successfully
    """
    # 把旧版布尔开关映射为归档或恢复。
    return cycle_action(
        "archive" if archive else "unarchive", project_id=project_id, cycle_id=cycle_id
    )


def complete_cycle(project_id: str, cycle_id: str) -> Cycle:
    """
    Complete (close) a cycle by setting its end date to today.

    Plane has no explicit "complete" action — a cycle is considered complete
    when its end_date is in the past. This tool sets end_date to today,
    effectively closing the cycle.

    Args:
        project_id: UUID of the project
        cycle_id: UUID of the cycle to complete

    Returns:
        Updated Cycle object
    """
    # 沿用上游将结束日期设为今天的行为。
    return cycle_action("complete", project_id=project_id, cycle_id=cycle_id)
