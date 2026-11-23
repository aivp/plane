"""Create a Plane SDK client from the active MCP request."""

from __future__ import annotations

from fastmcp.server.dependencies import get_access_token
from plane import PlaneClient
import plane_mcp.client as upstream_client


def get_caller_plane_client_context() -> upstream_client.PlaneClientContext:
    """Return a client using only values captured from this request's headers."""

    access_token = get_access_token()
    if access_token is None:
        raise RuntimeError("No authenticated Plane MCP request is active")

    workspace_slug = access_token.claims.get("workspace_slug")
    api_host_url = access_token.claims.get("plane_api_host_url")
    if not isinstance(workspace_slug, str) or not isinstance(api_host_url, str):
        raise RuntimeError(
            "Authenticated Plane MCP request is missing caller configuration"
        )

    return upstream_client.PlaneClientContext(
        client=PlaneClient(base_url=api_host_url, api_key=access_token.token),
        workspace_slug=workspace_slug,
    )


def get_my_todos_link() -> str:
    """飞书群聊或私聊问“我的待办”“我有哪些待做的任务”时，直接回复返回的 Markdown 链接。无需查询成员、项目或任务。"""
    # 仅使用鉴权后确定的站点和工作区，打开链接的人由 Plane 登录会话识别。
    token = get_access_token()
    if token is None:
        raise RuntimeError("No authenticated Plane MCP request is active")
    url = f"{token.claims['plane_api_host_url']}/{token.claims['workspace_slug']}/workspace-views/my-todos/"
    return f"[打开我的待办]({url})"
