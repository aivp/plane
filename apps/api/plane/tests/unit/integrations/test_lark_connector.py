# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_lark_connector_module_entrypoint_initializes_django():
    env = os.environ.copy()
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "plane.settings.test",
            "DEBUG": "0",
            "IS_LARK_ENABLED": "0",
            "LARK_CONNECTOR_ENABLED": "0",
            "REDIS_URL": "redis://localhost:6379/",
            "SKIP_ENV_VAR": "0",
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "plane.integrations.lark.connector"],
        cwd=Path(__file__).resolve().parents[4],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Feishu connector is disabled or not configured" in result.stdout
