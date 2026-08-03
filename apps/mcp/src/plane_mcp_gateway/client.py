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


def install_dynamic_client_context() -> None:
    """Install the request-scoped context before upstream tools are imported."""

    upstream_client.get_plane_client_context = get_caller_plane_client_context
