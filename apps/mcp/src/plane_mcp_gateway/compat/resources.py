"""读取 v0.3.6 的资源处理函数，资源本身不注册到公网网关。"""

from collections.abc import Callable
from types import ModuleType

from plane_mcp_gateway.client import get_caller_plane_client_context


class _HandlerRegistration(dict[str, Callable]):
    """上游 register 通过 @mcp.tool(...) 提供一个同步处理函数。"""

    def tool(self, *, name: str, **metadata):
        def register(fn):
            self[name] = fn
            return fn

        return register


def resource_handler(module: ModuleType) -> Callable:
    # 绑定该资源实际引用的客户端，包括网关启动前已导入的模块。
    module.get_plane_client_context = get_caller_plane_client_context
    registration = _HandlerRegistration()
    module.register(registration)
    handler = registration[module.NAME]
    required = {action.name: action.requires for action in module.ACTIONS}

    def call(action: str, **arguments):
        # 上游缺参时返回文本，旧删除工具的返回类型为 None，必须提前报告错误。
        for field in required[action]:
            if arguments.get(field) in (None, ""):
                raise ValueError(f"{field} is required")
        return handler(action=action, **arguments)

    return call
