"""仅操作项目状态，保留 is_triage、零序号和显式 false。"""

from typing import Any, get_args

from plane.models.enums import GroupEnum
from plane.models.states import CreateState, PaginatedStateResponse, State, UpdateState

from plane_mcp_gateway.client import (
    get_caller_plane_client_context as get_plane_client_context,
)


def list_states(
    project_id: str,
    params: dict[str, Any] | None = None,
) -> list[State]:
    """
    List all states in a project.

    Args:
        project_id: UUID of the project
        params: Optional query parameters as a dictionary

    Returns:
        List of State objects
    """
    # 按原参数查询项目状态，剥离分页外层。
    client, workspace_slug = get_plane_client_context()
    response: PaginatedStateResponse = client.states.list(
        workspace_slug=workspace_slug, project_id=project_id, params=params
    )
    return response.results


def create_state(
    project_id: str,
    name: str,
    color: str,
    description: str | None = None,
    sequence: float | None = None,
    group: str | None = None,
    is_triage: bool | None = None,
    default: bool | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
) -> State:
    """
    Create a new state.

    Args:
        project_id: UUID of the project
        name: State name
        color: State color (hex color code)
        description: State description
        sequence: State sequence order
        group: State group (e.g., backlog, unstarted, started, completed, cancelled)
        is_triage: Whether this is a triage state
        default: Whether this is the default state
        external_source: External system source name
        external_id: External system identifier

    Returns:
        Created State object
    """
    # 保留 is_triage、default 和序号等旧字段。
    client, workspace_slug = get_plane_client_context()

    # Validate group against allowed literal values
    validated_group: GroupEnum | None = (
        group if group in get_args(GroupEnum) else None  # type: ignore[assignment]
    )

    data = CreateState(
        name=name,
        color=color,
        description=description,
        sequence=sequence,
        group=validated_group,
        is_triage=is_triage,
        default=default,
        external_source=external_source,
        external_id=external_id,
    )

    return client.states.create(
        workspace_slug=workspace_slug, project_id=project_id, data=data
    )


def retrieve_state(project_id: str, state_id: str) -> State:
    """
    Retrieve a state by ID.

    Args:
        project_id: UUID of the project
        state_id: UUID of the state

    Returns:
        State object
    """
    # 绑定项目级 SDK，空 project_id 也不能转向工作区状态库。
    client, workspace_slug = get_plane_client_context()
    return client.states.retrieve(
        workspace_slug=workspace_slug, project_id=project_id, state_id=state_id
    )


def update_state(
    project_id: str,
    state_id: str,
    name: str | None = None,
    color: str | None = None,
    description: str | None = None,
    sequence: float | None = None,
    group: str | None = None,
    is_triage: bool | None = None,
    default: bool | None = None,
    external_source: str | None = None,
    external_id: str | None = None,
) -> State:
    """
    Update a state by ID.

    Args:
        project_id: UUID of the project
        state_id: UUID of the state
        name: State name
        color: State color (hex color code)
        description: State description
        sequence: State sequence order
        group: State group (e.g., backlog, unstarted, started, completed, cancelled)
        is_triage: Whether this is a triage state
        default: Whether this is the default state
        external_source: External system source name
        external_id: External system identifier

    Returns:
        Updated State object
    """
    # 保留显式 false 和零序号，避免被当作缺省值。
    client, workspace_slug = get_plane_client_context()

    # Validate group against allowed literal values
    validated_group: GroupEnum | None = (
        group if group in get_args(GroupEnum) else None  # type: ignore[assignment]
    )

    data = UpdateState(
        name=name,
        color=color,
        description=description,
        sequence=sequence,
        group=validated_group,
        is_triage=is_triage,
        default=default,
        external_source=external_source,
        external_id=external_id,
    )

    return client.states.update(
        workspace_slug=workspace_slug,
        project_id=project_id,
        state_id=state_id,
        data=data,
    )


def delete_state(project_id: str, state_id: str) -> None:
    """
    Delete a state by ID.

    Args:
        project_id: UUID of the project
        state_id: UUID of the state
    """
    # 绑定项目级 SDK，空 project_id 也不能转向工作区状态库。
    client, workspace_slug = get_plane_client_context()
    client.states.delete(
        workspace_slug=workspace_slug, project_id=project_id, state_id=state_id
    )
