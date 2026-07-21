# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import re

# Django imports
from django.db import models
from django.db.models import (
    Q,
    OuterRef,
    Subquery,
    Value,
    UUIDField,
    CharField,
    When,
    Case,
)
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone

# Third party imports
from pypinyin import Style, lazy_pinyin
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.app.permissions import WorkspaceUserPermission
from plane.db.models import (
    Workspace,
    Project,
    Issue,
    Cycle,
    Module,
    Page,
    IssueView,
    ProjectMember,
    ProjectPage,
    WorkspaceMember,
)


def normalize_search_text(value):
    return " ".join(str(value or "").lower().strip().split())


def compact_search_text(value):
    return normalize_search_text(value).replace(" ", "")


def pinyin_candidates(value):
    value = str(value or "").strip()
    if not value:
        return set()

    syllables = lazy_pinyin(value, style=Style.NORMAL, errors="default")
    initials = lazy_pinyin(value, style=Style.FIRST_LETTER, errors="default")
    return {
        normalize_search_text(value),
        normalize_search_text(" ".join(syllables)),
        compact_search_text("".join(syllables)),
        compact_search_text("".join(initials)),
    }


def user_mention_matches_query(user, query):
    normalized_query = normalize_search_text(query)
    compact_query = compact_search_text(query)
    if not normalized_query:
        return True

    values = [
        user.get("member__first_name"),
        user.get("member__last_name"),
        user.get("member__display_name"),
        f"{user.get('member__first_name') or ''} {user.get('member__last_name') or ''}",
    ]

    for value in values:
        normalized_value = normalize_search_text(value)
        if normalized_query in normalized_value or compact_query in compact_search_text(value):
            return True

        candidates = pinyin_candidates(value)
        if normalized_query in candidates or compact_query in candidates:
            return True
        if any(normalized_query in candidate or compact_query in candidate for candidate in candidates):
            return True

    return False


def serialize_user_mention(user):
    return {
        "member__avatar_url": user["member__avatar_url"],
        "member__display_name": user["member__display_name"],
        "member__id": user["member__id"],
    }


class GlobalSearchEndpoint(BaseAPIView):
    """Endpoint to search across multiple fields in the workspace and
    also show related workspace if found
    """

    def filter_workspaces(self, query, _slug, _project_id, _workspace_search):
        fields = ["name"]
        q = Q()
        if query:
            for field in fields:
                q |= Q(**{f"{field}__icontains": query})
        return (
            Workspace.objects.filter(q, workspace_member__member=self.request.user)
            .order_by("-created_at")
            .distinct()
            .values("name", "id", "slug")
        )

    def filter_projects(self, query, slug, _project_id, _workspace_search):
        fields = ["name", "identifier"]
        q = Q()
        if query:
            for field in fields:
                q |= Q(**{f"{field}__icontains": query})
        return (
            Project.objects.filter(
                q,
                project_projectmember__member=self.request.user,
                project_projectmember__is_active=True,
                archived_at__isnull=True,
                workspace__slug=slug,
            )
            .order_by("-created_at")
            .distinct()
            .values("name", "id", "identifier", "workspace__slug")
        )

    def filter_issues(self, query, slug, project_id, workspace_search):
        fields = ["name", "sequence_id", "project__identifier"]
        q = Q()
        if query:
            for field in fields:
                if field == "sequence_id":
                    # Match whole integers only (exclude decimal numbers)
                    sequences = re.findall(r"\b\d+\b", query)
                    for sequence_id in sequences:
                        q |= Q(**{"sequence_id": sequence_id})
                else:
                    q |= Q(**{f"{field}__icontains": query})

        issues = Issue.issue_objects.filter(
            q,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
            workspace__slug=slug,
        )

        if workspace_search == "false" and project_id:
            issues = issues.filter(project_id=project_id)

        return issues.distinct().values(
            "name",
            "id",
            "sequence_id",
            "project__identifier",
            "project_id",
            "workspace__slug",
        )[:100]

    def filter_cycles(self, query, slug, project_id, workspace_search):
        fields = ["name"]
        q = Q()
        if query:
            for field in fields:
                q |= Q(**{f"{field}__icontains": query})

        cycles = Cycle.objects.filter(
            q,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
            workspace__slug=slug,
        )

        if workspace_search == "false" and project_id:
            cycles = cycles.filter(project_id=project_id)

        return (
            cycles.order_by("-created_at")
            .distinct()
            .values("name", "id", "project_id", "project__identifier", "workspace__slug")
        )

    def filter_modules(self, query, slug, project_id, workspace_search):
        fields = ["name"]
        q = Q()
        if query:
            for field in fields:
                q |= Q(**{f"{field}__icontains": query})

        modules = Module.objects.filter(
            q,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
            workspace__slug=slug,
        )

        if workspace_search == "false" and project_id:
            modules = modules.filter(project_id=project_id)

        return (
            modules.order_by("-created_at")
            .distinct()
            .values("name", "id", "project_id", "project__identifier", "workspace__slug")
        )

    def filter_pages(self, query, slug, project_id, workspace_search):
        fields = ["name"]
        q = Q()
        if query:
            for field in fields:
                q |= Q(**{f"{field}__icontains": query})

        pages = (
            Page.objects.filter(
                q,
                projects__project_projectmember__member=self.request.user,
                projects__project_projectmember__is_active=True,
                projects__archived_at__isnull=True,
                workspace__slug=slug,
            )
            .annotate(
                project_ids=Coalesce(
                    ArrayAgg("projects__id", distinct=True, filter=~Q(projects__id=True)),
                    Value([], output_field=ArrayField(UUIDField())),
                )
            )
            .annotate(
                project_identifiers=Coalesce(
                    ArrayAgg(
                        "projects__identifier",
                        distinct=True,
                        filter=~Q(projects__id=True),
                    ),
                    Value([], output_field=ArrayField(CharField())),
                )
            )
        )

        if workspace_search == "false" and project_id:
            project_subquery = ProjectPage.objects.filter(page_id=OuterRef("id"), project_id=project_id).values_list(
                "project_id", flat=True
            )[:1]

            pages = pages.annotate(project_id=Subquery(project_subquery)).filter(project_id=project_id)

        return (
            pages.order_by("-created_at")
            .distinct()
            .values("name", "id", "project_ids", "project_identifiers", "workspace__slug")
        )

    def filter_views(self, query, slug, project_id, workspace_search):
        fields = ["name"]
        q = Q()
        if query:
            for field in fields:
                q |= Q(**{f"{field}__icontains": query})

        issue_views = IssueView.objects.filter(
            q,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
            workspace__slug=slug,
        )

        if workspace_search == "false" and project_id:
            issue_views = issue_views.filter(project_id=project_id)

        return (
            issue_views.order_by("-created_at")
            .distinct()
            .values("name", "id", "project_id", "project__identifier", "workspace__slug")
        )

    def filter_intakes(self, query, slug, project_id, workspace_search):
        fields = ["name", "sequence_id", "project__identifier"]
        q = Q()
        if query:
            for field in fields:
                if field == "sequence_id":
                    # Match whole integers only (exclude decimal numbers)
                    sequences = re.findall(r"\b\d+\b", query)
                    for sequence_id in sequences:
                        q |= Q(**{"sequence_id": sequence_id})
                else:
                    q |= Q(**{f"{field}__icontains": query})

        issues = Issue.objects.filter(
            q,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
            workspace__slug=slug,
        ).filter(models.Q(issue_intake__status=0) | models.Q(issue_intake__status=-2))

        if workspace_search == "false" and project_id:
            issues = issues.filter(project_id=project_id)

        return (
            issues.order_by("-created_at")
            .distinct()
            .values(
                "name",
                "id",
                "sequence_id",
                "project__identifier",
                "project_id",
                "workspace__slug",
            )[:100]
        )

    def get(self, request, slug):
        query = request.query_params.get("search", False)
        entities_param = request.query_params.get("entities")
        workspace_search = request.query_params.get("workspace_search", "false")
        project_id = request.query_params.get("project_id", False)

        MODELS_MAPPER = {
            "workspace": self.filter_workspaces,
            "project": self.filter_projects,
            "issue": self.filter_issues,
            "cycle": self.filter_cycles,
            "module": self.filter_modules,
            "issue_view": self.filter_views,
            "page": self.filter_pages,
            "intake": self.filter_intakes,
        }

        # Determine which entities to search
        if entities_param:
            requested_entities = [e.strip() for e in entities_param.split(",") if e.strip()]
            requested_entities = [e for e in requested_entities if e in MODELS_MAPPER]
        else:
            requested_entities = list(MODELS_MAPPER.keys())

        results = {}

        for entity in requested_entities:
            func = MODELS_MAPPER.get(entity)
            if func:
                results[entity] = func(query or None, slug, project_id, workspace_search)

        return Response({"results": results}, status=status.HTTP_200_OK)


class SearchEndpoint(BaseAPIView):
    permission_classes = (WorkspaceUserPermission,)

    def user_mention_queryset(self, slug, project_id=None):
        model = ProjectMember if project_id else WorkspaceMember
        filters = {
            "is_active": True,
            "workspace__slug": slug,
            "member__is_bot": False,
        }
        if project_id:
            filters["project_id"] = project_id

        return (
            model.objects.filter(**filters)
            .annotate(
                member__avatar_url=Case(
                    When(
                        member__avatar_asset__isnull=False,
                        then=Concat(
                            Value("/api/assets/v2/static/"),
                            "member__avatar_asset",
                            Value("/"),
                        ),
                    ),
                    When(
                        member__avatar_asset__isnull=True,
                        then="member__avatar",
                    ),
                    default=Value(None),
                    output_field=CharField(),
                )
            )
            .order_by("-created_at")
            .distinct()
            .values(
                "member__avatar_url",
                "member__display_name",
                "member__first_name",
                "member__id",
                "member__last_name",
            )
        )

    def search_user_mentions(self, slug, query, count, project_id=None, include_all_user_mentions=False):
        users = [
            user
            for user in self.user_mention_queryset(slug, project_id)
            if user_mention_matches_query(user, query)
        ]

        if project_id and include_all_user_mentions and not normalize_search_text(query):
            return [serialize_user_mention(user) for user in users]

        return [serialize_user_mention(user) for user in users[:count]]

    def get(self, request, slug):
        query = request.query_params.get("query", "")
        query_types = request.query_params.get("query_type", "user_mention").split(",")
        query_types = [qt.strip() for qt in query_types]
        count = int(request.query_params.get("count", 5))
        project_id = request.query_params.get("project_id", None)
        include_all_user_mentions = request.query_params.get("include_all_user_mentions", "false").lower() == "true"

        response_data = {}

        if project_id:
            for query_type in query_types:
                if query_type == "user_mention":
                    response_data["user_mention"] = self.search_user_mentions(
                        slug,
                        query,
                        count,
                        project_id=project_id,
                        include_all_user_mentions=include_all_user_mentions,
                    )

                elif query_type == "project":
                    fields = ["name", "identifier"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})
                    projects = (
                        Project.objects.filter(
                            q,
                            Q(project_projectmember__member=self.request.user) | Q(network=2),
                            workspace__slug=slug,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values("name", "id", "identifier", "logo_props", "workspace__slug")[:count]
                    )
                    response_data["project"] = list(projects)

                elif query_type == "issue":
                    fields = ["name", "sequence_id", "project__identifier"]
                    q = Q()

                    if query:
                        for field in fields:
                            if field == "sequence_id":
                                sequences = re.findall(r"\b\d+\b", query)
                                for sequence_id in sequences:
                                    q |= Q(**{"sequence_id": sequence_id})
                            else:
                                q |= Q(**{f"{field}__icontains": query})

                    issues = (
                        Issue.issue_objects.filter(
                            q,
                            project__project_projectmember__member=self.request.user,
                            project__project_projectmember__is_active=True,
                            workspace__slug=slug,
                            project_id=project_id,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "sequence_id",
                            "project__identifier",
                            "project_id",
                            "priority",
                            "state_id",
                            "type_id",
                        )[:count]
                    )
                    response_data["issue"] = list(issues)

                elif query_type == "cycle":
                    fields = ["name"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})

                    cycles = (
                        Cycle.objects.filter(
                            q,
                            project__project_projectmember__member=self.request.user,
                            project__project_projectmember__is_active=True,
                            workspace__slug=slug,
                            project_id=project_id,
                        )
                        .annotate(
                            status=Case(
                                When(
                                    Q(start_date__lte=timezone.now()) & Q(end_date__gte=timezone.now()),
                                    then=Value("CURRENT"),
                                ),
                                When(
                                    start_date__gt=timezone.now(),
                                    then=Value("UPCOMING"),
                                ),
                                When(end_date__lt=timezone.now(), then=Value("COMPLETED")),
                                When(
                                    Q(start_date__isnull=True) & Q(end_date__isnull=True),
                                    then=Value("DRAFT"),
                                ),
                                default=Value("DRAFT"),
                                output_field=CharField(),
                            )
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "project_id",
                            "project__identifier",
                            "status",
                            "workspace__slug",
                        )[:count]
                    )
                    response_data["cycle"] = list(cycles)

                elif query_type == "module":
                    fields = ["name"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})

                    modules = (
                        Module.objects.filter(
                            q,
                            project__project_projectmember__member=self.request.user,
                            project__project_projectmember__is_active=True,
                            workspace__slug=slug,
                            project_id=project_id,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "project_id",
                            "project__identifier",
                            "status",
                            "workspace__slug",
                        )[:count]
                    )
                    response_data["module"] = list(modules)

                elif query_type == "page":
                    fields = ["name"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})

                    pages = (
                        Page.objects.filter(
                            q,
                            projects__project_projectmember__member=self.request.user,
                            projects__project_projectmember__is_active=True,
                            projects__id=project_id,
                            workspace__slug=slug,
                            access=0,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "logo_props",
                            "projects__id",
                            "workspace__slug",
                        )[:count]
                    )
                    response_data["page"] = list(pages)
            return Response(response_data, status=status.HTTP_200_OK)

        else:
            for query_type in query_types:
                if query_type == "user_mention":
                    response_data["user_mention"] = self.search_user_mentions(slug, query, count)

                elif query_type == "project":
                    fields = ["name", "identifier"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})
                    projects = (
                        Project.objects.filter(
                            q,
                            Q(project_projectmember__member=self.request.user) | Q(network=2),
                            workspace__slug=slug,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values("name", "id", "identifier", "logo_props", "workspace__slug")[:count]
                    )
                    response_data["project"] = list(projects)

                elif query_type == "issue":
                    fields = ["name", "sequence_id", "project__identifier"]
                    q = Q()

                    if query:
                        for field in fields:
                            if field == "sequence_id":
                                sequences = re.findall(r"\b\d+\b", query)
                                for sequence_id in sequences:
                                    q |= Q(**{"sequence_id": sequence_id})
                            else:
                                q |= Q(**{f"{field}__icontains": query})

                    issues = (
                        Issue.issue_objects.filter(
                            q,
                            project__project_projectmember__member=self.request.user,
                            project__project_projectmember__is_active=True,
                            workspace__slug=slug,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "sequence_id",
                            "project__identifier",
                            "project_id",
                            "priority",
                            "state_id",
                            "type_id",
                        )[:count]
                    )
                    response_data["issue"] = list(issues)

                elif query_type == "cycle":
                    fields = ["name"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})

                    cycles = (
                        Cycle.objects.filter(
                            q,
                            project__project_projectmember__member=self.request.user,
                            project__project_projectmember__is_active=True,
                            workspace__slug=slug,
                        )
                        .annotate(
                            status=Case(
                                When(
                                    Q(start_date__lte=timezone.now()) & Q(end_date__gte=timezone.now()),
                                    then=Value("CURRENT"),
                                ),
                                When(
                                    start_date__gt=timezone.now(),
                                    then=Value("UPCOMING"),
                                ),
                                When(end_date__lt=timezone.now(), then=Value("COMPLETED")),
                                When(
                                    Q(start_date__isnull=True) & Q(end_date__isnull=True),
                                    then=Value("DRAFT"),
                                ),
                                default=Value("DRAFT"),
                                output_field=CharField(),
                            )
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "project_id",
                            "project__identifier",
                            "status",
                            "workspace__slug",
                        )[:count]
                    )
                    response_data["cycle"] = list(cycles)

                elif query_type == "module":
                    fields = ["name"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})

                    modules = (
                        Module.objects.filter(
                            q,
                            project__project_projectmember__member=self.request.user,
                            project__project_projectmember__is_active=True,
                            workspace__slug=slug,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "project_id",
                            "project__identifier",
                            "status",
                            "workspace__slug",
                        )[:count]
                    )
                    response_data["module"] = list(modules)

                elif query_type == "page":
                    fields = ["name"]
                    q = Q()

                    if query:
                        for field in fields:
                            q |= Q(**{f"{field}__icontains": query})

                    pages = (
                        Page.objects.filter(
                            q,
                            projects__project_projectmember__member=self.request.user,
                            projects__project_projectmember__is_active=True,
                            workspace__slug=slug,
                            access=0,
                            is_global=True,
                        )
                        .order_by("-created_at")
                        .distinct()
                        .values(
                            "name",
                            "id",
                            "logo_props",
                            "projects__id",
                            "workspace__slug",
                        )[:count]
                    )
                    response_data["page"] = list(pages)
            return Response(response_data, status=status.HTTP_200_OK)
