# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from plane.db.models import User
from plane.license.models import Instance, InstanceAdmin


@pytest.fixture
def setup_instance(db):
    instance, _ = Instance.objects.update_or_create(
        instance_id="test-instance",
        defaults={
            "instance_name": "Test Instance",
            "current_version": "1.0.0",
            "domain": "http://testserver",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )
    return instance


@pytest.fixture
def django_client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0")


@pytest.fixture(autouse=True)
def configure_base_urls(settings):
    settings.WEB_URL = "http://testserver"
    settings.APP_BASE_URL = "http://testserver"
    settings.ADMIN_BASE_URL = None
    settings.ADMIN_BASE_PATH = "/god-mode/"


def _lark_config():
    return SimpleNamespace(
        client_id="cli_test",
        client_secret="secret",
        is_enabled=True,
        is_configured=True,
    )


def _set_admin_session(client, **values):
    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore()
    for key, value in values.items():
        session[key] = value
    session.save()
    client.cookies[settings.ADMIN_SESSION_COOKIE_NAME] = session.session_key
    return session.session_key


def _get_session(session_key):
    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore(session_key=session_key)


@pytest.mark.contract
class TestInstanceAdminLarkOAuth:
    @pytest.mark.django_db
    @patch("plane.authentication.provider.oauth.lark.ensure_lark_ready")
    def test_initiate_uses_admin_callback_url(self, mock_ensure_lark_ready, django_client, setup_instance):
        mock_ensure_lark_ready.return_value = _lark_config()

        response = django_client.get(reverse("instance-admin-lark-initiate"), follow=False)

        assert response.status_code == 302
        location = urlparse(response.url)
        query = parse_qs(location.query)
        assert location.netloc == "accounts.feishu.cn"
        assert query["redirect_uri"] == ["http://testserver/api/instances/admins/lark/callback/"]
        assert settings.ADMIN_SESSION_COOKIE_NAME in response.cookies

    @pytest.mark.django_db
    @patch("plane.license.api.views.admin.LarkOAuthProvider")
    def test_callback_logs_in_registered_instance_admin(self, mock_provider, django_client, setup_instance):
        user = User.objects.create(email="admin@plane.so", username=uuid.uuid4().hex, is_active=True)
        InstanceAdmin.objects.create(instance=setup_instance, user=user)
        _set_admin_session(django_client, admin_lark_oauth_state="state")
        mock_provider.return_value.authenticate.return_value = user

        response = django_client.get(
            reverse("instance-admin-lark-callback"),
            {"code": "code", "state": "state"},
            follow=False,
        )

        assert response.status_code == 302
        assert response.url == "http://testserver/god-mode/general/"
        assert mock_provider.call_args.kwargs["callback_path"] == "/api/instances/admins/lark/callback/"
        assert mock_provider.call_args.kwargs["persist_user"] is False
        assert mock_provider.call_args.kwargs["allow_create_user"] is False

        session_key = response.cookies[settings.ADMIN_SESSION_COOKIE_NAME].value
        session = _get_session(session_key)
        assert session.get("_auth_user_id") == str(user.pk)

    @pytest.mark.django_db
    @patch("plane.license.api.views.admin.LarkOAuthProvider")
    def test_callback_rejects_non_admin_user(self, mock_provider, django_client, setup_instance):
        user = User.objects.create(email="member@plane.so", username=uuid.uuid4().hex, is_active=True)
        _set_admin_session(django_client, admin_lark_oauth_state="state")
        mock_provider.return_value.authenticate.return_value = user

        response = django_client.get(
            reverse("instance-admin-lark-callback"),
            {"code": "code", "state": "state"},
            follow=False,
        )

        assert response.status_code == 302
        assert "error_code=5175" in response.url

        session_key = response.cookies[settings.ADMIN_SESSION_COOKIE_NAME].value
        session = _get_session(session_key)
        assert session.get("_auth_user_id") is None
