# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import requests
from django.utils import timezone

from plane.db.models import GithubManagedRepository, GithubRepositoryBranch, GithubRepositorySync
from plane.license.utils.encryption import decrypt_data


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def sync_github_app_repositories(workspace_id) -> int:
    syncs = GithubRepositorySync.objects.filter(workspace_id=workspace_id).select_related("repository")
    synced_count = 0

    for sync in syncs:
        repository = sync.repository
        full_name = f"{repository.owner}/{repository.name}"
        managed_repository = GithubManagedRepository.objects.filter(
            workspace_id=workspace_id,
            full_name=full_name,
        ).first()

        if managed_repository:
            managed_repository.html_url = repository.url or managed_repository.html_url
            if managed_repository.source == GithubManagedRepository.Source.GITHUB_APP:
                managed_repository.owner = repository.owner
                managed_repository.name = repository.name
            managed_repository.save(update_fields=["owner", "name", "html_url", "updated_at"])
        else:
            GithubManagedRepository.objects.create(
                workspace_id=workspace_id,
                source=GithubManagedRepository.Source.GITHUB_APP,
                owner=repository.owner,
                name=repository.name,
                full_name=full_name,
                html_url=repository.url,
            )

        synced_count += 1

    return synced_count


def _extract_token_from_repository(repository: GithubManagedRepository) -> str:
    if repository.credential_profile_id:
        token = decrypt_data(repository.credential_profile.token_encrypted)
        if token:
            return token

    legacy_sync = (
        GithubRepositorySync.objects.filter(
            workspace_id=repository.workspace_id,
            repository__owner=repository.owner,
            repository__name=repository.name,
        )
        .select_related("repository")
        .first()
    )
    credentials = legacy_sync.credentials if legacy_sync else {}
    for key in ("access_token", "token", "github_token"):
        if credentials.get(key):
            return credentials[key]

    raise GitHubAPIError("No GitHub credential is available for this repository.")


def _github_get(url: str, token: str, params: dict | None = None) -> requests.Response:
    response = requests.get(
        url,
        params=params,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        message = "GitHub API request failed."
        try:
            message = response.json().get("message") or message
        except ValueError:
            pass
        raise GitHubAPIError(message, status_code=response.status_code)
    return response


def verify_github_token(token: str) -> None:
    _github_get("https://api.github.com/user", token)


def sync_repository_branches(repository: GithubManagedRepository) -> GithubManagedRepository:
    repository.sync_status = GithubManagedRepository.SyncStatus.SYNCING
    repository.last_sync_error = None
    repository.save(update_fields=["sync_status", "last_sync_error", "updated_at"])

    try:
        token = _extract_token_from_repository(repository)
        repo_response = _github_get(f"https://api.github.com/repos/{repository.full_name}", token)
        repo_data = repo_response.json()

        repository.default_branch = repo_data.get("default_branch") or repository.default_branch
        repository.html_url = repo_data.get("html_url") or repository.html_url
        repository.visibility = repo_data.get("visibility") or (
            GithubManagedRepository.Visibility.PRIVATE
            if repo_data.get("private")
            else GithubManagedRepository.Visibility.PUBLIC
        )

        page = 1
        now = timezone.now()
        while True:
            branch_response = _github_get(
                f"https://api.github.com/repos/{repository.full_name}/branches",
                token,
                params={"per_page": 100, "page": page},
            )
            branches = branch_response.json()
            if not branches:
                break

            for branch in branches:
                GithubRepositoryBranch.objects.update_or_create(
                    repository=repository,
                    name=branch.get("name", ""),
                    defaults={
                        "sha": (branch.get("commit") or {}).get("sha", ""),
                        "protected": bool(branch.get("protected")),
                        "is_default": branch.get("name") == repository.default_branch,
                        "last_seen_at": now,
                    },
                )

            if len(branches) < 100:
                break
            page += 1

        repository.sync_status = GithubManagedRepository.SyncStatus.SYNCED
        repository.last_synced_at = now
        repository.last_sync_error = None
        repository.save(
            update_fields=[
                "default_branch",
                "html_url",
                "visibility",
                "sync_status",
                "last_synced_at",
                "last_sync_error",
                "updated_at",
            ]
        )
    except Exception as exc:
        repository.sync_status = GithubManagedRepository.SyncStatus.FAILED
        repository.last_sync_error = str(exc)
        repository.save(update_fields=["sync_status", "last_sync_error", "updated_at"])
        if (
            repository.credential_profile_id
            and isinstance(exc, GitHubAPIError)
            and exc.status_code in [401, 403]
        ):
            repository.credential_profile.status = repository.credential_profile.Status.INVALID
            repository.credential_profile.last_error = "GitHub credential is invalid."
            repository.credential_profile.save(update_fields=["status", "last_error", "updated_at"])

    return repository
