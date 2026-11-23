"""Authentication for caller-provided Plane API credentials."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from hashlib import sha256
import logging
import socket
from time import monotonic, time

import httpx
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.dependencies import get_http_headers, get_http_request
from starlette.datastructures import MutableHeaders, QueryParams
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
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


class PlaneAuthRateLimited(Exception):
    """保留 Plane 的限流状态及建议的重试时间。"""

    def __init__(self, retry_after: str | None) -> None:
        self.retry_after = retry_after


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
        try:
            await self.app(scope, receive, send)
        except PlaneAuthRateLimited as exc:
            # 让 MCP 客户端按 Plane 的重试时间退避，避免误触发重新认证。
            response = JSONResponse(
                {"error": "rate_limited", "detail": "Plane API rate limit reached"},
                status_code=429,
                headers={"Retry-After": exc.retry_after} if exc.retry_after else None,
            )
            await response(scope, receive, send)


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
    if response.status_code == 429:
        raise PlaneAuthRateLimited(response.headers.get("Retry-After"))
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
        # 成功记录按写入顺序限量保留，键中只存密钥摘要。业务 API 仍逐次鉴权。
        self._verified: OrderedDict[tuple[str, str, bytes], float] = OrderedDict()
        self._inflight: dict[tuple[str, str, bytes], asyncio.Task[bool]] = {}

    async def _validate(self, config: PlaneRequestConfig) -> bool:
        key = (config.api_host_url, config.workspace_slug, sha256(config.api_key.encode()).digest())
        if self._verified.get(key, 0) > monotonic():
            return True

        # 并行握手或工具调用复用同一校验；一个客户端断开不应取消其他调用。
        async def probe() -> bool:
            try:
                if not await self._api_key_validator(config):
                    return False
                self._verified[key] = monotonic() + 15
                self._verified.move_to_end(key)
                if len(self._verified) > 1024:
                    self._verified.popitem(last=False)
                return True
            finally:
                self._inflight.pop(key, None)

        if key not in self._inflight:
            self._inflight[key] = asyncio.create_task(probe())
        return await asyncio.shield(self._inflight[key])

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

        if token != config.api_key or not await self._validate(config):
            return None

        return AccessToken(
            token=config.api_key,
            client_id="plane-api-key-caller",
            scopes=["read", "write"],
            expires_at=int(time()) + 60,
            claims={
                "auth_method": "api_key_header",
                "workspace_slug": config.workspace_slug,
                "plane_api_host_url": config.api_host_url,
            },
        )
