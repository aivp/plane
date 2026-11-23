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


def test_auth_preserves_upstream_throttling_and_retries_after_recovery(monkeypatch):
    import httpx

    # 先触发限流，随后撤销或恢复凭据，检查三种状态互不混淆。
    statuses = iter([429, 401, 200])

    async def get(client, url, **kwargs):
        assert url.endswith("/api/v1/users/me/")
        return httpx.Response(next(statuses), headers={"Retry-After": "17"})

    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    with TestClient(create_app(resolver=public_resolver)) as client:
        def initialize():
            return client.post("/mcp", headers=mcp_headers(), json=INITIALIZE_REQUEST)

        limited = initialize()
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "17"
        assert initialize().status_code == 401
        assert initialize().status_code == 200


def test_auth_coalesces_parallel_requests_and_isolates_credentials():
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    validated = []

    async def validate(config):
        validated.append(config)
        await asyncio.sleep(0.04)
        return True

    with TestClient(create_app(api_key_validator=validate, resolver=public_resolver)) as client:
        def initialize(headers):
            return client.post("/mcp", headers=headers, json=INITIALIZE_REQUEST).status_code

        # 同时握手、发现与调用工具共享验证结果；切换租户或密钥时需重新验证。
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(initialize, [mcp_headers()] * 8)) == [200] * 8
        assert len(validated) == 1
        for field, value in [
            ("X-Plane-Api-Key", "second-key"),
            ("X-Plane-Api-Host-Url", "https://other.example.com"),
            ("X-Plane-Workspace-Slug", "other-workspace"),
        ]:
            assert initialize(mcp_headers(**{field: value})) == 200
        assert len(validated) == 4


def test_revoked_key_is_rechecked_after_short_auth_cache(monkeypatch):
    from plane_mcp_gateway import auth

    # 缓存仅复用近期的握手结果，到期后必须重新验证已撤销的密钥。
    now = 100.0
    accepted = True

    async def validate(config):
        return accepted

    monkeypatch.setattr(auth, "monotonic", lambda: now)
    with TestClient(create_app(api_key_validator=validate, resolver=public_resolver)) as client:
        def initialize():
            return client.post("/mcp", headers=mcp_headers(), json=INITIALIZE_REQUEST).status_code

        assert initialize() == 200
        accepted = False
        now += 16
        assert initialize() == 401
