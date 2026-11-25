# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock

import pytest
from django.utils import timezone

from plane.bgtasks.issue_activities_task import issue_activity
from plane.bgtasks.notification_task import notifications
from plane.db.models import (
    Issue,
    IssueSubscriber,
    Notification,
    ProjectMember,
    State,
    UserNotificationPreference,
    WorkspaceMember,
)
from plane.tests.factories import ProjectFactory, UserFactory

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@pytest.fixture
def project(workspace, create_user):
    project = ProjectFactory(workspace=workspace, identifier="SUB")
    ProjectMember.objects.create(project=project, member=create_user, role=15)
    return project


@pytest.fixture
def issue(project, create_user):
    state = State.objects.create(project=project, name="Ready", color="#333333")
    issue = Issue(project=project, name="Review the release", state=state)
    issue.save(created_by_id=create_user.id)
    return issue


@pytest.fixture
def issue_url(issue):
    return f"/api/workspaces/{issue.workspace.slug}/projects/{issue.project_id}/issues/{issue.id}/"


@pytest.fixture
def member(project, workspace):
    user = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(project=project, member=user, role=15)
    return user


@pytest.fixture
def inline_activity_notifications(monkeypatch):
    # Run the activity and notification workers inline so delivery is observable in the test transaction.
    monkeypatch.setattr(issue_activity, "delay", issue_activity.run)
    monkeypatch.setattr(notifications, "delay", notifications.run)
    monkeypatch.setattr("plane.app.views.issue.base.model_activity.delay", Mock())
    monkeypatch.setattr("plane.app.views.issue.base.issue_description_version_task.delay", Mock())


def post_comment(client, issue_url):
    response = client.post(f"{issue_url}comments/", {"comment_html": "<p>Review</p>"}, format="json")
    assert response.status_code == 201, response.data


def test_self_subscription_and_managed_list_share_membership(session_client, issue_url, member, create_user):
    session_client.force_authenticate(user=member)
    candidates = session_client.get(f"{issue_url}issue-subscribers/").json()
    assert {candidate["member"]["id"] for candidate in candidates} == {str(member.id), str(create_user.id)}
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == []

    subscriber_id = str(create_user.id)
    url = f"{issue_url}issue-subscribers/"
    assert session_client.post(url, {"subscriber": subscriber_id}, format="json").status_code == 201
    assert session_client.post(url, {"subscriber": subscriber_id}, format="json").status_code == 200
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == [subscriber_id]

    session_client.force_authenticate(user=create_user)
    assert session_client.get(f"{issue_url}subscribe/").json() == {"subscribed": True}
    assert session_client.delete(f"{issue_url}subscribe/").status_code == 204
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == []
    assert session_client.post(f"{issue_url}subscribe/").status_code == 201

    session_client.force_authenticate(user=member)
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == [subscriber_id]
    assert session_client.delete(f"{url}{subscriber_id}/").status_code == 204
    assert session_client.delete(f"{url}{subscriber_id}/").status_code == 204


@pytest.mark.parametrize("target", ["guest", "inactive_project_member", "inactive_workspace_member", "other_project"])
def test_only_active_members_of_this_project_can_be_added(target, session_client, issue_url, project, member):
    membership = ProjectMember.objects.get(project=project, member=member)
    if target == "guest":
        project.guest_view_all_features = True
        project.save(update_fields=["guest_view_all_features"])
        membership.role = 5
        membership.save(update_fields=["role"])
    elif target == "inactive_project_member":
        membership.is_active = False
        membership.save(update_fields=["is_active"])
    elif target == "inactive_workspace_member":
        WorkspaceMember.objects.filter(workspace=project.workspace, member=member).update(is_active=False)
    else:
        membership.project = ProjectFactory(workspace=project.workspace, identifier="OTHER")
        membership.save(update_fields=["project"])

    response = session_client.post(f"{issue_url}issue-subscribers/", {"subscriber": str(member.id)}, format="json")
    assert response.status_code == 400
    assert not IssueSubscriber.objects.filter(subscriber=member).exists()


def test_guest_can_view_subscribers_only_when_they_can_view_the_issue(
    session_client, issue, issue_url, project, member, create_user
):
    ProjectMember.objects.filter(member=member, project=project).update(role=5)
    IssueSubscriber.objects.create(project=project, issue=issue, subscriber=create_user)
    session_client.force_authenticate(user=member)
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").status_code == 403

    project.guest_view_all_features = True
    project.save(update_fields=["guest_view_all_features"])
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == [str(create_user.id)]
    url = f"{issue_url}issue-subscribers/"
    assert session_client.post(url, {"subscriber": str(create_user.id)}, format="json").status_code == 403
    assert session_client.delete(f"{url}{create_user.id}/").status_code == 403
    assert IssueSubscriber.objects.filter(issue=issue, subscriber=create_user).exists()


@pytest.mark.parametrize("scope", ["archived_issue", "archived_project", "draft", "triage", "different_project"])
def test_managing_subscribers_requires_an_editable_issue_in_the_project(
    scope, session_client, issue_url, issue, project, member, create_user
):
    if scope == "archived_issue":
        Issue.objects.filter(pk=issue.pk).update(archived_at=timezone.localdate())
    elif scope == "archived_project":
        project.archived_at = timezone.now()
        project.save(update_fields=["archived_at"])
    elif scope == "draft":
        Issue.objects.filter(pk=issue.pk).update(is_draft=True)
    elif scope == "triage":
        State.objects.filter(pk=issue.state_id).update(group="triage", is_triage=True)
    else:
        other = ProjectFactory(workspace=issue.workspace, identifier="OTHER")
        ProjectMember.objects.create(project=other, member=create_user, role=20)
        ProjectMember.objects.create(project=other, member=member, role=15)
        issue_url = f"/api/workspaces/{issue.workspace.slug}/projects/{other.id}/issues/{issue.id}/"

    IssueSubscriber.objects.create(issue=issue, project=project, subscriber=create_user)
    if scope == "archived_issue":
        assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == [str(create_user.id)]
    url = f"{issue_url}issue-subscribers/"
    assert session_client.post(url, {"subscriber": str(member.id)}, format="json").status_code == 404
    assert session_client.delete(f"{url}{create_user.id}/").status_code == 404
    assert IssueSubscriber.objects.filter(issue=issue, subscriber=create_user).exists()
    assert not IssueSubscriber.objects.filter(issue=issue, subscriber=member).exists()


def test_member_receives_future_activity_until_removed(
    session_client, issue_url, issue, member, inline_activity_notifications
):
    initial = issue.state
    started = State.objects.create(project=issue.project, name="In progress", group="started", color="#555555")
    received = Notification.objects.filter(receiver=member, entity_identifier=issue.id)
    url = f"{issue_url}issue-subscribers/"
    assert session_client.post(url, {"subscriber": str(member.id)}, format="json").status_code == 201
    assert not received.exists()

    def comment_and_change_state(state):
        post_comment(session_client, issue_url)
        update = session_client.patch(issue_url, {"state_id": str(state.id)}, format="json")
        assert update.status_code == 204, update.data

    comment_and_change_state(started)
    assert sorted(received.values_list("data__issue_activity__field", flat=True)) == ["comment", "state"]
    assert session_client.delete(f"{url}{member.id}/").status_code == 204
    comment_and_change_state(initial)
    assert received.count() == 2


@pytest.mark.parametrize("access_change", ["restricted_guest", "inactive_workspace_member"])
def test_subscriber_who_loses_issue_access_stops_receiving_comments(
    access_change, session_client, issue_url, issue, member, inline_activity_notifications
):
    member_id = str(member.id)
    response = session_client.post(f"{issue_url}issue-subscribers/", {"subscriber": member_id}, format="json")
    assert response.status_code == 201
    assert session_client.get(f"{issue_url}issue-subscriber-ids/").json() == [member_id]

    received = Notification.objects.filter(receiver=member, entity_identifier=issue.id)
    post_comment(session_client, issue_url)
    assert received.count() == 1

    if access_change == "restricted_guest":
        ProjectMember.objects.filter(project=issue.project, member=member).update(role=5)
    else:
        WorkspaceMember.objects.filter(workspace=issue.workspace, member=member).update(is_active=False)

    assert member_id not in session_client.get(f"{issue_url}issue-subscriber-ids/").json()
    post_comment(session_client, issue_url)
    assert received.count() == 1


@pytest.mark.parametrize("bot_notifications_enabled", [True, False])
def test_existing_bot_subscription_keeps_its_delivery_and_does_not_block_other_subscribers(
    bot_notifications_enabled, session_client, issue_url, issue, member, create_bot_user, inline_activity_notifications
):
    bot = create_bot_user
    ProjectMember.objects.create(project=issue.project, member=bot, role=15)
    WorkspaceMember.objects.create(workspace=issue.workspace, member=bot, role=15)
    if bot_notifications_enabled:
        UserNotificationPreference.objects.create(user=bot)
    IssueSubscriber.objects.create(project=issue.project, issue=issue, subscriber=bot)

    project_members = session_client.get(f"/api/workspaces/{issue.workspace.slug}/projects/{issue.project_id}/members/")
    assert project_members.status_code == 200
    assert str(bot.id) not in {row["member"] for row in project_members.json()}
    assert str(bot.id) not in session_client.get(f"{issue_url}issue-subscriber-ids/").json()
    add = session_client.post(f"{issue_url}issue-subscribers/", {"subscriber": str(bot.id)}, format="json")
    assert add.status_code == 400
    assert session_client.delete(f"{issue_url}issue-subscribers/{bot.id}/").status_code == 204
    assert session_client.post(f"{issue_url}issue-subscribers/", {"subscriber": str(member.id)}).status_code == 201
    post_comment(session_client, issue_url)
    received = Notification.objects.filter(entity_identifier=issue.id, data__issue_activity__field="comment")
    assert received.filter(receiver=bot).exists() == bot_notifications_enabled
    assert received.filter(receiver=member).count() == 1
