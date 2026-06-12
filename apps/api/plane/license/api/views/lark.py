# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

from plane.integrations.lark.client import FEISHU_BASE_DOMAIN, LarkAPIClient, LarkAPIError, get_lark_configuration
from plane.license.api.views.base import BaseAPIView


class InstanceLarkStatusEndpoint(BaseAPIView):
    def get(self, request):
        config = get_lark_configuration()
        request_base_url = f"""{"https" if request.is_secure() else "http"}://{request.get_host()}"""
        connector_heartbeat = cache.get("integrations:lark:connector:heartbeat")

        return Response(
            {
                "enabled": config.is_enabled,
                "configured": config.is_configured,
                "domain": FEISHU_BASE_DOMAIN,
                "client_id_configured": bool(config.client_id),
                "client_secret_configured": bool(config.client_secret),
                "auto_sync_enabled": config.auto_sync_enabled,
                "notifications_enabled": config.notifications_enabled,
                "connector_enabled": config.connector_enabled,
                "default_workspace_slug": config.default_workspace_slug,
                "default_workspace_role": config.default_workspace_role,
                "oauth_callback_urls": {
                    "app": f"{request_base_url}/auth/lark/callback/",
                    "space": f"{request_base_url}/auth/spaces/lark/callback/",
                    "admin": f"{request_base_url}/api/instances/admins/lark/callback/",
                },
                "connector": {
                    "healthy": bool(connector_heartbeat),
                    "last_heartbeat": connector_heartbeat,
                },
            },
            status=status.HTTP_200_OK,
        )


class InstanceLarkTestConnectionEndpoint(BaseAPIView):
    def post(self, request):
        config = get_lark_configuration()
        if not config.is_configured:
            return Response({"error": "Feishu app credentials are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = LarkAPIClient(config)
            client.get_tenant_access_token(force_refresh=True)
            scopes = client.list_contact_scopes()
            return Response(
                {
                    "connected": True,
                    "domain": FEISHU_BASE_DOMAIN,
                    "scope_summary": {
                        "department_count": len(scopes.get("department_ids", []) or []),
                        "user_count": len(scopes.get("user_ids", []) or []),
                    },
                },
                status=status.HTTP_200_OK,
            )
        except LarkAPIError as exc:
            return Response(
                {"connected": False, "error": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )


class InstanceLarkTestMessageEndpoint(BaseAPIView):
    def post(self, request):
        receive_id = request.data.get("receive_id")
        receive_id_type = request.data.get("receive_id_type", "union_id")
        if not receive_id:
            return Response({"error": "receive_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if receive_id_type not in ["open_id", "union_id", "user_id", "email", "chat_id"]:
            return Response({"error": "receive_id_type is invalid"}, status=status.HTTP_400_BAD_REQUEST)

        config = get_lark_configuration()
        if not config.is_configured:
            return Response({"error": "Feishu integration is not configured"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            response = LarkAPIClient(config).send_message(
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                msg_type="text",
                content={"text": request.data.get("text") or "Plane Feishu integration test message"},
            )
            return Response({"sent": True, "response": response}, status=status.HTTP_200_OK)
        except LarkAPIError as exc:
            return Response(
                {"sent": False, "error": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
