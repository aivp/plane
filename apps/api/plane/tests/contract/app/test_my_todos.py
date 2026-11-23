import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, Project, ProjectMember, State, WorkspaceMember
from plane.tests.factories import UserFactory


@pytest.mark.contract
@pytest.mark.django_db
def test_my_todos_follow_the_session_and_project_permissions(api_client, workspace, create_user):
    # 同一入口分别由两位成员打开，并覆盖私有项目及受限访客的情况。
    other = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)

    def project(identifier):
        return Project.objects.create(workspace=workspace, name=identifier, identifier=identifier)

    shared, private, guest = [project(key) for key in ("SHARED", "PRIVATE", "GUEST")]
    memberships = [(shared, create_user, 15), (shared, other, 15), (private, other, 15), (guest, create_user, 5)]
    for target, user, role in memberships:
        ProjectMember.objects.create(workspace=workspace, project=target, member=user, role=role)
    guest.guest_view_all_features = False
    guest.save(update_fields=["guest_view_all_features"])

    def assign(name, target, user, group="started", **changes):
        state, _ = State.objects.get_or_create(project=target, name=group, defaults={"group": group, "color": "#888888"})
        issue = Issue.objects.create(project=target, state=state, name=name, created_by=other, **changes)
        return IssueAssignee.objects.create(project=target, issue=issue, assignee=user)

    assign("本人", shared, create_user)
    assign("同事", shared, other, "backlog")
    assign("私有", private, other, "unstarted")
    assign("失去项目访问权限", private, create_user)
    assign("访客无权查看", guest, create_user)
    assign("已完成", shared, create_user, "completed")
    assign("已取消", shared, create_user, "cancelled")
    assign("已归档", shared, create_user, archived_at=timezone.now())
    removed = assign("已移除负责人", shared, create_user)
    IssueAssignee.objects.filter(pk=removed.pk).update(deleted_at=timezone.now())

    url = f"/api/workspaces/{workspace.slug}/my-todos/"
    assert api_client.get(url).status_code in (401, 403)

    for user, expected in [(create_user, {"本人"}), (other, {"同事", "私有"})]:
        api_client.force_login(user)
        response = api_client.get(url)
        assert response.status_code == 200, response.data
        assert {row["name"] for row in response.data["results"]} == expected
