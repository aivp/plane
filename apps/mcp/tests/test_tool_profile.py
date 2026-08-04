from __future__ import annotations

from plane_mcp_gateway.app import create_app
from plane_mcp_gateway.tool_profile import PROJECT_MANAGEMENT_TOOL_NAMES


async def test_default_mcp_exposes_exact_project_management_tool_profile():
    app = create_app()

    tools = await app.state.fastmcp_server.list_tools(run_middleware=False)
    tool_names = {tool.name for tool in tools}

    assert len(tools) == 75
    assert len(tools) <= 80
    assert tool_names == PROJECT_MANAGEMENT_TOOL_NAMES


async def test_project_management_profile_keeps_core_workflows():
    app = create_app()

    tool_names = {
        tool.name
        for tool in await app.state.fastmcp_server.list_tools(run_middleware=False)
    }

    assert {
        "list_projects",
        "create_work_item",
        "update_work_item",
        "manage_work_item_assignee",
        "manage_cycle_work_items",
        "manage_module_work_items",
        "create_work_item_comment",
        "upload_work_item_attachment_from_url",
        "get_workspace_members",
    } <= tool_names


async def test_project_management_profile_hides_unused_or_unsupported_domains():
    app = create_app()
    mcp = app.state.fastmcp_server

    tool_names = {tool.name for tool in await mcp.list_tools(run_middleware=False)}

    assert {
        "create_release",
        "create_customer",
        "create_initiative",
        "create_milestone",
        "create_page",
        "create_work_item_property",
        "create_work_item_type",
        "create_work_log",
        "create_work_item_relation_definition",
        "update_workspace_features",
        "create_project_estimate",
    }.isdisjoint(tool_names)
    assert await mcp.get_tool("create_release") is None
