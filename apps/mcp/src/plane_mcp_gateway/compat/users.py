"""通过当前请求的客户端查询用户身份。"""

from plane.models.users import UserLite
from plane_mcp.tools import member

from plane_mcp_gateway.compat.resources import resource_handler

member_action = resource_handler(member)


def get_me() -> UserLite:
    """
    Get current user information.

    Returns:
        UserLite object containing current user information
    """
    # 使用当前请求的凭据查询调用者。
    return member_action("me")
