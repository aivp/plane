# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import requests
from django.core.cache import cache

from plane.license.utils.instance_value import get_configuration_value


FEISHU_BASE_DOMAIN = "feishu.cn"
FEISHU_OPEN_API_BASE = "https://open.feishu.cn/open-apis"
FEISHU_ACCOUNT_BASE = "https://accounts.feishu.cn"
TENANT_TOKEN_CACHE_KEY = "integrations:lark:tenant_access_token"


class LarkConfigurationError(Exception):
    """Raised when the Feishu integration is not ready to make API calls."""


class LarkAPIError(Exception):
    def __init__(self, message: str, code: int | str | None = None, payload: dict[str, Any] | None = None):
        self.code = code
        self.payload = payload or {}
        super().__init__(message)


@dataclass(frozen=True)
class LarkConfiguration:
    is_enabled: bool
    client_id: str
    client_secret: str
    base_domain: str
    default_workspace_slug: str
    default_workspace_role: int
    auto_sync_enabled: bool
    offboarding_policy: str
    notifications_enabled: bool
    connector_enabled: bool
    public_base_url: str

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def _as_bool(value: Any) -> bool:
    return str(value or "0").strip() == "1"


def _as_role(value: Any) -> int:
    try:
        role = int(value)
    except (TypeError, ValueError):
        return 15
    return role if role in [5, 15, 20] else 15


def get_lark_configuration() -> LarkConfiguration:
    (
        IS_LARK_ENABLED,
        LARK_CLIENT_ID,
        LARK_CLIENT_SECRET,
        LARK_BASE_DOMAIN,
        LARK_DEFAULT_WORKSPACE_SLUG,
        LARK_DEFAULT_WORKSPACE_ROLE,
        LARK_AUTO_SYNC_ENABLED,
        LARK_OFFBOARDING_POLICY,
        LARK_NOTIFICATIONS_ENABLED,
        LARK_CONNECTOR_ENABLED,
        PLANE_PUBLIC_BASE_URL,
    ) = get_configuration_value(
        [
            {"key": "IS_LARK_ENABLED", "default": os.environ.get("IS_LARK_ENABLED", "0")},
            {"key": "LARK_CLIENT_ID", "default": os.environ.get("LARK_CLIENT_ID", "")},
            {"key": "LARK_CLIENT_SECRET", "default": os.environ.get("LARK_CLIENT_SECRET", "")},
            {"key": "LARK_BASE_DOMAIN", "default": FEISHU_BASE_DOMAIN},
            {
                "key": "LARK_DEFAULT_WORKSPACE_SLUG",
                "default": os.environ.get("LARK_DEFAULT_WORKSPACE_SLUG", ""),
            },
            {"key": "LARK_DEFAULT_WORKSPACE_ROLE", "default": os.environ.get("LARK_DEFAULT_WORKSPACE_ROLE", "15")},
            {"key": "LARK_AUTO_SYNC_ENABLED", "default": os.environ.get("LARK_AUTO_SYNC_ENABLED", "0")},
            {
                "key": "LARK_OFFBOARDING_POLICY",
                "default": os.environ.get("LARK_OFFBOARDING_POLICY", "deactivate_workspace_member"),
            },
            {"key": "LARK_NOTIFICATIONS_ENABLED", "default": os.environ.get("LARK_NOTIFICATIONS_ENABLED", "0")},
            {"key": "LARK_CONNECTOR_ENABLED", "default": os.environ.get("LARK_CONNECTOR_ENABLED", "0")},
            {"key": "PLANE_PUBLIC_BASE_URL", "default": os.environ.get("PLANE_PUBLIC_BASE_URL", "")},
        ]
    )

    base_domain = str(LARK_BASE_DOMAIN or FEISHU_BASE_DOMAIN).strip().lower()
    if base_domain != FEISHU_BASE_DOMAIN:
        base_domain = FEISHU_BASE_DOMAIN

    return LarkConfiguration(
        is_enabled=_as_bool(IS_LARK_ENABLED),
        client_id=str(LARK_CLIENT_ID or "").strip(),
        client_secret=str(LARK_CLIENT_SECRET or "").strip(),
        base_domain=base_domain,
        default_workspace_slug=str(LARK_DEFAULT_WORKSPACE_SLUG or "").strip(),
        default_workspace_role=_as_role(LARK_DEFAULT_WORKSPACE_ROLE),
        auto_sync_enabled=_as_bool(LARK_AUTO_SYNC_ENABLED),
        offboarding_policy=str(LARK_OFFBOARDING_POLICY or "deactivate_workspace_member").strip(),
        notifications_enabled=_as_bool(LARK_NOTIFICATIONS_ENABLED),
        connector_enabled=_as_bool(LARK_CONNECTOR_ENABLED),
        public_base_url=str(PLANE_PUBLIC_BASE_URL or "").strip(),
    )


def ensure_lark_ready() -> LarkConfiguration:
    config = get_lark_configuration()
    if not config.is_enabled:
        raise LarkConfigurationError("Feishu integration is disabled")
    if not config.is_configured:
        raise LarkConfigurationError("Feishu integration is missing app credentials")
    return config


def build_lark_authorize_url(client_id: str, redirect_uri: str, state: str | None = None) -> str:
    params = {
        "app_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    if state:
        params["state"] = state
    return f"{FEISHU_ACCOUNT_BASE}/open-apis/authen/v1/authorize?{urlencode(params)}"


class LarkAPIClient:
    def __init__(self, config: LarkConfiguration | None = None):
        self.config = config or ensure_lark_ready()

    def _parse_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LarkAPIError("Feishu returned a non-JSON response", payload={"status_code": response.status_code}) from exc

        if response.status_code >= 400:
            raise LarkAPIError(
                payload.get("msg") or payload.get("message") or "Feishu request failed",
                code=payload.get("code"),
                payload=payload,
            )

        if isinstance(payload, dict) and payload.get("code", 0) != 0:
            raise LarkAPIError(
                payload.get("msg") or payload.get("message") or "Feishu request failed",
                code=payload.get("code"),
                payload=payload,
            )

        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        use_tenant_token: bool = True,
        timeout: int = 15,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if use_tenant_token:
            headers["Authorization"] = f"Bearer {self.get_tenant_access_token()}"

        response = requests.request(
            method,
            f"{FEISHU_OPEN_API_BASE}{path}",
            params=params,
            json=json_body,
            headers=headers,
            timeout=timeout,
        )
        payload = self._parse_response(response)
        return payload.get("data", payload)

    def exchange_oauth_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        response = requests.post(
            f"{FEISHU_OPEN_API_BASE}/authen/v2/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
        payload = self._parse_response(response)
        return payload.get("data", payload)

    def get_oauth_user_info(self, user_access_token: str) -> dict[str, Any]:
        response = requests.get(
            f"{FEISHU_OPEN_API_BASE}/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_access_token}"},
            timeout=15,
        )
        payload = self._parse_response(response)
        return payload.get("data", payload)

    def get_tenant_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached_token = cache.get(TENANT_TOKEN_CACHE_KEY)
            if cached_token:
                return str(cached_token)

        response = requests.post(
            f"{FEISHU_OPEN_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.config.client_id, "app_secret": self.config.client_secret},
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
        payload = self._parse_response(response)
        token = payload.get("tenant_access_token")
        if not token:
            raise LarkAPIError("Feishu tenant_access_token is missing", payload=payload)

        expires_in = int(payload.get("expire", 7200))
        cache.set(TENANT_TOKEN_CACHE_KEY, token, timeout=max(expires_in - 300, 60))
        return str(token)

    def list_contact_scopes(self) -> dict[str, Any]:
        return self._request("GET", "/contact/v3/scopes")

    def list_department_children(
        self,
        department_id: str,
        *,
        page_token: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "department_id_type": "open_department_id",
            "page_size": page_size,
        }
        if page_token:
            params["page_token"] = page_token
        return self._request("GET", f"/contact/v3/departments/{quote(department_id)}/children", params=params)

    def list_department_users(
        self,
        department_id: str,
        *,
        page_token: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "department_id": department_id,
            "department_id_type": "open_department_id",
            "user_id_type": "open_id",
            "page_size": page_size,
        }
        if page_token:
            params["page_token"] = page_token
        return self._request("GET", "/contact/v3/users/find_by_department", params=params)

    def get_user(self, user_id: str, *, user_id_type: str = "open_id") -> dict[str, Any]:
        params = {
            "user_id_type": user_id_type,
            "department_id_type": "open_department_id",
        }
        return self._request("GET", f"/contact/v3/users/{quote(user_id)}", params=params).get("user", {})

    def send_message(
        self,
        *,
        receive_id: str,
        receive_id_type: str,
        msg_type: str,
        content: dict[str, Any] | str,
    ) -> dict[str, Any]:
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)

        return self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json_body={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": content,
            },
        )
