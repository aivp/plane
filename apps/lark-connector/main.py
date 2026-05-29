#!/usr/bin/env python
# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")

import django  # noqa: E402

django.setup()

from plane.integrations.lark.connector import run_connector  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run_connector())
