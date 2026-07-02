/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { Bot, Copy, ExternalLink, GitBranch, RefreshCw } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import {
  GITHUB_MANAGED_REPOSITORIES,
  GITHUB_REPOSITORY_BRANCHES,
  ISSUE_AGENT_TASK,
} from "@/constants/fetch-keys";
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

  const selectedRepository = useMemo(
    () => repositories.find((repository) => repository.id === repositoryId),
    [repositories, repositoryId]
  );
  const isWorkspaceAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);
  const isProjectAdmin = allowPermissions(
    [EUserPermissions.ADMIN],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );
  const isReadOnly = disabled || task?.status === "running" || task?.status === "completed";
  const canSubmit = Boolean(repositoryId && baseBranch && !isReadOnly);
  const canResetCompleted = Boolean(task?.status === "completed" && !disabled && (isWorkspaceAdmin || isProjectAdmin));

  useEffect(() => {
    if (task) {
      setRepositoryId(task.repository.id);
      setBaseBranch(task.base_branch);
    }
  }, [task?.id, task?.repository.id, task?.base_branch]);

  useEffect(() => {
    if (!task && !repositoryId && repositories[0]) setRepositoryId(repositories[0].id);
  }, [task, repositories, repositoryId]);

  useEffect(() => {
    if (!isReadOnly && !baseBranch && branches.length > 0) {
      const defaultBranch = branches.find((branch) => branch.is_default)?.name;
      setBaseBranch(defaultBranch ?? selectedRepository?.default_branch ?? branches[0].name);
    }
  }, [isReadOnly, selectedRepository, branches, baseBranch]);

  const showError = (message: string) =>
    setToast({
      type: TOAST_TYPE.ERROR,
      title: "Agent 任务操作失败",
      message,
    });

  const refreshTask = () => mutate(ISSUE_AGENT_TASK(issueId));

  const submitTask = async () => {
    if (!canSubmit) return;
    setLoadingAction("submit");
    try {
      await issueAgentTaskService.upsert(workspaceSlug, projectId, issueId, {
        repository_id: repositoryId,
        base_branch: baseBranch,
        status: "pending",
      });
      await refreshTask();
      setToast({ type: TOAST_TYPE.SUCCESS, title: "已交给 Agent", message: "当前卡片已进入等待队列。" });
    } catch (error: any) {
      showError(getErrorMessage(error, "Agent 任务保存失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const retryTask = async () => {
    if (!task) return;
    setLoadingAction("retry");
    try {
      await issueAgentTaskService.update(workspaceSlug, projectId, issueId, {
        repository_id: repositoryId || task.repository.id,
        base_branch: baseBranch || task.base_branch,
        status: "pending",
      });
      await refreshTask();
    } catch (error: any) {
      showError(getErrorMessage(error, "Agent 任务重试失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const resetCompletedTask = async () => {
    if (!task) return;
    setLoadingAction("reset");
    try {
      await issueAgentTaskService.update(workspaceSlug, projectId, issueId, {
        repository_id: task.repository.id,
        base_branch: task.base_branch,
        status: "pending",
      });
      await refreshTask();
    } catch (error: any) {
      showError(getErrorMessage(error, "Agent 任务重置失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const cancelTask = async () => {
    setLoadingAction("cancel");
    try {
      await issueAgentTaskService.cancel(workspaceSlug, projectId, issueId);
      await refreshTask();
    } catch (error: any) {
      showError(getErrorMessage(error, "Agent 任务取消失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

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
        <h5 className="text-body-xs-medium">Agent</h5>
        {task && <IssueAgentTaskBadge task={task} />}
      </div>

      <SidebarPropertyListItem icon={Bot} label="仓库">
        <select
          className="h-7.5 w-full rounded bg-transparent px-2 text-body-xs-regular"
          value={repositoryId}
          disabled={isReadOnly}
          onChange={(e) => {
            setRepositoryId(e.target.value);
            setBaseBranch("");
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
            disabled={isReadOnly || !repositoryId}
            onChange={(e) => setBaseBranch(e.target.value)}
          >
            <option value="">选择分支</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.name}>
                {branch.name}
              </option>
            ))}
          </select>
          {!isReadOnly && isWorkspaceAdmin && (
            <Button variant="ghost" size="sm" onClick={syncBranches} loading={loadingAction === "sync"}>
              <RefreshCw className="size-3" />
            </Button>
          )}
        </div>
      </SidebarPropertyListItem>

      {task?.work_branch && (
        <div className="truncate px-2 text-caption text-secondary">工作分支：{task.work_branch}</div>
      )}

      {task?.pr_url && (
        <div className="flex items-center gap-1 px-2">
          <a className="min-w-0 truncate text-caption text-link-primary" href={task.pr_url} target="_blank" rel="noreferrer">
            {task.pr_url}
          </a>
          <ExternalLink className="size-3 shrink-0 text-secondary" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigator.clipboard?.writeText(task.pr_url ?? "")}
          >
            <Copy className="size-3" />
          </Button>
        </div>
      )}

      {task?.last_error && (
        <div className="mx-2 max-h-24 overflow-y-auto rounded border border-danger-subtle bg-danger-subtle px-2 py-1 text-caption text-danger-primary">
          {task.last_error}
        </div>
      )}

      {!task || task.status === "pending" || task.status === "cancelled" ? (
        <div className="flex gap-2 px-2">
          <Button variant="primary" size="sm" onClick={submitTask} loading={loadingAction === "submit"} disabled={!canSubmit}>
            {task?.status === "cancelled" ? "重新交给 Agent" : "交给 Agent 处理"}
          </Button>
          {task && (
            <Button variant="secondary" size="sm" onClick={cancelTask} loading={loadingAction === "cancel"} disabled={disabled}>
              取消
            </Button>
          )}
        </div>
      ) : null}

      {task?.status === "failed" && (
        <div className="flex gap-2 px-2">
          <Button variant="primary" size="sm" onClick={retryTask} loading={loadingAction === "retry"} disabled={disabled}>
            重试
          </Button>
          <Button variant="secondary" size="sm" onClick={cancelTask} loading={loadingAction === "cancel"} disabled={disabled}>
            取消
          </Button>
        </div>
      )}

      {canResetCompleted && (
        <div className="flex gap-2 px-2">
          <Button variant="secondary" size="sm" onClick={resetCompletedTask} loading={loadingAction === "reset"}>
            重置为等待中
          </Button>
        </div>
      )}
    </div>
  );
}
