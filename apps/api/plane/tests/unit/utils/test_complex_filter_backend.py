# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest

from plane.db.models import Issue
from plane.utils.filters import ComplexFilterBackend, IssueFilterSet


class DummyIssueView:
    filterset_class = IssueFilterSet


@pytest.mark.unit
class TestComplexFilterBackend:
    def test_build_leaf_q_preserves_all_list_values_for_in_filters(self):
        label_ids = [uuid4(), uuid4()]

        q_object = ComplexFilterBackend()._build_leaf_q(
            {"label_id__in": [str(label_id) for label_id in label_ids]},
            DummyIssueView(),
            Issue.objects.none(),
        )

        assert ("label_issue__label_id__in", label_ids) in q_object.children
        assert ("label_issue__deleted_at__isnull", True) in q_object.children
