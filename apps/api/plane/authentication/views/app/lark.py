# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.http import HttpResponseRedirect
from django.views import View

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.provider.oauth.lark import LarkOAuthProvider
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.license.models import Instance
from plane.utils.path_validator import get_safe_redirect_url


class LarkOauthInitiateEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_app=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(next_path)

        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_app=True),
                next_path=next_path,
                params=exc.get_error_dict(),
            )
            return HttpResponseRedirect(url)

        try:
            state = uuid.uuid4().hex
            provider = LarkOAuthProvider(request=request, state=state)
            request.session["state"] = state
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as e:
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_app=True),
                next_path=next_path,
                params=e.get_error_dict(),
            )
            return HttpResponseRedirect(url)


class LarkCallbackEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        next_path = request.session.get("next_path")

        if state != request.session.get("state", "") or not code:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["LARK_OAUTH_PROVIDER_ERROR"],
                error_message="LARK_OAUTH_PROVIDER_ERROR",
            )
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_app=True),
                next_path=next_path,
                params=exc.get_error_dict(),
            )
            return HttpResponseRedirect(url)

        try:
            provider = LarkOAuthProvider(request=request, code=code, callback=post_user_auth_workflow)
            user = provider.authenticate()
            user_login(request=request, user=user, is_app=True)
            path = next_path if next_path else get_redirection_path(user=user)
            return HttpResponseRedirect(
                get_safe_redirect_url(base_url=base_host(request=request, is_app=True), next_path=path, params={})
            )
        except AuthenticationException as e:
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_app=True),
                next_path=next_path,
                params=e.get_error_dict(),
            )
            return HttpResponseRedirect(url)
