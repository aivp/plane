/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TLarkWorkspaceRole = 5 | 15 | 20;

export type TLarkContact = {
  open_id: string | null;
  union_id: string | null;
  user_id?: string;
  employee_no?: string;
  name: string;
  email?: string;
  avatar?: string;
  status?: Record<string, unknown>;
  is_active: boolean;
  is_imported: boolean;
  workspace_role: TLarkWorkspaceRole | null;
};

export type TLarkSyncRun = {
  id: string;
  job_id: string;
  sync_type: "full" | "incremental" | "import";
  status: "pending" | "running" | "succeeded" | "failed";
  users_seen: number;
  users_created: number;
  users_updated: number;
  members_added: number;
  members_deactivated: number;
  users_skipped: number;
  error: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type TLarkInstanceStatus = {
  enabled: boolean;
  configured: boolean;
  domain: "feishu.cn";
  client_id_configured: boolean;
  client_secret_configured: boolean;
  auto_sync_enabled: boolean;
  notifications_enabled: boolean;
  connector_enabled: boolean;
  default_workspace_slug: string;
  default_workspace_role: TLarkWorkspaceRole;
  oauth_callback_urls: {
    app: string;
    space: string;
    admin: string;
  };
  connector: {
    healthy: boolean;
    last_heartbeat: string | null;
  };
};
