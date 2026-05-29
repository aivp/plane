/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TLarkContact, TLarkSyncRun, TLarkWorkspaceRole } from "@plane/types";
import { APIService } from "../api.service";

export class WorkspaceLarkService extends APIService {
  constructor(BASE_URL?: string) {
    super(BASE_URL || API_BASE_URL);
  }

  async contacts(workspaceSlug: string, params?: { search?: string; limit?: number }): Promise<{ contacts: TLarkContact[] }> {
    return this.get(`/api/workspaces/${workspaceSlug}/lark/contacts/`, { params })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async sync(workspaceSlug: string, data?: { role?: TLarkWorkspaceRole }): Promise<TLarkSyncRun> {
    return this.post(`/api/workspaces/${workspaceSlug}/lark/sync/`, data || {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async syncRuns(workspaceSlug: string): Promise<{ sync_runs: TLarkSyncRun[] }> {
    return this.get(`/api/workspaces/${workspaceSlug}/lark/sync-runs/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async importUsers(
    workspaceSlug: string,
    data: { user_ids: string[]; user_id_type?: "open_id" | "union_id" | "user_id"; role?: TLarkWorkspaceRole }
  ): Promise<{ sync_run: TLarkSyncRun; stats: Record<string, number> }> {
    return this.post(`/api/workspaces/${workspaceSlug}/lark/import/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
