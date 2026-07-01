# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.urls import reverse

from plane.db.models import Project, ProjectMember, User, WorkspaceMember


def create_workspace_user(workspace, display_name, first_name=None, last_name=None, is_bot=False):
    unique_id = uuid4().hex
    user = User.objects.create(
        email=f"{unique_id}@plane.so",
        username=f"user_{unique_id}",
        display_name=display_name,
        first_name=first_name or display_name,
        last_name=last_name or "",
        is_bot=is_bot,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    return user


@pytest.fixture
def entity_search_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Entity Search Project",
        identifier="ESP",
        workspace=workspace,
        created_by=create_user,
        updated_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20)
    return project


@pytest.mark.contract
class TestEntitySearchEndpoint:
    def get_url(self, workspace_slug):
        return reverse("entity-search", kwargs={"slug": workspace_slug})

    @pytest.mark.django_db
    def test_project_user_mentions_can_return_all_project_members(
        self, session_client, workspace, entity_search_project
    ):
        project_users = []
        for index in range(6):
            user = create_workspace_user(workspace, f"Member {index}")
            ProjectMember.objects.create(project=entity_search_project, member=user, role=15)
            project_users.append(user)

        non_project_user = create_workspace_user(workspace, "Outside Project")
        bot_user = create_workspace_user(workspace, "Search Bot", is_bot=True)
        ProjectMember.objects.create(project=entity_search_project, member=bot_user, role=15)

        response = session_client.get(
            self.get_url(workspace.slug),
            {
                "query": "",
                "query_type": "user_mention",
                "count": 5,
                "project_id": str(entity_search_project.id),
                "include_all_user_mentions": "true",
            },
        )

        assert response.status_code == 200
        returned_ids = {str(item["member__id"]) for item in response.data["user_mention"]}
        assert len(response.data["user_mention"]) == 7
        assert {str(user.id) for user in project_users}.issubset(returned_ids)
        assert str(non_project_user.id) not in returned_ids
        assert str(bot_user.id) not in returned_ids

    @pytest.mark.django_db
    def test_project_user_mentions_keep_count_limit_without_include_all(
        self, session_client, workspace, entity_search_project
    ):
        for index in range(6):
            user = create_workspace_user(workspace, f"Limited Member {index}")
            ProjectMember.objects.create(project=entity_search_project, member=user, role=15)

        response = session_client.get(
            self.get_url(workspace.slug),
            {
                "query": "",
                "query_type": "user_mention",
                "count": 5,
                "project_id": str(entity_search_project.id),
            },
        )

        assert response.status_code == 200
        assert len(response.data["user_mention"]) == 5

    @pytest.mark.django_db
    @pytest.mark.parametrize("query", ["zhangsan", "zhang san", "zs"])
    def test_user_mentions_match_chinese_names_by_pinyin(
        self, session_client, workspace, entity_search_project, query
    ):
        user = create_workspace_user(workspace, "张三", first_name="张", last_name="三")
        ProjectMember.objects.create(project=entity_search_project, member=user, role=15)

        response = session_client.get(
            self.get_url(workspace.slug),
            {
                "query": query,
                "query_type": "user_mention",
                "count": 5,
                "project_id": str(entity_search_project.id),
            },
        )

        assert response.status_code == 200
        assert [str(item["member__id"]) for item in response.data["user_mention"]] == [str(user.id)]
