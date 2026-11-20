"""使用上游 PQL 帮助，示例指向网关可发现的旧工具名。"""

from plane_mcp.pql_reference import (
    _FULL_REFERENCE_TEMPLATE,
    render,
)

# 保留调用方已发现的参数描述，避免推荐通用资源工具。
PQL_FIELD_HINT = (
    "Optional Plane Query Language (PQL) filter. Examples: "
    '`priority = "urgent" AND assignee = currentUser()`, '
    "`stateGroup IN openStates() AND isOverdue()`. "
    "UUID fields (project, assignee, state, label, cycle, module, type, milestone, createdBy) "
    "need UUIDs — call the relevant `list_*` tool first if you only have a name or short "
    "identifier (e.g. `LSS` → call `list_projects` and match `identifier` to get `id`). "
    "Call `get_pql_reference` for full PQL syntax before composing complex queries."
)
PQL_FULL_REFERENCE = render(
    _FULL_REFERENCE_TEMPLATE,
    {
        "projects": "`list_projects`",
        "members": "`get_workspace_members`",
        "states": "`list_states`",
        "labels": "`list_labels`",
        "cycles": "`list_cycles`",
        "modules": "`list_modules`",
        "types": "the Plane UI",
        "milestones": "the Plane UI",
        "properties": "the Plane UI",
    },
)


def query_error(name, pql, exc):
    """旧工具只将 PQL 的 400 转成可修正的结果，其余 SDK 异常继续上抛。"""
    if (
        pql
        and exc.status_code == 400
        and isinstance(exc.response, dict)
        and "pql" in exc.response
    ):
        return {
            "error": exc.response["pql"],
            "failed_pql": pql,
            "pql_reference": PQL_FULL_REFERENCE,
            "hint": f"The PQL above failed. Fix it using the reference and retry {name}.",
        }
    raise exc
