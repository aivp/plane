# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from celery import shared_task

from plane.db.models import GithubManagedRepository, GithubRepositorySync
from plane.integrations.github import sync_github_app_repositories, sync_repository_branches


@shared_task
def github_sync_repository_branches(repository_id):
    repository = GithubManagedRepository.objects.get(pk=repository_id)
    sync_repository_branches(repository)
    return str(repository.id)


@shared_task
def github_sync_all_repository_branches(limit=100):
    workspace_ids = (
        GithubRepositorySync.objects.values_list("workspace_id", flat=True)
        .union(GithubManagedRepository.objects.values_list("workspace_id", flat=True))
    )
    for workspace_id in workspace_ids:
        sync_github_app_repositories(workspace_id)

    repository_ids = list(
        GithubManagedRepository.objects.filter(
            sync_status__in=[
                GithubManagedRepository.SyncStatus.PENDING,
                GithubManagedRepository.SyncStatus.SYNCED,
                GithubManagedRepository.SyncStatus.FAILED,
            ]
        )
        .order_by("last_synced_at", "created_at")
        .values_list("id", flat=True)[:limit]
    )
    for repository_id in repository_ids:
        github_sync_repository_branches.delay(str(repository_id))
    return len(repository_ids)
