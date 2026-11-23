"""Server-side tool profiles for the Plane Remote MCP interface."""

from __future__ import annotations

from fastmcp import FastMCP

from plane_mcp_gateway.client import get_my_todos_link
from plane_mcp_gateway.compat import (
    cycles,
    intake,
    labels,
    modules,
    pql,
    projects,
    states,
    users,
    work_item_activities,
    work_item_attachments,
    work_item_comments,
    work_item_links,
    work_item_relations,
    work_items,
    workspaces,
)

# 仅注册这些有明确签名的旧入口，不向调用方公开通用 action 分发器。
# 保持旧目录的顺序，以便调用方复用稳定的工具提示。
_PROJECT_MANAGEMENT_TOOLS = (
    projects.list_projects,
    projects.create_project,
    projects.retrieve_project,
    projects.update_project,
    projects.delete_project,
    projects.manage_project_archive,
    projects.get_project_members,
    work_items.list_work_items,
    work_items.count_work_items,
    work_items.create_work_item,
    work_items.retrieve_work_item,
    work_items.retrieve_work_item_by_identifier,
    work_items.update_work_item,
    work_items.delete_work_item,
    work_items.manage_work_item_assignee,
    work_items.manage_work_item_label,
    work_items.list_archived_work_items,
    work_items.manage_work_item_archive,
    work_items.search_work_items,
    work_item_activities.list_work_item_activities,
    work_item_activities.retrieve_work_item_activity,
    work_item_attachments.list_work_item_attachments,
    work_item_attachments.get_work_item_attachment_download_url,
    work_item_attachments.upload_work_item_attachment_from_url,
    work_item_attachments.delete_work_item_attachment,
    work_item_attachments.read_work_item_attachment,
    work_item_comments.list_work_item_comments,
    work_item_comments.retrieve_work_item_comment,
    work_item_comments.create_work_item_comment,
    work_item_comments.update_work_item_comment,
    work_item_comments.delete_work_item_comment,
    work_item_links.list_work_item_links,
    work_item_links.retrieve_work_item_link,
    work_item_links.create_work_item_link,
    work_item_links.update_work_item_link,
    work_item_links.delete_work_item_link,
    work_item_relations.list_work_item_relations,
    work_item_relations.create_work_item_relation,
    work_item_relations.remove_work_item_relation,
    cycles.list_cycles,
    cycles.create_cycle,
    cycles.retrieve_cycle,
    cycles.update_cycle,
    cycles.delete_cycle,
    cycles.manage_cycle_work_items,
    cycles.list_cycle_work_items,
    cycles.transfer_cycle_work_items,
    cycles.manage_cycle_archive,
    cycles.complete_cycle,
    users.get_me,
    modules.list_modules,
    modules.create_module,
    modules.retrieve_module,
    modules.update_module,
    modules.delete_module,
    modules.manage_module_work_items,
    modules.list_module_work_items,
    modules.manage_module_archive,
    intake.list_intake_work_items,
    intake.create_intake_work_item,
    intake.retrieve_intake_work_item,
    intake.update_intake_work_item,
    intake.delete_intake_work_item,
    labels.list_labels,
    labels.create_label,
    labels.retrieve_label,
    labels.update_label,
    labels.delete_label,
    states.list_states,
    states.create_state,
    states.retrieve_state,
    states.update_state,
    states.delete_state,
    workspaces.get_workspace_members,
    pql.get_pql_reference,
    get_my_todos_link,
)
PROJECT_MANAGEMENT_TOOL_NAMES = frozenset(
    fn.__name__ for fn in _PROJECT_MANAGEMENT_TOOLS
)


def apply_project_management_tool_profile(mcp: FastMCP) -> None:
    """把白名单直接注册为可发现、可调用的 MCP 工具。"""
    for fn in _PROJECT_MANAGEMENT_TOOLS:
        mcp.tool(fn)
