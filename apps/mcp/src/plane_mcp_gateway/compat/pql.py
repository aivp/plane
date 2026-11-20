"""按旧工具名称提供 PQL 参考。"""

from typing import Literal

from plane_mcp.pql_reference import PQL_FIELD_DESCRIPTION

from plane_mcp_gateway.compat.pql_help import PQL_FULL_REFERENCE


def get_pql_reference(detail: Literal["brief", "full"] = "full") -> dict:
    """
    Return the Plane Query Language (PQL) syntax reference.

    Call this when composing the `pql` filter for `list_work_items`,
    `list_archived_work_items`, `list_cycle_work_items`, `list_module_work_items`,
    or `count_work_items`.

    Args:
        detail: "full" (default) returns the comprehensive reference with
            all operators, functions, common mistakes, and worked examples.
            "brief" returns the compact field/operator/function quick
            reference (lighter payload for simple queries).

    Returns:
        Dict with `detail` (which version was returned) and `reference`
        (the PQL syntax text).
    """
    # 保留 brief 和 full 两种帮助入口。
    if detail == "brief":
        return {"detail": "brief", "reference": PQL_FIELD_DESCRIPTION}
    return {"detail": "full", "reference": PQL_FULL_REFERENCE}
