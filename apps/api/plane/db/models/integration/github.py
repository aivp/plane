# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports

# Django imports
from django.db import models

# Module imports
from plane.db.models.base import BaseModel
from plane.db.models.project import ProjectBaseModel


class GithubRepository(ProjectBaseModel):
    name = models.CharField(max_length=500)
    url = models.URLField(null=True)
    config = models.JSONField(default=dict)
    repository_id = models.BigIntegerField()
    owner = models.CharField(max_length=500)

    def __str__(self):
        """Return the repo name"""
        return f"{self.name}"

    class Meta:
        verbose_name = "Repository"
        verbose_name_plural = "Repositories"
        db_table = "github_repositories"
        ordering = ("-created_at",)


class GithubRepositorySync(ProjectBaseModel):
    repository = models.OneToOneField("db.GithubRepository", on_delete=models.CASCADE, related_name="syncs")
    credentials = models.JSONField(default=dict)
    # Bot user
    actor = models.ForeignKey("db.User", related_name="user_syncs", on_delete=models.CASCADE)
    workspace_integration = models.ForeignKey(
        "db.WorkspaceIntegration", related_name="github_syncs", on_delete=models.CASCADE
    )
    label = models.ForeignKey("db.Label", on_delete=models.SET_NULL, null=True, related_name="repo_syncs")

    def __str__(self):
        """Return the repo sync"""
        return f"{self.repository.name} <{self.project.name}>"

    class Meta:
        unique_together = ["project", "repository"]
        verbose_name = "Github Repository Sync"
        verbose_name_plural = "Github Repository Syncs"
        db_table = "github_repository_syncs"
        ordering = ("-created_at",)


class GithubIssueSync(ProjectBaseModel):
    repo_issue_id = models.BigIntegerField()
    github_issue_id = models.BigIntegerField()
    issue_url = models.URLField(blank=False)
    issue = models.ForeignKey("db.Issue", related_name="github_syncs", on_delete=models.CASCADE)
    repository_sync = models.ForeignKey("db.GithubRepositorySync", related_name="issue_syncs", on_delete=models.CASCADE)

    def __str__(self):
        """Return the github issue sync"""
        return f"{self.repository.name}-{self.project.name}-{self.issue.name}"

    class Meta:
        unique_together = ["repository_sync", "issue"]
        verbose_name = "Github Issue Sync"
        verbose_name_plural = "Github Issue Syncs"
        db_table = "github_issue_syncs"
        ordering = ("-created_at",)


class GithubCommentSync(ProjectBaseModel):
    repo_comment_id = models.BigIntegerField()
    comment = models.ForeignKey("db.IssueComment", related_name="comment_syncs", on_delete=models.CASCADE)
    issue_sync = models.ForeignKey("db.GithubIssueSync", related_name="comment_syncs", on_delete=models.CASCADE)

    def __str__(self):
        """Return the github issue sync"""
        return f"{self.comment.id}"

    class Meta:
        unique_together = ["issue_sync", "comment"]
        verbose_name = "Github Comment Sync"
        verbose_name_plural = "Github Comment Syncs"
        db_table = "github_comment_syncs"
        ordering = ("-created_at",)


class GithubCredentialProfile(BaseModel):
    class Provider(models.TextChoices):
        GITHUB = "github", "GitHub"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVALID = "invalid", "Invalid"

    workspace = models.ForeignKey(
        "db.Workspace",
        related_name="github_credential_profiles",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.GITHUB)
    token_encrypted = models.TextField()
    token_last_four = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "GitHub Credential Profile"
        verbose_name_plural = "GitHub Credential Profiles"
        db_table = "github_credential_profiles"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="github_credential_profile_unique_workspace_name_when_deleted_at_null",
            )
        ]

    def __str__(self):
        return f"{self.name} <{self.workspace_id}>"


class GithubManagedRepository(BaseModel):
    class Source(models.TextChoices):
        GITHUB_APP = "github_app", "GitHub App"
        MANUAL = "manual", "Manual"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"
        INTERNAL = "internal", "Internal"
        UNKNOWN = "unknown", "Unknown"

    class SyncStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SYNCING = "syncing", "Syncing"
        SYNCED = "synced", "Synced"
        FAILED = "failed", "Failed"

    workspace = models.ForeignKey(
        "db.Workspace",
        related_name="github_managed_repositories",
        on_delete=models.CASCADE,
    )
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.MANUAL)
    credential_profile = models.ForeignKey(
        "db.GithubCredentialProfile",
        related_name="managed_repositories",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    owner = models.CharField(max_length=500)
    name = models.CharField(max_length=500)
    full_name = models.CharField(max_length=1000)
    html_url = models.URLField(null=True, blank=True)
    default_branch = models.CharField(max_length=255, blank=True, default="")
    visibility = models.CharField(max_length=32, choices=Visibility.choices, default=Visibility.UNKNOWN)
    sync_status = models.CharField(max_length=32, choices=SyncStatus.choices, default=SyncStatus.PENDING)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "GitHub Managed Repository"
        verbose_name_plural = "GitHub Managed Repositories"
        db_table = "github_managed_repositories"
        ordering = ("full_name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "full_name"],
                condition=models.Q(deleted_at__isnull=True),
                name="github_managed_repository_unique_workspace_full_name_when_deleted_at_null",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.full_name and self.owner and self.name:
            self.full_name = f"{self.owner}/{self.name}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


class GithubRepositoryBranch(BaseModel):
    repository = models.ForeignKey(
        "db.GithubManagedRepository",
        related_name="branches",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    sha = models.CharField(max_length=255, blank=True, default="")
    protected = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "GitHub Repository Branch"
        verbose_name_plural = "GitHub Repository Branches"
        db_table = "github_repository_branches"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="github_repository_branch_unique_repository_name_when_deleted_at_null",
            )
        ]

    def __str__(self):
        return f"{self.repository.full_name}:{self.name}"
