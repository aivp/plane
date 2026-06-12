# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
import signal
import threading
import time
from typing import Any

import lark_oapi as lark


LOCK_KEY = "integrations:lark:connector:lock"
HEARTBEAT_KEY = "integrations:lark:connector:heartbeat"
LOCK_TTL_SECONDS = 45
EVENT_TYPES = [
    "im.message.receive_v1",
    "contact.user.created_v3",
    "contact.user.updated_v3",
    "contact.user.deleted_v3",
    "contact.department.created_v3",
    "contact.department.updated_v3",
    "contact.department.deleted_v3",
]

stop_event = threading.Event()


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if hasattr(value, "__dict__"):
        return {
            key: _to_plain(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_") and item is not None
        }
    return str(value)


def _event_id(event) -> str:
    from django.utils import timezone

    header = getattr(event, "header", None)
    if header and getattr(header, "event_id", None):
        return str(header.event_id)
    if getattr(event, "uuid", None):
        return str(event.uuid)
    return f"{getattr(event, 'type', 'unknown')}:{timezone.now().timestamp()}"


def _event_type(event) -> str:
    header = getattr(event, "header", None)
    if header and getattr(header, "event_type", None):
        return str(header.event_type)
    return str(getattr(event, "type", "unknown"))


def _tenant_key(event) -> str:
    header = getattr(event, "header", None)
    if header and getattr(header, "tenant_key", None):
        return str(header.tenant_key)
    return ""


def persist_event(event) -> None:
    from django.db import IntegrityError

    from plane.bgtasks.lark_task import lark_process_events
    from plane.db.models import LarkEvent

    try:
        LarkEvent.objects.create(
            event_id=_event_id(event),
            event_type=_event_type(event),
            tenant_key=_tenant_key(event),
            payload=_to_plain(event),
        )
        lark_process_events.delay()
    except IntegrityError:
        return


def _heartbeat(lock_value: str) -> None:
    from django.core.cache import cache
    from django.utils import timezone

    from plane.settings.redis import redis_instance

    redis_client = redis_instance()
    while not stop_event.wait(15):
        current_lock = redis_client.get(LOCK_KEY)
        if current_lock and current_lock.decode() != lock_value:
            stop_event.set()
            return
        redis_client.expire(LOCK_KEY, LOCK_TTL_SECONDS)
        cache.set(HEARTBEAT_KEY, timezone.now().isoformat(), timeout=LOCK_TTL_SECONDS)


def _build_handler():
    builder = lark.EventDispatcherHandler.builder("", "")
    for event_type in EVENT_TYPES:
        builder.register_p2_customized_event(event_type, persist_event)
    return builder.build()


def _shutdown(*_args):
    stop_event.set()


def run_connector() -> int:
    setup_django()

    from django.core.cache import cache
    from django.utils import timezone

    from plane.integrations.lark.client import FEISHU_BASE_DOMAIN, get_lark_configuration
    from plane.settings.redis import redis_instance

    config = get_lark_configuration()
    if not (config.is_enabled and config.connector_enabled and config.is_configured):
        print("Feishu connector is disabled or not configured", flush=True)
        return 0
    if config.base_domain != FEISHU_BASE_DOMAIN:
        print("Only feishu.cn is supported", flush=True)
        return 1

    redis_client = redis_instance()
    lock_value = f"{os.getpid()}:{time.time()}"
    lock_acquired = redis_client.set(LOCK_KEY, lock_value, nx=True, ex=LOCK_TTL_SECONDS)
    if not lock_acquired:
        print("Another Feishu connector is already running", flush=True)
        while not stop_event.wait(30):
            cache.set(HEARTBEAT_KEY, timezone.now().isoformat(), timeout=LOCK_TTL_SECONDS)
        return 0

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    heartbeat_thread = threading.Thread(target=_heartbeat, args=(lock_value,), daemon=True)
    heartbeat_thread.start()

    try:
        client = lark.ws.Client(
            app_id=config.client_id,
            app_secret=config.client_secret,
            event_handler=_build_handler(),
            domain=lark.FEISHU_DOMAIN,
            log_level=lark.LogLevel.INFO,
            auto_reconnect=True,
        )
        client.start()
    finally:
        current_lock = redis_client.get(LOCK_KEY)
        if current_lock and current_lock.decode() == lock_value:
            redis_client.delete(LOCK_KEY)
        cache.delete(HEARTBEAT_KEY)
        stop_event.set()

    return 0


if __name__ == "__main__":
    raise SystemExit(run_connector())
