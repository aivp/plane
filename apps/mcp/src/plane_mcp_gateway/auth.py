"""Authentication for caller-provided Plane API credentials."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import socket
import time

import httpx
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.dependencies import get_http_headers
from starlette.datastructures import MutableHeaders
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from plane_mcp_gateway.request_config import (
    InvalidPlaneRequestConfig,
    PlaneRequestConfig,
    Resolver,
    API_KEY_HEADER,
)


logger = logging.getLogger(__name__)

ApiKeyValidator = Callable[[PlaneRequestConfig], Awaitable[bool]]


class PlaneApiKeyHeaderMiddleware:
    """Adapt the explicit Plane API key header to FastMCP bearer authentication."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope = dict(scope)
            scope["headers"] = list(scope["headers"])
            headers = MutableHeaders(scope=scope)
            api_key = headers.get(API_KEY_HEADER)
            if api_key and not headers.get("Authorization"):
                headers["Authorization"] = f"Bearer {api_key}"
        await self.app(scope, receive, send)


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
    """Turn one request's three Plane settings into a FastMCP access token."""

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
        return [Middleware(PlaneApiKeyHeaderMiddleware), *super().get_middleware()]

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            config = PlaneRequestConfig.from_headers(
                get_http_headers(include={"authorization"}),
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
