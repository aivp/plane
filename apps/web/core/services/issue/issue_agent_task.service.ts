/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TIssueAgentTask, TIssueAgentTaskStatus } from "@plane/types";
import { APIService } from "@/services/api.service";

export class IssueAgentTaskService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async retrieve(workspaceSlug: string, projectId: string, issueId: string): Promise<TIssueAgentTask | null> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/agent-task/`).then(
      (response) => response.data
    );
  }

  async upsert(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    data: {
      repository_id?: string | null;
      base_branch?: string;
      status?: TIssueAgentTaskStatus;
    }
  ): Promise<TIssueAgentTask> {
    return this.put(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/agent-task/`, data).then(
      (response) => response.data
    );
  }

  async update(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    data: Partial<{
      repository_id: string | null;
      base_branch: string;
      status: TIssueAgentTaskStatus;
    }>
  ): Promise<TIssueAgentTask> {
    return super
      .patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/agent-task/`, data)
      .then((response) => response.data);
  }

  async cancel(workspaceSlug: string, projectId: string, issueId: string): Promise<TIssueAgentTask> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/agent-task/`).then(
      (response) => response.data
    );
  }
}
