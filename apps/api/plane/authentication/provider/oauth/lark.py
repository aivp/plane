# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.authentication.adapter.base import Adapter
from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.integrations.lark.client import (
    LarkAPIClient,
    LarkAPIError,
    LarkConfigurationError,
    build_lark_authorize_url,
    ensure_lark_ready,
)
from plane.integrations.lark.identity import sync_lark_user_identity


class LarkOAuthProvider(Adapter):
    provider = "lark"

    def __init__(
        self,
        request,
        code=None,
        state=None,
        callback=None,
        is_space=False,
        callback_path=None,
        persist_user=True,
        allow_create_user=True,
    ):
        try:
            config = ensure_lark_ready()
        except LarkConfigurationError:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["LARK_NOT_CONFIGURED"],
                error_message="LARK_NOT_CONFIGURED",
            )

        super().__init__(request=request, provider=self.provider, callback=callback)
        self.code = code
        self.config = config
        self.persist_user = persist_user
        self.allow_create_user = allow_create_user
        callback_path = callback_path or ("/auth/spaces/lark/callback/" if is_space else "/auth/lark/callback/")
        self.redirect_uri = f"""{"https" if request.is_secure() else "http"}://{request.get_host()}{callback_path}"""
        self.auth_url = build_lark_authorize_url(
            client_id=config.client_id,
            redirect_uri=self.redirect_uri,
            state=state,
        )
        self.client = LarkAPIClient(config)

    def get_auth_url(self):
        return self.auth_url

    def authenticate(self):
        try:
            token_response = self.client.exchange_oauth_code(code=self.code, redirect_uri=self.redirect_uri)
            user_access_token = token_response.get("access_token") or token_response.get("user_access_token")
            if not user_access_token:
                raise LarkAPIError("Feishu OAuth response is missing user access token", payload=token_response)

            user_response = self.client.get_oauth_user_info(user_access_token)
            result = sync_lark_user_identity(
                user_response,
                source="oauth",
                token_data={**token_response, "access_token": user_access_token},
                tenant_key=token_response.get("tenant_key"),
                allow_create_user=self.allow_create_user,
            )

            user = self.save_user_data(user=result.user) if self.persist_user else result.user
            if self.callback:
                self.callback(user, result.created_user, self.request)
            return user
        except (LarkAPIError, ValueError):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["LARK_OAUTH_PROVIDER_ERROR"],
                error_message="LARK_OAUTH_PROVIDER_ERROR",
            )
