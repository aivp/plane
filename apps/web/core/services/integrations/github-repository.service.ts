/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TGithubCredentialProfile, TGithubManagedRepository, TGithubRepositoryBranch } from "@plane/types";
import { APIService } from "@/services/api.service";

export class GithubRepositoryService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async listCredentials(workspaceSlug: string): Promise<TGithubCredentialProfile[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/github/credentials/`).then((response) => response.data);
  }

  async createCredential(
    workspaceSlug: string,
    data: { name: string; token: string }
  ): Promise<TGithubCredentialProfile> {
    return this.post(`/api/workspaces/${workspaceSlug}/github/credentials/`, data).then((response) => response.data);
  }

  async updateCredential(
    workspaceSlug: string,
    credentialId: string,
    data: { name?: string; token?: string }
  ): Promise<TGithubCredentialProfile> {
    return this.patch(`/api/workspaces/${workspaceSlug}/github/credentials/${credentialId}/`, data).then(
      (response) => response.data
    );
  }

  async deleteCredential(workspaceSlug: string, credentialId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/github/credentials/${credentialId}/`).then(
      (response) => response.data
    );
  }

  async verifyCredential(workspaceSlug: string, credentialId: string): Promise<TGithubCredentialProfile> {
    return this.post(`/api/workspaces/${workspaceSlug}/github/credentials/${credentialId}/verify/`).then(
      (response) => response.data
    );
  }

  async listRepositories(workspaceSlug: string): Promise<TGithubManagedRepository[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/github/repositories/`).then((response) => response.data);
  }

  async createRepository(
    workspaceSlug: string,
    data: {
      source: "manual" | "github_app";
      credential_profile_id?: string | null;
      owner: string;
      name: string;
      html_url?: string | null;
    }
  ): Promise<TGithubManagedRepository> {
    return this.post(`/api/workspaces/${workspaceSlug}/github/repositories/`, data).then((response) => response.data);
  }

  async updateRepository(
    workspaceSlug: string,
    repositoryId: string,
    data: {
      credential_profile_id?: string | null;
      owner?: string;
      name?: string;
      html_url?: string | null;
    }
  ): Promise<TGithubManagedRepository> {
    return this.patch(`/api/workspaces/${workspaceSlug}/github/repositories/${repositoryId}/`, data).then(
      (response) => response.data
    );
  }

  async deleteRepository(workspaceSlug: string, repositoryId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/github/repositories/${repositoryId}/`).then(
      (response) => response.data
    );
  }

  async syncBranches(workspaceSlug: string, repositoryId: string): Promise<TGithubManagedRepository> {
    return this.post(`/api/workspaces/${workspaceSlug}/github/repositories/${repositoryId}/sync-branches/`).then(
      (response) => response.data
    );
  }

  async listBranches(workspaceSlug: string, repositoryId: string): Promise<TGithubRepositoryBranch[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/github/repositories/${repositoryId}/branches/`).then(
      (response) => response.data.results
    );
  }
}
