"""Authentication for caller-provided Plane API credentials."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import socket
import time

import httpx
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.dependencies import get_http_headers, get_http_request
from starlette.datastructures import MutableHeaders, QueryParams
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from plane_mcp_gateway.request_config import (
    InvalidPlaneRequestConfig,
    PlaneRequestConfig,
    QUERY_API_KEY,
    Resolver,
    API_KEY_HEADER,
)


logger = logging.getLogger(__name__)

ApiKeyValidator = Callable[[PlaneRequestConfig], Awaitable[bool]]


class PlaneApiKeyAuthMiddleware:
    """Adapt a Plane API key header or query value to FastMCP bearer auth."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope = dict(scope)
            scope["headers"] = list(scope["headers"])
            headers = MutableHeaders(scope=scope)
            api_key = headers.get(API_KEY_HEADER) or _query_api_key(scope)
            if api_key and not headers.get("Authorization"):
                headers["Authorization"] = f"Bearer {api_key}"
        await self.app(scope, receive, send)


def _query_api_key(scope: Scope) -> str:
    query = QueryParams(scope.get("query_string", b"").decode("latin-1"))
    values = [
        value.strip()
        for name, value in query.multi_items()
        if name.lower() == QUERY_API_KEY and value.strip()
    ]
    return values[0] if len(set(values)) == 1 else ""


def _request_origin() -> str | None:
    request = get_http_request()
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    scheme = forwarded_proto.split(",", 1)[0].strip() or request.url.scheme
    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = forwarded_host.split(",", 1)[0].strip() or request.headers.get("host", "")
    return f"{scheme}://{host}" if scheme and host else None


async def validate_api_key_with_plane(config: PlaneRequestConfig) -> bool:
    """Validate a caller key against the Plane host supplied in the same request."""

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(
                f"{config.api_host_url}/api/v1/users/me/",
                headers={"x-api-key": config.api_key, "Accept": "application/json"},
            )
    except httpx.RequestError:
        logger.warning("Plane API key validation request failed", exc_info=True)
        return False
    return response.status_code == 200


class CallerPlaneTokenVerifier(TokenVerifier):
    """Turn one request's Plane settings into a FastMCP access token."""

    def __init__(
        self,
        *,
        api_key_validator: ApiKeyValidator = validate_api_key_with_plane,
        resolver: Resolver = socket.getaddrinfo,
    ) -> None:
        super().__init__(required_scopes=["read", "write"])
        self._api_key_validator = api_key_validator
        self._resolver = resolver

    def get_middleware(self) -> list:
        return [Middleware(PlaneApiKeyAuthMiddleware), *super().get_middleware()]

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            request = get_http_request()
            config = PlaneRequestConfig.from_headers(
                get_http_headers(include={"authorization"}),
                query_params=request.query_params,
                default_api_host_url=_request_origin(),
                resolver=self._resolver,
            )
        except (InvalidPlaneRequestConfig, RuntimeError) as exc:
            logger.info("Rejected incomplete or unsafe Plane MCP request: %s", exc)
            return None

        if token != config.api_key or not await self._api_key_validator(config):
            return None

        return AccessToken(
            token=config.api_key,
            client_id="plane-api-key-caller",
            scopes=["read", "write"],
            expires_at=int(time.time()) + 60,
            claims={
                "auth_method": "api_key_header",
                "workspace_slug": config.workspace_slug,
                "plane_api_host_url": config.api_host_url,
            },
        )
