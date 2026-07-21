/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import useSWR, { mutate } from "swr";
import { Bot, Copy, ExternalLink, GitBranch, Github, RefreshCw, XCircle } from "lucide-react";
import {
  EUserPermissions,
  EUserPermissionsLevel,
  GITHUB_MANAGED_REPOSITORIES,
  GITHUB_REPOSITORY_BRANCHES,
  ISSUE_AGENT_TASK,
} from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssueAgentTaskStatus } from "@plane/types";
import { GithubRepositoryService } from "@/services/integrations";
import { IssueAgentTaskService } from "@/services/issue";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { useUserPermissions } from "@/hooks/store/user";
import { IssueAgentTaskBadge } from "./agent-badge";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
};

const githubRepositoryService = new GithubRepositoryService();
const issueAgentTaskService = new IssueAgentTaskService();

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.error ?? error?.data?.error ?? error?.message ?? fallback;

const STATUS_LABELS: Record<TIssueAgentTaskStatus, string> = {
  pending: "等待中",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const RERUN_STATUSES = new Set<TIssueAgentTaskStatus>(["completed", "failed", "cancelled"]);

export function IssueAgentTaskProperty(props: Props) {
  const { workspaceSlug, projectId, issueId, disabled } = props;
  const { allowPermissions } = useUserPermissions();
  const [repositoryId, setRepositoryId] = useState("");
  const [baseBranch, setBaseBranch] = useState("");
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const { data: task } = useSWR(ISSUE_AGENT_TASK(issueId), () =>
    issueAgentTaskService.retrieve(workspaceSlug, projectId, issueId)
  );
  const { data: repositories = [] } = useSWR(GITHUB_MANAGED_REPOSITORIES(workspaceSlug), () =>
    githubRepositoryService.listRepositories(workspaceSlug)
  );
  const { data: branches = [] } = useSWR(
    repositoryId ? GITHUB_REPOSITORY_BRANCHES(workspaceSlug, repositoryId) : null,
    () => githubRepositoryService.listBranches(workspaceSlug, repositoryId)
  );

  const isWorkspaceAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);
  const isBusy = loadingAction !== null;
  const isRunning = task?.status === "running";
  const isPending = task?.status === "pending";
  const canEditTarget = !disabled && !isRunning;
  const canStart = !disabled && !isRunning && !isPending;
  const isRerun = !!task?.status && RERUN_STATUSES.has(task.status);
  const startButtonLabel = isRerun ? "让 AI 再次实现" : "让 AI 实现";

  useEffect(() => {
    if (task) {
      setRepositoryId(task.repository?.id ?? "");
      setBaseBranch(task.base_branch ?? "");
    }
  }, [task]);

  useEffect(() => {
    if (!task) {
      setRepositoryId("");
      setBaseBranch("");
    }
  }, [issueId, task]);

  const showError = (message: string) =>
    setToast({
      type: TOAST_TYPE.ERROR,
      title: "AI Coding Agent 设置失败",
      message,
    });

  const refreshTask = () => mutate(ISSUE_AGENT_TASK(issueId));

  const saveTask = async (
    next: {
      status?: TIssueAgentTaskStatus;
      repositoryId?: string;
      baseBranch?: string;
    },
    successMessage = "AI Coding Agent 已更新。"
  ) => {
    const nextStatus = next.status ?? task?.status;
    if (!nextStatus) return;

    const nextRepositoryId = next.repositoryId !== undefined ? next.repositoryId : repositoryId;
    const nextBaseBranch = next.baseBranch !== undefined ? next.baseBranch : baseBranch;

    setLoadingAction(nextStatus === "cancelled" ? "cancel" : nextStatus === "pending" ? "start" : "save");
    try {
      await issueAgentTaskService.update(workspaceSlug, projectId, issueId, {
        repository_id: nextRepositoryId || null,
        base_branch: nextBaseBranch || "",
        status: nextStatus,
      });
      await refreshTask();
      setToast({ type: TOAST_TYPE.SUCCESS, title: "AI Coding Agent 已更新", message: successMessage });
    } catch (error: any) {
      showError(getErrorMessage(error, "AI Coding Agent 设置保存失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const startAgent = () => {
    if (!repositoryId || !baseBranch) {
      showError("请选择仓库和分支。");
      return;
    }
    void saveTask(
      { status: "pending", repositoryId, baseBranch },
      isRerun ? "已重新加入等待队列。" : "已加入等待队列。"
    );
  };

  const cancelAgent = () => saveTask({ status: "cancelled" }, "已取消等待，后续仍可再次让 AI 实现。");

  const syncBranches = async () => {
    if (!repositoryId) return;
    if (!isWorkspaceAdmin) {
      showError("只有 Workspace Admin 可以刷新分支。");
      return;
    }
    setLoadingAction("sync");
    try {
      await githubRepositoryService.syncBranches(workspaceSlug, repositoryId);
      await mutate(GITHUB_REPOSITORY_BRANCHES(workspaceSlug, repositoryId));
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
    } catch (error: any) {
      showError(getErrorMessage(error, "分支刷新失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="space-y-2.5 border-t border-subtle pt-3">
      <div className="flex items-center justify-between">
        <h5 className="text-body-xs-medium">AI Coding Agent</h5>
        {task && <IssueAgentTaskBadge task={task} />}
      </div>

      <SidebarPropertyListItem icon={Bot} label="状态">
        <span className="w-full px-2 text-body-xs-regular text-secondary">
          {task?.status ? STATUS_LABELS[task.status] : "未设置"}
        </span>
      </SidebarPropertyListItem>

      <SidebarPropertyListItem icon={Github} label="仓库">
        <select
          className="h-7.5 w-full rounded bg-transparent px-2 text-body-xs-regular"
          value={repositoryId}
          disabled={!canEditTarget || isBusy}
          onChange={(e) => {
            const nextRepositoryId = e.target.value;
            setRepositoryId(nextRepositoryId);
            setBaseBranch("");
            if (task?.status === "pending") void saveTask({ repositoryId: nextRepositoryId, baseBranch: "" });
          }}
        >
          <option value="">选择仓库</option>
          {repositories.map((repository) => (
            <option key={repository.id} value={repository.id}>
              {repository.full_name}
            </option>
          ))}
        </select>
      </SidebarPropertyListItem>

      <SidebarPropertyListItem icon={GitBranch} label="分支">
        <div className="flex w-full items-center gap-1">
          <select
            className="h-7.5 min-w-0 grow rounded bg-transparent px-2 text-body-xs-regular"
            value={baseBranch}
            disabled={!canEditTarget || isBusy || !repositoryId}
            onChange={(e) => {
              const nextBaseBranch = e.target.value;
              setBaseBranch(nextBaseBranch);
              if (task?.status === "pending") void saveTask({ baseBranch: nextBaseBranch });
            }}
          >
            <option value="">选择分支</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.name}>
                {branch.name}
              </option>
            ))}
          </select>
          {canEditTarget && isWorkspaceAdmin && (
            <Button
              variant="ghost"
              size="sm"
              onClick={syncBranches}
              loading={loadingAction === "sync"}
              disabled={!repositoryId || isBusy}
            >
              <RefreshCw className="size-3" />
            </Button>
          )}
        </div>
      </SidebarPropertyListItem>

      {task?.work_branch && (
        <div className="text-caption truncate px-2 text-secondary">工作分支：{task.work_branch}</div>
      )}

      {task?.pr_url && (
        <div className="flex items-center gap-1 px-2">
          <a
            className="text-caption min-w-0 truncate text-link-primary"
            href={task.pr_url}
            target="_blank"
            rel="noreferrer"
          >
            {task.pr_url}
          </a>
          <ExternalLink className="size-3 shrink-0 text-secondary" />
          <Button variant="ghost" size="sm" onClick={() => navigator.clipboard?.writeText(task.pr_url ?? "")}>
            <Copy className="size-3" />
          </Button>
        </div>
      )}

      {task?.last_error && (
        <div className="text-caption mx-2 max-h-24 overflow-y-auto rounded border border-danger-subtle bg-danger-subtle px-2 py-1 text-danger-primary">
          {task.last_error}
        </div>
      )}

      <div className="flex items-center gap-2 px-2">
        {canStart && (
          <Button
            variant="primary"
            size="sm"
            className="min-w-0 grow justify-center"
            onClick={startAgent}
            loading={loadingAction === "start"}
            disabled={!repositoryId || !baseBranch || isBusy}
          >
            <Bot className="size-3 shrink-0" />
            <span className="truncate">{startButtonLabel}</span>
          </Button>
        )}
        {isPending && !disabled && (
          <Button
            variant="secondary"
            size="sm"
            className="min-w-0 grow justify-center"
            onClick={cancelAgent}
            loading={loadingAction === "cancel"}
            disabled={isBusy}
          >
            <XCircle className="size-3 shrink-0" />
            <span className="truncate">取消等待</span>
          </Button>
        )}
      </div>
    </div>
  );
}
