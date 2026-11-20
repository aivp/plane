"""保留旧版查询、增量更新和关系字段语义，通过请求级客户端调用 SDK。"""

from html import escape
from typing import Annotated, Any, get_args

from plane.errors.errors import HttpError
from plane.models.enums import PriorityEnum
from plane.models.query_params import (
    RetrieveQueryParams,
    WorkItemCountQueryParams,
    WorkItemQueryParams,
)
from plane.models.work_items import (
    CreateWorkItem,
    PaginatedWorkItemResponse,
    UpdateWorkItem,
    WorkItem,
    WorkItemDetail,
    WorkItemGroupedCountResponse,
    WorkItemSearch,
)
from plane_mcp.toolkit import envelope, ids_of
from plane_mcp.tools import workitem
from pydantic import Field

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)
from plane_mcp_gateway.compat.pql_help import PQL_FIELD_HINT, query_error
from plane_mcp_gateway.compat.resources import resource_handler


def _resolve_description_html(
    description_html: str | None, description_stripped: str | None
) -> str | None:
    """Resolve the description_html to persist.

    Plane recomputes description_stripped server-side from description_html on
    every save, so a stripped value sent on write is silently discarded. When the
    caller supplies only plain text, wrap it into minimal HTML so the description
    actually lands. description_html always wins when both are given.
    """
    if description_html is not None:
        return description_html
    if description_stripped is not None:
        return "<p>" + escape(description_stripped).replace("\n", "<br/>") + "</p>"
    return None


workitem_action = resource_handler(workitem)


def list_work_items(
    project_id: str | None = None,
    pql: Annotated[str | None, Field(description=PQL_FIELD_HINT)] = None,
    order_by: str | None = None,
    per_page: int | None = None,
    cursor: str | None = None,
    expand: str | None = None,
    fields: str | None = None,
    external_id: str | None = None,
    external_source: str | None = None,
) -> dict[str, Any]:
    """
    List work items with optional PQL filtering.

    Omit project_id to list across the entire workspace.
    Pass project_id to scope results to a single project.

    For UUID fields (assignee, state, label, cycle, module, type,
    milestone) call the relevant list tool first to get the UUID.

    Args:
        project_id: UUID of the project. Omit for workspace-wide results.
        pql: PQL filter. See field description for syntax.
        order_by: Sort field; prefix `-` for descending (e.g. `-created_at`).
        per_page: 1-100, default 25.
        cursor: From previous response's next_cursor.
        expand: Comma-separated relations to expand (e.g. assignees,labels,state).
        fields: Sparse fieldset — the response contains only the fields you
            name here (plus pagination metadata). Available: id, name,
            sequence_id, priority, state, project, assignees, labels, type_id,
            description_html, start_date, target_date, created_at, updated_at,
            created_by, is_draft. Use `project` (not `project_id`) and
            `description_html` (there is no `description` field); a misnamed
            field is simply absent from the result.
        external_id / external_source: Filter by external system.

    Returns:
        results: Paginated list of work items.
        total_count: True DB total, not page-bounded — use for counts.
        next_cursor: Cursor for the next page.
        prev_cursor: Cursor for the previous page.
    """
    # 是否传 project_id 决定查询项目还是整个工作区。
    client, workspace_slug = get_plane_client_context()

    params = WorkItemQueryParams(
        pql=pql,
        order_by=order_by,
        per_page=per_page,
        cursor=cursor,
        expand=expand,
        fields=fields,
        external_id=external_id,
        external_source=external_source,
    )

    try:
        if project_id:
            response: PaginatedWorkItemResponse = client.work_items.list(
                workspace_slug=workspace_slug,
                project_id=project_id,
                params=params,
            )
        else:
            response = client.work_items.list_workspace(
                workspace_slug=workspace_slug,
                params=params,
            )
    except HttpError as exc:
        return query_error("list_work_items", pql, exc)

    return envelope(response, fields)


def count_work_items(
    pql: Annotated[str | None, Field(description=PQL_FIELD_HINT)] = None,
    group_by: str | None = None,
    sub_group_by: str | None = None,
) -> dict[str, Any]:
    """
    Count work items across the workspace with optional grouping.

    Use this for analytics — "how many urgent items?", "distribution by state?" —
    without fetching full work item payloads.

    Args:
        pql: PQL filter to scope the count (e.g. 'priority = "urgent"').
        group_by: Dimension to group counts by. Supported values:
            state_id, state__group, priority, project_id, type_id,
            labels__id, assignees__id, issue_module__module_id,
            release_work_items__release_id, cycle_id, milestone_id,
            created_by, target_date, start_date.
        sub_group_by: Second dimension for nested grouping (requires group_by).

    Returns:
        grouped_by: The group_by field used (null if none).
        sub_grouped_by: The sub_group_by field used (null if none).
        total_count: Total matching work items.
        grouped_counts: Dict of group_key → {count} or
            {count, sub_grouped_counts} when sub_group_by is set.
            Keys are UUIDs for FK fields, plain strings for priority/state__group,
            ISO dates for target_date/start_date, "None" for unset values.
    """
    # 保留工作区计数的原始分组结构。
    client, workspace_slug = get_plane_client_context()
    params = WorkItemCountQueryParams(
        pql=pql, group_by=group_by, sub_group_by=sub_group_by
    )
    try:
        response: WorkItemGroupedCountResponse = client.work_items.count_workspace(
            workspace_slug=workspace_slug,
            params=params,
        )
    except HttpError as exc:
        return query_error("count_work_items", pql, exc)
    return response.model_dump()


def create_work_item(
    project_id: str,
    name: str,
    assignees: list[str] | None = None,
    labels: list[str] | None = None,
    type_id: str | None = None,
    point: int | None = None,
    description_html: str | None = None,
    description_stripped: str | None = None,
    priority: str | None = None,
    start_date: str | None = None,
    target_date: str | None = None,
    sort_order: float | None = None,
    is_draft: bool | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    parent: str | None = None,
    state: str | None = None,
    estimate_point: str | None = None,
    type: str | None = None,
) -> WorkItem:
    """
    Create a new work item.

    Args:
        project_id: UUID of the project
        name: Work item name (required)
        assignees: List of user IDs to assign to the work item
        labels: List of label IDs to attach to the work item
        type_id: UUID of the work item type
        point: Story point value
        description_html: HTML description of the work item
        description_stripped: Plain text description. Convenience only — it is
            wrapped into HTML and stored as description_html (Plane derives
            description_stripped server-side). Ignored if description_html is set.
        priority: Priority level (urgent, high, medium, low, none)
        start_date: Start date (ISO 8601 format)
        target_date: Target/end date (ISO 8601 format)
        sort_order: Sort order value
        is_draft: Whether the work item is a draft
        external_source: External system source name
        external_id: External system identifier
        parent: UUID of the parent work item
        state: UUID of the state
        estimate_point: Estimate point value
        type: Work item type identifier

    Returns:
        Created WorkItem object
    """
    # 保留旧 type 字段以及纯文本描述转 HTML 的规则。
    client, workspace_slug = get_plane_client_context()

    validated_priority: PriorityEnum | None = (
        priority if priority in get_args(PriorityEnum) else None  # type: ignore[assignment]
    )

    data = CreateWorkItem(
        name=name,
        assignees=assignees,
        labels=labels,
        type_id=type_id,
        point=point,
        description_html=_resolve_description_html(
            description_html, description_stripped
        ),
        priority=validated_priority,
        start_date=start_date,
        target_date=target_date,
        sort_order=sort_order,
        is_draft=is_draft,
        external_source=external_source,
        external_id=external_id,
        parent=parent,
        state=state,
        estimate_point=estimate_point,
        type=type,
    )

    return client.work_items.create(
        workspace_slug=workspace_slug, project_id=project_id, data=data
    )


def retrieve_work_item(
    project_id: str,
    work_item_id: str,
    expand: str | None = None,
    fields: str | None = None,
    external_id: str | None = None,
    external_source: str | None = None,
    order_by: str | None = None,
) -> WorkItemDetail:
    """
    Retrieve a work item by ID.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        expand: Comma-separated fields to expand (e.g., "assignees,labels,state")
        fields: Comma-separated fields to include in response
        external_id: External system identifier for filtering
        external_source: External system source name for filtering
        order_by: Field to order results by

    Returns:
        WorkItemDetail object with expanded relationships
    """
    # 将展开字段和稀疏字段选择交给当前项目的查询接口。
    client, workspace_slug = get_plane_client_context()

    params = RetrieveQueryParams(
        expand=expand,
        fields=fields,
        external_id=external_id,
        external_source=external_source,
        order_by=order_by,
    )

    return client.work_items.retrieve(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        params=params,
    )


def retrieve_work_item_by_identifier(
    work_item_identifier: str,
    expand: str | None = None,
    fields: str | None = None,
    external_id: str | None = None,
    external_source: str | None = None,
    order_by: str | None = None,
) -> WorkItemDetail:
    """
    Retrieve a work item by its full identifier (project prefix + sequence number).

    The identifier must be in PROJECT-N format where PROJECT is the project's
    identifier string and N is the sequence number. Both parts are required.

    Valid sparse `fields` values include: id, name, sequence_id, priority,
    state, project, workspace, parent, assignees, labels, type_id,
    start_date, target_date, created_at, updated_at, created_by,
    updated_by, is_draft, external_source, external_id, estimate_point.
    Use `project` (not `project_id`) to get the project UUID.

    If you need the project UUID from a short identifier like "SHO",
    use `list_projects()` instead — it returns `id` and `identifier`
    for every project.

    Args:
        work_item_identifier: Full work item identifier in PROJECT-N format
        expand: Comma-separated fields to expand (e.g., "assignees,labels,state")
        fields: Comma-separated sparse fieldset (see valid values above)
        external_id: External system identifier for filtering
        external_source: External system source name for filtering
        order_by: Field to order results by

    Returns:
        WorkItemDetail object with expanded relationships
    """
    # 从最后一个连字符拆分编号，允许项目前缀本身含连字符。
    parts = work_item_identifier.rsplit("-", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        raise ValueError(
            f"Invalid work item identifier {work_item_identifier!r}. "
            "Expected PROJECT-N format where N is the sequence number."
        )
    project_identifier, sequence_str = parts
    client, workspace_slug = get_plane_client_context()

    params = RetrieveQueryParams(
        expand=expand,
        fields=fields,
        external_id=external_id,
        external_source=external_source,
        order_by=order_by,
    )

    return client.work_items.retrieve_by_identifier(
        workspace_slug=workspace_slug,
        project_identifier=project_identifier,
        issue_identifier=int(sequence_str),
        params=params,
    )


def update_work_item(
    project_id: str,
    work_item_id: str,
    name: str | None = None,
    assignees: list[str] | None = None,
    labels: list[str] | None = None,
    type_id: str | None = None,
    point: int | None = None,
    description_html: str | None = None,
    description_stripped: str | None = None,
    priority: str | None = None,
    start_date: str | None = None,
    target_date: str | None = None,
    sort_order: float | None = None,
    is_draft: bool | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
    parent: str | None = None,
    state: str | None = None,
    estimate_point: str | None = None,
    type: str | None = None,
) -> WorkItem:
    """
    Update a work item by ID.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        name: Work item name
        assignees: List of user IDs to assign to the work item
        labels: List of label IDs to attach to the work item
        type_id: UUID of the work item type
        point: Story point value
        description_html: HTML description of the work item
        description_stripped: Plain text description. Convenience only — it is
            wrapped into HTML and stored as description_html (Plane derives
            description_stripped server-side). Ignored if description_html is set.
        priority: Priority level (urgent, high, medium, low, none)
        start_date: Start date (ISO 8601 format)
        target_date: Target/end date (ISO 8601 format)
        sort_order: Sort order value
        is_draft: Whether the work item is a draft
        external_source: External system source name
        external_id: External system identifier
        parent: UUID of the parent work item
        state: UUID of the state
        estimate_point: Estimate point value
        type: Work item type identifier

    Returns:
        Updated WorkItem object
    """
    client, workspace_slug = get_plane_client_context()

    validated_priority: PriorityEnum | None = (
        priority if priority in get_args(PriorityEnum) else None  # type: ignore[assignment]
    )

    changes = {
        "name": name,
        "assignees": assignees,
        "labels": labels,
        "type_id": type_id,
        "point": point,
        "description_html": _resolve_description_html(
            description_html, description_stripped
        ),
        "priority": validated_priority,
        "start_date": start_date,
        "target_date": target_date,
        "sort_order": sort_order,
        "is_draft": is_draft,
        "external_source": external_source,
        "external_id": external_id,
        "parent": parent,
        "state": state,
        "estimate_point": estimate_point,
        "type": type,
    }

    # 旧版忽略 None；新版 SDK 会将显式传入的 None 序列化为清空字段的 PATCH。
    data = UpdateWorkItem(
        **{key: value for key, value in changes.items() if value is not None}
    )
    return client.work_items.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        data=data,
    )


def delete_work_item(project_id: str, work_item_id: str) -> None:
    """
    Delete a work item by ID.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    workitem_action("delete", project_id=project_id, workitem_id=work_item_id)


def manage_work_item_assignee(
    project_id: str,
    work_item_id: str,
    add_user_id: str | None = None,
    remove_user_id: str | None = None,
) -> WorkItem:
    """
    Add or remove a single assignee on a work item without replacing the full list.

    Provide add_user_id, remove_user_id, or both. If both are given the
    removal is applied first, then the addition. Already-assigned users in
    add_user_id are silently skipped.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        add_user_id: UUID of the user to add as assignee
        remove_user_id: UUID of the user to remove from assignees

    Returns:
        Updated WorkItem object
    """
    # 先读取现有负责人，再移除和追加指定人员。
    client, workspace_slug = get_plane_client_context()
    current = client.work_items.retrieve(
        workspace_slug=workspace_slug, project_id=project_id, work_item_id=work_item_id
    )
    ids = ids_of(current.assignees)
    if remove_user_id:
        ids = [uid for uid in ids if uid != remove_user_id]
    if add_user_id and add_user_id not in ids:
        ids.append(add_user_id)
    return client.work_items.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        data=UpdateWorkItem(assignees=ids),
    )


def manage_work_item_label(
    project_id: str,
    work_item_id: str,
    add_label_id: str | None = None,
    remove_label_id: str | None = None,
) -> WorkItem:
    """
    Add or remove a single label on a work item without replacing the full list.

    Provide add_label_id, remove_label_id, or both. If both are given the
    removal is applied first, then the addition. Already-attached labels in
    add_label_id are silently skipped.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        add_label_id: UUID of the label to add
        remove_label_id: UUID of the label to remove

    Returns:
        Updated WorkItem object
    """
    # 保留现有标签，只应用本次要求的增减。
    client, workspace_slug = get_plane_client_context()
    current = client.work_items.retrieve(
        workspace_slug=workspace_slug, project_id=project_id, work_item_id=work_item_id
    )
    ids = ids_of(current.labels)
    if remove_label_id:
        ids = [lid for lid in ids if lid != remove_label_id]
    if add_label_id and add_label_id not in ids:
        ids.append(add_label_id)
    return client.work_items.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        work_item_id=work_item_id,
        data=UpdateWorkItem(labels=ids),
    )


def list_archived_work_items(
    project_id: str,
    pql: Annotated[str | None, Field(description=PQL_FIELD_HINT)] = None,
    order_by: str | None = None,
    per_page: int | None = None,
    cursor: str | None = None,
    expand: str | None = None,
    fields: str | None = None,
) -> dict[str, Any]:
    """
    List archived work items in a project with optional PQL filtering.

    Args:
        project_id: UUID of the project
        pql: PQL filter expression. Omit to list all archived items.
        order_by: Field to sort by; prefix with `-` for descending
            (default `-archived_at`).
        per_page: Results per page, 1-100 (default 100).
        cursor: Pagination cursor from a previous response's `next_cursor`.
        expand: Comma-separated related fields to expand.
        fields: Comma-separated sparse fieldset.

    Returns:
        Paginated envelope with results, total_count, next_cursor, prev_cursor.
    """
    # 归档列表仍支持 PQL 和字段选择。
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
        response = client.work_items.list_archived(
            workspace_slug=workspace_slug,
            project_id=project_id,
            params=params,
        )
    except HttpError as exc:
        return query_error("list_archived_work_items", pql, exc)
    return envelope(response, fields)


def manage_work_item_archive(project_id: str, work_item_id: str, archive: bool) -> None:
    """
    Archive or unarchive a work item.

    Only work items in a completed or cancelled state can be archived.
    Archived work items no longer appear in active work item lists.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        archive: True to archive the work item, False to unarchive it
    """
    # 按布尔值选择操作，维持旧版空返回。
    client, workspace_slug = get_plane_client_context()
    if archive:
        client.work_items.archive(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=work_item_id,
        )
    else:
        client.work_items.unarchive(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=work_item_id,
        )


def search_work_items(
    query: str,
    expand: str | None = None,
    fields: str | None = None,
    external_id: str | None = None,
    external_source: str | None = None,
    order_by: str | None = None,
) -> WorkItemSearch:
    """
    Search work items by text across a workspace.

    Matches on work item name, sequence id, and project identifier (not
    description). For structured filtering (priority, state, assignee,
    dates, etc.) use `list_work_items` with a PQL expression.

    Args:
        query: Free-text string matched against name, sequence id, and project identifier
        expand: Comma-separated list of related fields to expand in response
        fields: Comma-separated list of fields to include in response
        external_id: External system identifier for filtering
        external_source: External system source name for filtering
        order_by: Field to order results by. Prefix with '-' for descending

    Returns:
        WorkItemSearch object containing search results
    """
    # 保留按文本搜索时的展开和字段过滤。
    client, workspace_slug = get_plane_client_context()

    params = RetrieveQueryParams(
        expand=expand,
        fields=fields,
        external_id=external_id,
        external_source=external_source,
        order_by=order_by,
    )

    return client.work_items.search(
        workspace_slug=workspace_slug, query=query, params=params
    )
