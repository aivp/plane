"""ASGI application exposing Plane tools over stateless Streamable HTTP."""

from __future__ import annotations

import socket

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from plane_mcp_gateway.auth import (
    ApiKeyValidator,
    CallerPlaneTokenVerifier,
    validate_api_key_with_plane,
)
from plane_mcp_gateway.request_config import Resolver
from plane_mcp_gateway.tool_profile import apply_project_management_tool_profile


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_app(
    *,
    api_key_validator: ApiKeyValidator = validate_api_key_with_plane,
    resolver: Resolver = socket.getaddrinfo,
):
    """Create the Remote MCP ASGI app with injectable external network boundaries."""

    mcp = FastMCP(
        "Plane Remote MCP",
        instructions=(
            "Use the Plane host, workspace, and API key supplied by the caller for this request. "
            "For personal to-do requests (我的待办), call get_my_todos_link and reply with its link directly. "
            "Do not list projects or tasks for this request."
        ),
        auth=CallerPlaneTokenVerifier(
            api_key_validator=api_key_validator, resolver=resolver
        ),
    )
    apply_project_management_tool_profile(mcp)
    app = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)
    app.routes.insert(0, Route("/mcp/healthz", health_check, methods=["GET"]))
    return app


app = create_app()
