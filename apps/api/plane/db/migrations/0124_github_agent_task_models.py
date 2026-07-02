# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0123_lark_workspace_member_exclusion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GithubCredentialProfile",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "provider",
                    models.CharField(choices=[("github", "GitHub")], default="github", max_length=32),
                ),
                ("token_encrypted", models.TextField()),
                ("token_last_four", models.CharField(blank=True, max_length=8)),
                (
                    "status",
                    models.CharField(choices=[("active", "Active"), ("invalid", "Invalid")], default="active", max_length=32),
                ),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="github_credential_profiles",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "GitHub Credential Profile",
                "verbose_name_plural": "GitHub Credential Profiles",
                "db_table": "github_credential_profiles",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="GithubManagedRepository",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("github_app", "GitHub App"), ("manual", "Manual")],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("owner", models.CharField(max_length=500)),
                ("name", models.CharField(max_length=500)),
                ("full_name", models.CharField(max_length=1000)),
                ("html_url", models.URLField(blank=True, null=True)),
                ("default_branch", models.CharField(blank=True, default="", max_length=255)),
                (
                    "visibility",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("private", "Private"),
                            ("internal", "Internal"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=32,
                    ),
                ),
                (
                    "sync_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("syncing", "Syncing"),
                            ("synced", "Synced"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_sync_error", models.TextField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "credential_profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="managed_repositories",
                        to="db.githubcredentialprofile",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="github_managed_repositories",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "GitHub Managed Repository",
                "verbose_name_plural": "GitHub Managed Repositories",
                "db_table": "github_managed_repositories",
                "ordering": ("full_name",),
            },
        ),
        migrations.CreateModel(
            name="GithubRepositoryBranch",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("sha", models.CharField(blank=True, default="", max_length=255)),
                ("protected", models.BooleanField(default=False)),
                ("is_default", models.BooleanField(default=False)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "repository",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="branches",
                        to="db.githubmanagedrepository",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "verbose_name": "GitHub Repository Branch",
                "verbose_name_plural": "GitHub Repository Branches",
                "db_table": "github_repository_branches",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="IssueAgentTask",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("base_branch", models.CharField(blank=True, default="", max_length=255)),
                ("work_branch", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("pr_url", models.URLField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, null=True)),
                ("claimed_by", models.CharField(blank=True, max_length=255, null=True)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "issue",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="agent_task", to="db.issue"),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issue_agent_tasks",
                        to="db.project",
                    ),
                ),
                (
                    "repository",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="issue_agent_tasks",
                        to="db.githubmanagedrepository",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issue_agent_tasks",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Issue Agent Task",
                "verbose_name_plural": "Issue Agent Tasks",
                "db_table": "issue_agent_tasks",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="githubcredentialprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("workspace", "name"),
                name="github_credential_profile_unique_workspace_name_when_deleted_at_null",
            ),
        ),
        migrations.AddConstraint(
            model_name="githubmanagedrepository",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("workspace", "full_name"),
                name="github_managed_repository_unique_workspace_full_name_when_deleted_at_null",
            ),
        ),
        migrations.AddConstraint(
            model_name="githubrepositorybranch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("repository", "name"),
                name="github_repository_branch_unique_repository_name_when_deleted_at_null",
            ),
        ),
        migrations.AddIndex(
            model_name="issueagenttask",
            index=models.Index(fields=["workspace", "status"], name="iat_workspace_status_idx"),
        ),
        migrations.AddIndex(
            model_name="issueagenttask",
            index=models.Index(fields=["project", "status"], name="iat_project_status_idx"),
        ),
    ]
