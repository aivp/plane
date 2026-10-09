# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""验证独立 Worker 注册日志任务，并将 API 调用日志写入数据库。"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_worker_registers_api_log_task():
    # 独立进程避免 API 中间件或其他测试提前导入任务，掩盖 Worker 启动问题。
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from plane.celery import app; "
            "app.loader.init_worker(); "
            "assert 'plane.bgtasks.logger_task.process_logs' in app.tasks",
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.unit
@pytest.mark.django_db
def test_process_logs_persists_api_activity_log():
    from plane.bgtasks.logger_task import process_logs
    from plane.db.models import APIActivityLog

    log_data = {
        "token_identifier": "hashed-token",
        "path": "/api/v1/workspaces/",
        "method": "GET",
        "response_code": 200,
    }

    result = process_logs.apply(kwargs={"log_data": log_data})

    assert result.successful(), result.result
    assert APIActivityLog.objects.filter(**log_data).count() == 1
