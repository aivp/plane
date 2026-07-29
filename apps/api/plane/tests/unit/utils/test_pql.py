# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest
from django.db.models import Q

from plane.utils.pql import OPEN_STATE_GROUPS, PQLParseError, compile_work_item_pql


USER_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))


@pytest.mark.unit
class TestWorkItemPQLCompiler:
    def test_compiles_mcp_current_user_open_states_query(self):
        result = compile_work_item_pql(
            "assignee = currentUser() AND stateGroup IN openStates()",
            USER_ID,
        )

        assert result == (
            Q(issue_assignee__assignee_id=USER_ID)
            & Q(issue_assignee__deleted_at__isnull=True)
            & Q(state__group__in=list(OPEN_STATE_GROUPS))
        )

    def test_preserves_not_and_or_precedence(self):
        result = compile_work_item_pql(
            'priority = "urgent" OR priority = "high" AND NOT title ~ "deferred"',
            USER_ID,
        )

        assert result == (Q(priority="urgent") | (Q(priority="high") & ~Q(name__icontains="deferred")))

    def test_compiles_date_between_functions(self):
        result = compile_work_item_pql(
            "dueDate BETWEEN (daysAgo(7), today())",
            USER_ID,
        )

        assert result.children[0][0] == "target_date__gte"
        assert result.children[1][0] == "target_date__lte"

    def test_empty_relation_predicate_ignores_soft_deleted_assignments(self):
        assert compile_work_item_pql("hasNoAssignee()", USER_ID) == ~Q(issue_assignee__deleted_at__isnull=True)

    @pytest.mark.parametrize(
        "query, message",
        [
            ('created_by__password = "secret"', "Unsupported PQL field"),
            ('assignee = "not-a-uuid"', "Invalid UUID"),
            ("unknownFunction()", "Unsupported PQL predicate"),
            ('priority ~ "high"', "~ operator is only supported"),
            ('priority = "critical"', "Priority must be one of"),
        ],
    )
    def test_rejects_unsupported_or_unsafe_queries(self, query, message):
        with pytest.raises(PQLParseError, match=message):
            compile_work_item_pql(query, USER_ID)

    def test_rejects_more_than_five_conditions(self):
        query = (
            'priority = "high" OR priority = "urgent" OR priority = "medium" '
            'OR priority = "low" OR priority = "none" OR title ~ "overflow"'
        )

        with pytest.raises(PQLParseError, match="at most 5 conditions"):
            compile_work_item_pql(query, USER_ID)
