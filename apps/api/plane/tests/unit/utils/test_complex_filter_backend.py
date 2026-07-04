# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueLabel, Label, Project, State
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

    @pytest.mark.django_db
    def test_label_all_filter_requires_every_label_and_ignores_soft_deleted_relations(self, workspace):
        project = Project.objects.create(name="Filter project", identifier="FLT", workspace=workspace)
        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
        )
        other_state = State.objects.create(
            name="Done",
            color="#46A758",
            group="completed",
            project=project,
        )

        label_a = Label.objects.create(name="Label A", color="#ff0000", project=project)
        label_b = Label.objects.create(name="Label B", color="#00ff00", project=project)

        matching_issue = Issue.objects.create(name="Has both labels", project=project, state=state)
        partial_issue = Issue.objects.create(name="Has one label", project=project, state=state)
        soft_deleted_relation_issue = Issue.objects.create(name="Soft deleted label", project=project, state=state)
        other_state_issue = Issue.objects.create(
            name="Has both labels in another state",
            project=project,
            state=other_state,
        )

        IssueLabel.objects.create(project=project, issue=matching_issue, label=label_a)
        IssueLabel.objects.create(project=project, issue=matching_issue, label=label_b)
        IssueLabel.objects.create(project=project, issue=partial_issue, label=label_a)
        IssueLabel.objects.create(project=project, issue=soft_deleted_relation_issue, label=label_a)
        IssueLabel.objects.create(
            project=project,
            issue=soft_deleted_relation_issue,
            label=label_b,
            deleted_at=timezone.now(),
        )
        IssueLabel.objects.create(project=project, issue=other_state_issue, label=label_a)
        IssueLabel.objects.create(project=project, issue=other_state_issue, label=label_b)

        queryset = ComplexFilterBackend().filter_queryset(
            request=None,
            queryset=Issue.issue_objects.filter(project=project),
            view=DummyIssueView(),
            filter_data={
                "and": [
                    {"label_id__all": [str(label_a.id), str(label_b.id)]},
                    {"state_id__exact": str(state.id)},
                ]
            },
        )

        assert list(queryset.values_list("id", flat=True)) == [matching_issue.id]

    @pytest.mark.django_db
    def test_label_in_filter_keeps_any_label_semantics(self, workspace):
        project = Project.objects.create(name="Any label project", identifier="ANY", workspace=workspace)
        state = State.objects.create(
            name="Todo",
            color="#60646C",
            group="unstarted",
            default=True,
            project=project,
        )
        label_a = Label.objects.create(name="Label A", color="#ff0000", project=project)
        label_b = Label.objects.create(name="Label B", color="#00ff00", project=project)

        issue_a = Issue.objects.create(name="Has label A", project=project, state=state)
        issue_b = Issue.objects.create(name="Has label B", project=project, state=state)
        issue_without_labels = Issue.objects.create(name="No labels", project=project, state=state)

        IssueLabel.objects.create(project=project, issue=issue_a, label=label_a)
        IssueLabel.objects.create(project=project, issue=issue_b, label=label_b)

        queryset = ComplexFilterBackend().filter_queryset(
            request=None,
            queryset=Issue.issue_objects.filter(project=project),
            view=DummyIssueView(),
            filter_data={"label_id__in": [str(label_a.id), str(label_b.id)]},
        )

        issue_ids = set(queryset.values_list("id", flat=True))

        assert issue_ids == {issue_a.id, issue_b.id}
        assert issue_without_labels.id not in issue_ids
