from __future__ import annotations

import socket
import json

import requests
from starlette.testclient import TestClient

from plane_mcp_gateway.app import create_app
from plane_mcp_gateway.request_config import PlaneRequestConfig


INITIALIZE_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "gateway-test", "version": "1.0.0"},
    },
}


def public_resolver(host: str, port: int, *, type: int):
    assert type == socket.SOCK_STREAM
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def mcp_headers(**overrides: str) -> dict[str, str]:
    headers = {
        "X-Plane-Api-Key": "caller-api-key",
        "X-Plane-Workspace-Slug": "caller-workspace",
        "X-Plane-Api-Host-Url": "https://plane.example.com",
        "Accept": "application/json, text/event-stream",
    }
    headers.update(overrides)
    return headers


def test_mcp_rejects_request_without_caller_workspace():
    async def accept_credentials(config: PlaneRequestConfig) -> bool:
        return True

    app = create_app(api_key_validator=accept_credentials, resolver=public_resolver)
    headers = mcp_headers()
    headers.pop("X-Plane-Workspace-Slug")

    with TestClient(app) as client:
        response = client.post("/mcp", headers=headers, json=INITIALIZE_REQUEST)

    assert response.status_code in (401, 403)


def test_mcp_uses_only_the_three_values_from_the_current_request(monkeypatch):
    monkeypatch.setenv("PLANE_API_KEY", "wrong-deployment-key")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "wrong-deployment-workspace")
    monkeypatch.setenv("PLANE_API_HOST_URL", "https://wrong-deployment.example")
    validated: list[PlaneRequestConfig] = []

    async def capture_credentials(config: PlaneRequestConfig) -> bool:
        validated.append(config)
        return True

    app = create_app(api_key_validator=capture_credentials, resolver=public_resolver)

    with TestClient(app) as client:
        response = client.post("/mcp", headers=mcp_headers(), json=INITIALIZE_REQUEST)

    assert response.status_code == 200
    assert validated == [
        PlaneRequestConfig(
            api_key="caller-api-key",
            workspace_slug="caller-workspace",
            api_host_url="https://plane.example.com",
        )
    ]


def test_mcp_accepts_query_values_and_infers_same_origin_plane_host():
    validated: list[PlaneRequestConfig] = []

    async def capture_credentials(config: PlaneRequestConfig) -> bool:
        validated.append(config)
        return True

    app = create_app(api_key_validator=capture_credentials, resolver=public_resolver)

    with TestClient(app) as client:
        response = client.post(
            "/mcp?PLANE_API_KEY=query-api-key&PLANE_WORKSPACE_SLUG=query-workspace",
            headers={
                "Host": "plane.example.com",
                "X-Forwarded-Proto": "https",
                "Accept": "application/json, text/event-stream",
            },
            json=INITIALIZE_REQUEST,
        )

    assert response.status_code == 200
    assert validated == [
        PlaneRequestConfig(
            api_key="query-api-key",
            workspace_slug="query-workspace",
            api_host_url="https://plane.example.com",
        )
    ]


def test_mcp_rejects_conflicting_header_and_query_api_keys():
    validated: list[PlaneRequestConfig] = []

    async def capture_credentials(config: PlaneRequestConfig) -> bool:
        validated.append(config)
        return True

    app = create_app(api_key_validator=capture_credentials, resolver=public_resolver)

    with TestClient(app) as client:
        response = client.post(
            "/mcp?PLANE_API_KEY=different-query-key",
            headers=mcp_headers(),
            json=INITIALIZE_REQUEST,
        )

    assert response.status_code in (401, 403)
    assert validated == []


def test_app_has_health_check_but_no_oauth_authorization_routes():
    async def accept_credentials(config: PlaneRequestConfig) -> bool:
        return True

    app = create_app(api_key_validator=accept_credentials, resolver=public_resolver)

    with TestClient(app) as client:
        health = client.get("/mcp/healthz")
        oauth = client.get("/authorize")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert oauth.status_code == 404


def test_tool_call_builds_plane_client_from_the_current_request(monkeypatch):
    async def accept_credentials(config: PlaneRequestConfig) -> bool:
        return True

    observed_request: dict[str, object] = {}

    def fake_get(session, url, *, headers, params, timeout):
        observed_request.update(
            url=url, headers=headers, params=params, timeout=timeout
        )
        response = requests.Response()
        response.status_code = 200
        response.headers["content-type"] = "application/json"
        response._content = json.dumps(
            {
                "total_count": 0,
                "next_cursor": "",
                "prev_cursor": "",
                "next_page_results": False,
                "prev_page_results": False,
                "count": 0,
                "total_pages": 0,
                "total_results": 0,
                "results": [],
            }
        ).encode()
        return response

    monkeypatch.setattr(requests.Session, "get", fake_get)
    app = create_app(api_key_validator=accept_credentials, resolver=public_resolver)
    tool_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "list_projects", "arguments": {}},
    }

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={**mcp_headers(), "MCP-Protocol-Version": "2025-06-18"},
            json=tool_request,
        )

    assert response.status_code == 200
    assert observed_request["url"] == (
        "https://plane.example.com/api/v1/workspaces/caller-workspace/projects-lite/"
    )
    assert observed_request["headers"] == {
        "Content-Type": "application/json",
        "X-Api-Key": "caller-api-key",
    }
