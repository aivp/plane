"""Server-side tool profiles for the Plane Remote MCP interface."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.transforms import Visibility


# The default interface is intentionally limited to project-management workflows
# supported by this repository's Community API routes. Keep this explicit so a
# future upstream dependency update cannot silently expose new tools.
PROJECT_MANAGEMENT_TOOL_NAMES = frozenset(
    {
        # Identity and membership
        "get_me",
        "get_workspace_members",
        # Projects
        "list_projects",
        "create_project",
        "retrieve_project",
        "update_project",
        "delete_project",
        "manage_project_archive",
        "get_project_members",
        # Work items
        "list_work_items",
        "count_work_items",
        "create_work_item",
        "retrieve_work_item",
        "retrieve_work_item_by_identifier",
        "update_work_item",
        "delete_work_item",
        "manage_work_item_assignee",
        "manage_work_item_label",
        "list_archived_work_items",
        "manage_work_item_archive",
        "search_work_items",
        # Cycles
        "list_cycles",
        "create_cycle",
        "retrieve_cycle",
        "update_cycle",
        "delete_cycle",
        "manage_cycle_work_items",
        "list_cycle_work_items",
        "transfer_cycle_work_items",
        "manage_cycle_archive",
        "complete_cycle",
        # Modules
        "list_modules",
        "create_module",
        "retrieve_module",
        "update_module",
        "delete_module",
        "manage_module_work_items",
        "list_module_work_items",
        "manage_module_archive",
        # Intake
        "list_intake_work_items",
        "create_intake_work_item",
        "retrieve_intake_work_item",
        "update_intake_work_item",
        "delete_intake_work_item",
        # Labels and states
        "list_labels",
        "create_label",
        "retrieve_label",
        "update_label",
        "delete_label",
        "list_states",
        "create_state",
        "retrieve_state",
        "update_state",
        "delete_state",
        # Comments and activity
        "list_work_item_comments",
        "retrieve_work_item_comment",
        "create_work_item_comment",
        "update_work_item_comment",
        "delete_work_item_comment",
        "list_work_item_activities",
        "retrieve_work_item_activity",
        # Attachments
        "list_work_item_attachments",
        "get_work_item_attachment_download_url",
        "upload_work_item_attachment_from_url",
        "delete_work_item_attachment",
        "read_work_item_attachment",
        # Links and relations
        "list_work_item_links",
        "retrieve_work_item_link",
        "create_work_item_link",
        "update_work_item_link",
        "delete_work_item_link",
        "list_work_item_relations",
        "create_work_item_relation",
        "remove_work_item_relation",
        # Query language help
        "get_pql_reference",
    }
)


def apply_project_management_tool_profile(mcp: FastMCP) -> None:
    """Expose only the default internal project-management tool interface."""

    mcp.add_transform(Visibility(False, components={"tool"}))
    mcp.add_transform(
        Visibility(
            True,
            names=set(PROJECT_MANAGEMENT_TOOL_NAMES),
            components={"tool"},
        )
    )
