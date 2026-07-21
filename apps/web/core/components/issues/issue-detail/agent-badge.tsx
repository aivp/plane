/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle, CheckCircle2, Clock3, Loader2, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { TIssueAgentTaskLite, TIssueAgentTaskStatus } from "@plane/types";

const STATUS_META: Record<TIssueAgentTaskStatus, { label: string; className: string; icon: LucideIcon }> = {
  pending: { label: "等待中", className: "text-secondary", icon: Clock3 },
  running: { label: "执行中", className: "text-accent-primary", icon: Loader2 },
  completed: { label: "已完成", className: "text-success-primary", icon: CheckCircle2 },
  failed: { label: "失败", className: "text-danger-primary", icon: AlertTriangle },
  cancelled: { label: "已取消", className: "text-secondary", icon: XCircle },
};

export function IssueAgentTaskBadge({ task, compact = false }: { task: TIssueAgentTaskLite; compact?: boolean }) {
  const meta = STATUS_META[task.status];
  const Icon = meta.icon;
  const detail = task.pr_url ?? task.last_error ?? task.work_branch;
  const repositoryName = task.repository?.full_name ?? "未配置仓库";

  return (
    <span
      title={[meta.label, repositoryName, task.base_branch, detail].filter(Boolean).join(" · ")}
      className={`text-caption inline-flex h-5 max-w-full items-center gap-1 rounded border border-subtle bg-surface-1 px-1.5 ${meta.className}`}
    >
      <Icon className={`size-3 shrink-0 ${task.status === "running" ? "animate-spin" : ""}`} />
      {!compact && <span className="truncate">{meta.label}</span>}
    </span>
  );
}
