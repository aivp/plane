# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from plane.db.models import Account, Profile, User


PLACEHOLDER_EMAIL_DOMAIN = "internal.local"


@dataclass
class LarkIdentitySyncResult:
    user: User
    account: Account
    created_user: bool
    created_account: bool


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _avatar_url(raw_avatar: Any) -> str:
    if isinstance(raw_avatar, dict):
        for key in ["avatar_origin", "avatar_640", "avatar_240", "avatar_72"]:
            if raw_avatar.get(key):
                return _clean(raw_avatar.get(key))
    return _clean(raw_avatar)


def normalize_lark_user(raw_user: dict[str, Any], tenant_key: str | None = None) -> dict[str, Any]:
    raw = raw_user or {}
    avatar = raw.get("avatar") or raw.get("avatar_url") or raw.get("avatar_thumb") or raw.get("avatar_middle")
    email = _clean(raw.get("email")).lower()
    enterprise_email = _clean(raw.get("enterprise_email")).lower()
    mobile = _clean(raw.get("mobile"))
    name = _clean(raw.get("name") or raw.get("en_name") or raw.get("display_name"))
    union_id = _clean(raw.get("union_id"))
    open_id = _clean(raw.get("open_id"))
    user_id = _clean(raw.get("user_id"))
    employee_no = _clean(raw.get("employee_no"))
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}

    identity = union_id or open_id
    if not name:
        name = (email or enterprise_email or identity or "Feishu User").split("@")[0]

    return {
        "open_id": open_id,
        "union_id": union_id,
        "user_id": user_id,
        "employee_no": employee_no,
        "email": email or enterprise_email,
        "enterprise_email": enterprise_email,
        "mobile": mobile,
        "display_name": name,
        "first_name": name[:255],
        "last_name": "",
        "avatar": _avatar_url(avatar),
        "status": status,
        "tenant_key": _clean(tenant_key or raw.get("tenant_key")),
        "raw": raw,
    }


def stable_lark_identity(lark_user: dict[str, Any]) -> str:
    return _clean(lark_user.get("union_id") or lark_user.get("open_id"))


def placeholder_email(identity: str) -> str:
    return f"lark+{identity.lower()}@{PLACEHOLDER_EMAIL_DOMAIN}"


def is_placeholder_email(email: str | None) -> bool:
    value = _clean(email).lower()
    return value.startswith("lark+") and value.endswith(f"@{PLACEHOLDER_EMAIL_DOMAIN}")


def _access_token_expiry(token_data: dict[str, Any] | None) -> datetime | None:
    if not token_data:
        return None
    expires_in = token_data.get("expires_in") or token_data.get("access_token_expires_in")
    if not expires_in:
        return None
    try:
        return timezone.now() + timedelta(seconds=max(int(expires_in) - 60, 0))
    except (TypeError, ValueError):
        return None


def _refresh_token_expiry(token_data: dict[str, Any] | None) -> datetime | None:
    if not token_data:
        return None
    expires_in = token_data.get("refresh_expires_in") or token_data.get("refresh_token_expires_in")
    if not expires_in:
        return None
    try:
        return timezone.now() + timedelta(seconds=max(int(expires_in) - 60, 0))
    except (TypeError, ValueError):
        return None


def _real_email_available(email: str, *, for_user: User | None = None) -> bool:
    if not email or is_placeholder_email(email):
        return False

    queryset = User.objects.filter(email=email)
    if for_user:
        queryset = queryset.exclude(pk=for_user.pk)
    return not queryset.exists()


def _find_lark_account(identity: str, open_id: str, union_id: str) -> tuple[Account | None, bool]:
    account = Account.objects.select_for_update().filter(provider="lark", provider_account_id=identity).first()
    if account:
        return account, False

    if union_id and open_id:
        account = Account.objects.select_for_update().filter(provider="lark", provider_account_id=open_id).first()
        if account and not Account.objects.filter(provider="lark", provider_account_id=union_id).exists():
            account.provider_account_id = union_id
            account.save(update_fields=["provider_account_id", "updated_at"])
            return account, False

    return None, False


def _create_lark_user(lark_user: dict[str, Any], identity: str) -> User:
    email = lark_user.get("email") if _real_email_available(lark_user.get("email", "")) else placeholder_email(identity)
    user = User(
        email=email,
        username=uuid.uuid4().hex,
        display_name=lark_user.get("display_name") or User.get_display_name(email),
        first_name=lark_user.get("first_name", ""),
        last_name=lark_user.get("last_name", ""),
        avatar=lark_user.get("avatar", ""),
        is_password_autoset=True,
        is_email_verified=not is_placeholder_email(email),
        is_active=True,
    )
    user.set_password(uuid.uuid4().hex)
    user.save()
    Profile.objects.get_or_create(user=user)
    return user


def _maybe_merge_by_real_email(lark_user: dict[str, Any], identity: str) -> User | None:
    email = lark_user.get("email", "")
    if not email or is_placeholder_email(email):
        return None

    user = User.objects.select_for_update().filter(email=email).first()
    if not user:
        return None

    existing_lark_account = Account.objects.filter(provider="lark", user=user).exclude(provider_account_id=identity)
    if existing_lark_account.exists():
        return None

    return user


def _update_user_profile(user: User, lark_user: dict[str, Any]) -> None:
    update_fields = []

    real_email = lark_user.get("email", "")
    if real_email and is_placeholder_email(user.email) and _real_email_available(real_email, for_user=user):
        user.email = real_email
        user.is_email_verified = True
        update_fields.extend(["email", "is_email_verified"])

    for field, value in [
        ("display_name", lark_user.get("display_name", "")),
        ("first_name", lark_user.get("first_name", "")),
        ("last_name", lark_user.get("last_name", "")),
        ("avatar", lark_user.get("avatar", "")),
    ]:
        if value and getattr(user, field) != value:
            setattr(user, field, value)
            update_fields.append(field)

    if update_fields:
        update_fields.append("updated_at")
        user.save(update_fields=list(set(update_fields)))

    Profile.objects.get_or_create(user=user)


def _account_metadata(lark_user: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "open_id": lark_user.get("open_id", ""),
        "union_id": lark_user.get("union_id", ""),
        "user_id": lark_user.get("user_id", ""),
        "tenant_key": lark_user.get("tenant_key", ""),
        "email": lark_user.get("email", ""),
        "enterprise_email": lark_user.get("enterprise_email", ""),
        "mobile": lark_user.get("mobile", ""),
        "employee_no": lark_user.get("employee_no", ""),
        "display_name": lark_user.get("display_name", ""),
        "avatar": lark_user.get("avatar", ""),
        "lark_status": lark_user.get("status", {}),
        "source": source,
        "last_synced_at": timezone.now().isoformat(),
    }


@transaction.atomic
def sync_lark_user_identity(
    raw_lark_user: dict[str, Any],
    *,
    source: str,
    token_data: dict[str, Any] | None = None,
    tenant_key: str | None = None,
) -> LarkIdentitySyncResult:
    lark_user = normalize_lark_user(raw_lark_user, tenant_key=tenant_key)
    identity = stable_lark_identity(lark_user)
    if not identity:
        raise ValueError("Feishu user is missing union_id/open_id")

    account, _ = _find_lark_account(identity, lark_user.get("open_id", ""), lark_user.get("union_id", ""))
    created_user = False
    created_account = False

    if account:
        user = account.user
    else:
        user = _maybe_merge_by_real_email(lark_user, identity)
        if not user:
            user = _create_lark_user(lark_user, identity)
            created_user = True

        account = Account.objects.create(
            user=user,
            provider="lark",
            provider_account_id=identity,
            access_token="",
            refresh_token=None,
            access_token_expired_at=None,
            refresh_token_expired_at=None,
            last_connected_at=timezone.now(),
            metadata={},
        )
        created_account = True

    _update_user_profile(user, lark_user)

    account.metadata = {**(account.metadata or {}), **_account_metadata(lark_user, source)}
    account.last_connected_at = timezone.now()
    if token_data:
        account.access_token = token_data.get("access_token") or token_data.get("user_access_token") or ""
        account.refresh_token = token_data.get("refresh_token") or account.refresh_token
        account.access_token_expired_at = _access_token_expiry(token_data)
        account.refresh_token_expired_at = _refresh_token_expiry(token_data)

    account.save(
        update_fields=[
            "access_token",
            "refresh_token",
            "access_token_expired_at",
            "refresh_token_expired_at",
            "last_connected_at",
            "metadata",
            "updated_at",
        ]
    )

    return LarkIdentitySyncResult(
        user=user,
        account=account,
        created_user=created_user,
        created_account=created_account,
    )
