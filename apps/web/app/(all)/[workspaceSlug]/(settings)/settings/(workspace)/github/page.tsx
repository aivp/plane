/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR, { mutate } from "swr";
import { CheckCircle2, Loader2, Pencil, RefreshCw, Save, Trash2, X, XCircle } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TGithubCredentialProfile, TGithubManagedRepository } from "@plane/types";
import { Input } from "@plane/ui";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import {
  GITHUB_CREDENTIALS,
  GITHUB_MANAGED_REPOSITORIES,
} from "@/constants/fetch-keys";
import { useUserPermissions } from "@/hooks/store/user";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { GithubRepositoryService } from "@/services/integrations";
import type { Route } from "./+types/page";
import { GithubWorkspaceSettingsHeader } from "./header";

const githubRepositoryService = new GithubRepositoryService();

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.error ?? error?.data?.error ?? error?.message ?? fallback;

function GithubWorkspaceSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { currentWorkspace } = useWorkspace();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE, workspaceSlug);

  const [credentialName, setCredentialName] = useState("");
  const [credentialToken, setCredentialToken] = useState("");
  const [repositoryOwner, setRepositoryOwner] = useState("");
  const [repositoryName, setRepositoryName] = useState("");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [repositoryCredentialId, setRepositoryCredentialId] = useState("");
  const [editingCredentialId, setEditingCredentialId] = useState<string | null>(null);
  const [editingCredentialName, setEditingCredentialName] = useState("");
  const [editingCredentialToken, setEditingCredentialToken] = useState("");
  const [editingRepositoryId, setEditingRepositoryId] = useState<string | null>(null);
  const [editingRepositoryCredentialId, setEditingRepositoryCredentialId] = useState("");
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const { data: credentials = [] } = useSWR(
    isAdmin ? GITHUB_CREDENTIALS(workspaceSlug) : null,
    () => githubRepositoryService.listCredentials(workspaceSlug)
  );
  const { data: repositories = [] } = useSWR(
    isAdmin ? GITHUB_MANAGED_REPOSITORIES(workspaceSlug) : null,
    () => githubRepositoryService.listRepositories(workspaceSlug)
  );

  const latestSync = useMemo(
    () => {
      const syncedAtValues = repositories
        .map((repository) => repository.last_synced_at)
        .filter((value): value is string => Boolean(value))
        .sort();

      return syncedAtValues.length > 0 ? syncedAtValues[syncedAtValues.length - 1] : undefined;
    },
    [repositories]
  );
  const githubAppRepositoryCount = repositories.filter((repository) => repository.source === "github_app").length;

  const showError = (message: string) =>
    setToast({
      type: TOAST_TYPE.ERROR,
      title: "GitHub 操作失败",
      message,
    });

  const handleCreateCredential = async () => {
    if (!credentialName.trim() || !credentialToken.trim()) return;
    setLoadingAction("create-credential");
    try {
      const credential = await githubRepositoryService.createCredential(workspaceSlug, {
        name: credentialName.trim(),
        token: credentialToken.trim(),
      });
      const verifiedCredential = await githubRepositoryService.verifyCredential(workspaceSlug, credential.id);
      setCredentialName("");
      setCredentialToken("");
      await mutate(GITHUB_CREDENTIALS(workspaceSlug));

      if (verifiedCredential.status === "invalid") {
        showError(verifiedCredential.last_error ?? "凭证验证失败。");
        return;
      }

      setToast({ type: TOAST_TYPE.SUCCESS, title: "凭证已保存", message: "GitHub 凭证已验证。" });
    } catch (error: any) {
      showError(getErrorMessage(error, "凭证保存失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleCreateRepository = async () => {
    if (!repositoryOwner.trim() || !repositoryName.trim() || !repositoryCredentialId) return;
    setLoadingAction("create-repository");
    try {
      const repository = await githubRepositoryService.createRepository(workspaceSlug, {
        source: "manual",
        credential_profile_id: repositoryCredentialId,
        owner: repositoryOwner.trim(),
        name: repositoryName.trim(),
        html_url: repositoryUrl.trim() || null,
      });
      await githubRepositoryService.syncBranches(workspaceSlug, repository.id);
      setRepositoryOwner("");
      setRepositoryName("");
      setRepositoryUrl("");
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
      setToast({ type: TOAST_TYPE.SUCCESS, title: "仓库已添加", message: "分支信息已同步。" });
    } catch (error: any) {
      showError(getErrorMessage(error, "仓库保存失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const refreshRepository = async (repositoryId: string) => {
    setLoadingAction(`sync-${repositoryId}`);
    try {
      await githubRepositoryService.syncBranches(workspaceSlug, repositoryId);
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
    } catch (error: any) {
      showError(getErrorMessage(error, "分支同步失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const verifyCredential = async (credentialId: string) => {
    setLoadingAction(`verify-${credentialId}`);
    try {
      const credential = await githubRepositoryService.verifyCredential(workspaceSlug, credentialId);
      await mutate(GITHUB_CREDENTIALS(workspaceSlug));
      if (credential.status === "invalid") {
        showError(credential.last_error ?? "凭证验证失败。");
      }
    } catch (error: any) {
      showError(getErrorMessage(error, "凭证验证失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const startEditingCredential = (credential: TGithubCredentialProfile) => {
    setEditingCredentialId(credential.id);
    setEditingCredentialName(credential.name);
    setEditingCredentialToken("");
  };

  const updateCredential = async () => {
    if (!editingCredentialId || !editingCredentialName.trim()) return;
    setLoadingAction(`update-credential-${editingCredentialId}`);
    try {
      const shouldVerify = Boolean(editingCredentialToken.trim());
      await githubRepositoryService.updateCredential(workspaceSlug, editingCredentialId, {
        name: editingCredentialName.trim(),
        ...(editingCredentialToken.trim() ? { token: editingCredentialToken.trim() } : {}),
      });
      const verifiedCredential = shouldVerify
        ? await githubRepositoryService.verifyCredential(workspaceSlug, editingCredentialId)
        : null;
      setEditingCredentialId(null);
      setEditingCredentialName("");
      setEditingCredentialToken("");
      await mutate(GITHUB_CREDENTIALS(workspaceSlug));
      if (verifiedCredential?.status === "invalid") {
        showError(verifiedCredential.last_error ?? "凭证验证失败。");
        return;
      }
      setToast({ type: TOAST_TYPE.SUCCESS, title: "凭证已更新", message: "凭证档案已保存。" });
    } catch (error: any) {
      showError(getErrorMessage(error, "凭证更新失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const deleteCredential = async (credentialId: string) => {
    setLoadingAction(`delete-credential-${credentialId}`);
    try {
      await githubRepositoryService.deleteCredential(workspaceSlug, credentialId);
      await mutate(GITHUB_CREDENTIALS(workspaceSlug));
    } catch (error: any) {
      showError(getErrorMessage(error, "凭证删除失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const deleteRepository = async (repositoryId: string) => {
    setLoadingAction(`delete-repository-${repositoryId}`);
    try {
      await githubRepositoryService.deleteRepository(workspaceSlug, repositoryId);
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
    } catch (error: any) {
      showError(getErrorMessage(error, "仓库删除失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const startEditingRepository = (repository: TGithubManagedRepository) => {
    setEditingRepositoryId(repository.id);
    setEditingRepositoryCredentialId("");
  };

  const updateRepositoryCredential = async () => {
    if (!editingRepositoryId || !editingRepositoryCredentialId) return;
    setLoadingAction(`update-repository-${editingRepositoryId}`);
    try {
      await githubRepositoryService.updateRepository(workspaceSlug, editingRepositoryId, {
        credential_profile_id: editingRepositoryCredentialId,
      });
      setEditingRepositoryId(null);
      setEditingRepositoryCredentialId("");
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
      setToast({ type: TOAST_TYPE.SUCCESS, title: "仓库已更新", message: "绑定凭证已变更。" });
    } catch (error: any) {
      showError(getErrorMessage(error, "仓库更新失败。"));
    } finally {
      setLoadingAction(null);
    }
  };

  const refreshAllRepositories = async () => {
    if (repositories.length === 0) return;

    setLoadingAction("sync-all");
    try {
      await Promise.all(repositories.map((repository) => githubRepositoryService.syncBranches(workspaceSlug, repository.id)));
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
      setToast({ type: TOAST_TYPE.SUCCESS, title: "刷新完成", message: "仓库分支信息已更新。" });
    } catch (error: any) {
      showError(getErrorMessage(error, "部分仓库分支同步失败。"));
      await mutate(GITHUB_MANAGED_REPOSITORIES(workspaceSlug));
    } finally {
      setLoadingAction(null);
    }
  };

  if (workspaceUserInfo && !isAdmin) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <SettingsContentWrapper header={<GithubWorkspaceSettingsHeader />}>
      <PageHead title={currentWorkspace?.name ? `${currentWorkspace.name} - GitHub` : undefined} />
      <div className="w-full space-y-8">
        <SettingsHeading
          title="GitHub"
          description="维护 Agent 任务可选择的 GitHub 凭证、仓库目录和分支缓存。"
          control={
            <Button
              variant="secondary"
              onClick={refreshAllRepositories}
              disabled={repositories.length === 0 || !!loadingAction}
              loading={loadingAction === "sync-all"}
            >
              <RefreshCw className="mr-2 size-3.5" />
              全部刷新
            </Button>
          }
        />

        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <SummaryItem label="凭证档案" value={credentials.length.toString()} />
          <SummaryItem label="仓库数量" value={repositories.length.toString()} />
          <SummaryItem label="GitHub App" value={`${githubAppRepositoryCount} 个仓库`} />
          <SummaryItem label="最近同步" value={latestSync ? new Date(latestSync).toLocaleString() : "从未同步"} />
        </div>

        <section className="space-y-3">
          <div>
            <h3 className="text-body-sm-medium">凭证档案</h3>
            <p className="text-body-xs-regular text-secondary">Token 加密保存，前端只展示末尾四位。</p>
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1.4fr_auto]">
            <Input value={credentialName} onChange={(e) => setCredentialName(e.target.value)} placeholder="凭证名称" />
            <Input
              type="password"
              value={credentialToken}
              onChange={(e) => setCredentialToken(e.target.value)}
              placeholder="GitHub token"
            />
            <Button
              variant="primary"
              onClick={handleCreateCredential}
              loading={loadingAction === "create-credential"}
              disabled={!credentialName.trim() || !credentialToken.trim()}
            >
              验证并保存
            </Button>
          </div>
          <div className="overflow-hidden rounded border border-subtle">
            {credentials.length === 0 ? (
              <EmptyRow text="还没有凭证档案。" />
            ) : (
              credentials.map((credential) => (
                <div key={credential.id} className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3 border-b border-subtle px-3 py-2 last:border-b-0">
                  <div className="min-w-0">
                    {editingCredentialId === credential.id ? (
                      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                        <Input
                          value={editingCredentialName}
                          onChange={(e) => setEditingCredentialName(e.target.value)}
                          placeholder="凭证名称"
                        />
                        <Input
                          type="password"
                          value={editingCredentialToken}
                          onChange={(e) => setEditingCredentialToken(e.target.value)}
                          placeholder="重新粘贴 token，可留空"
                        />
                      </div>
                    ) : (
                      <>
                        <div className="truncate text-body-xs-medium">{credential.name}</div>
                        <div className="text-caption text-secondary">Token 尾号 {credential.token_last_four || "无"}</div>
                      </>
                    )}
                  </div>
                  <StatusPill status={credential.status} />
                  {editingCredentialId === credential.id ? (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={updateCredential}
                        loading={loadingAction === `update-credential-${credential.id}`}
                      >
                        <Save className="size-3.5" />
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => verifyCredential(credential.id)}
                      loading={loadingAction === `verify-${credential.id}`}
                    >
                      验证
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      editingCredentialId === credential.id
                        ? setEditingCredentialId(null)
                        : startEditingCredential(credential)
                    }
                    disabled={loadingAction === `delete-credential-${credential.id}`}
                  >
                    {editingCredentialId === credential.id ? <X className="size-3.5" /> : <Pencil className="size-3.5" />}
                  </Button>
                  {editingCredentialId !== credential.id && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteCredential(credential.id)}
                      loading={loadingAction === `delete-credential-${credential.id}`}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="space-y-3">
          <div>
            <h3 className="text-body-sm-medium">仓库目录</h3>
            <p className="text-body-xs-regular text-secondary">卡片只能选择目录中的仓库和已缓存分支。</p>
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_1.4fr_1.2fr_auto]">
            <Input value={repositoryOwner} onChange={(e) => setRepositoryOwner(e.target.value)} placeholder="Owner" />
            <Input value={repositoryName} onChange={(e) => setRepositoryName(e.target.value)} placeholder="仓库名" />
            <Input value={repositoryUrl} onChange={(e) => setRepositoryUrl(e.target.value)} placeholder="https://github.com/owner/repo" />
            <select
              className="h-9 rounded border border-subtle bg-surface-1 px-3 text-body-xs-regular"
              value={repositoryCredentialId}
              onChange={(e) => setRepositoryCredentialId(e.target.value)}
            >
              <option value="">选择凭证</option>
              {credentials.map((credential) => (
                <option key={credential.id} value={credential.id}>
                  {credential.name}
                </option>
              ))}
            </select>
            <Button
              variant="primary"
              onClick={handleCreateRepository}
              loading={loadingAction === "create-repository"}
              disabled={!repositoryOwner.trim() || !repositoryName.trim() || !repositoryCredentialId}
            >
              添加
            </Button>
          </div>
          <div className="overflow-hidden rounded border border-subtle">
            {repositories.length === 0 ? (
              <EmptyRow text="还没有仓库。请先安装 GitHub App 或新增手动仓库。" />
            ) : (
              repositories.map((repository) => (
                <div key={repository.id} className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3 border-b border-subtle px-3 py-2 last:border-b-0">
                  <div className="min-w-0">
                    <div className="truncate text-body-xs-medium">{repository.full_name}</div>
                    <div className="truncate text-caption text-secondary">
                      {repository.source} · 默认 {repository.default_branch || "未知"} · {repository.branch_count ?? 0} 个分支
                    </div>
                    {repository.last_sync_error && <div className="truncate text-caption text-danger-primary">{repository.last_sync_error}</div>}
                    {editingRepositoryId === repository.id && (
                      <select
                        className="mt-2 h-8 w-full rounded border border-subtle bg-surface-1 px-2 text-body-xs-regular"
                        value={editingRepositoryCredentialId}
                        onChange={(e) => setEditingRepositoryCredentialId(e.target.value)}
                      >
                        <option value="">选择新的绑定凭证</option>
                        {credentials.map((credential) => (
                          <option key={credential.id} value={credential.id}>
                            {credential.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                  <StatusPill status={repository.sync_status} />
                  <Button variant="ghost" size="sm" onClick={() => refreshRepository(repository.id)} loading={loadingAction === `sync-${repository.id}`}>
                    <RefreshCw className="size-3.5" />
                  </Button>
                  {repository.source === "manual" && (
                    <>
                      {editingRepositoryId === repository.id ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={updateRepositoryCredential}
                          loading={loadingAction === `update-repository-${repository.id}`}
                          disabled={!editingRepositoryCredentialId}
                        >
                          <Save className="size-3.5" />
                        </Button>
                      ) : (
                        <Button variant="ghost" size="sm" onClick={() => startEditingRepository(repository)}>
                          <Pencil className="size-3.5" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          editingRepositoryId === repository.id
                            ? setEditingRepositoryId(null)
                            : deleteRepository(repository.id)
                        }
                        loading={loadingAction === `delete-repository-${repository.id}`}
                      >
                        {editingRepositoryId === repository.id ? <X className="size-3.5" /> : <Trash2 className="size-3.5" />}
                      </Button>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </SettingsContentWrapper>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-subtle bg-surface-1 p-3">
      <div className="text-caption text-secondary">{label}</div>
      <div className="mt-1 truncate text-body-sm-medium">{value}</div>
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <div className="px-3 py-8 text-center text-body-xs-regular text-secondary">{text}</div>;
}

function StatusPill({ status }: { status: string }) {
  const isGood = ["active", "synced"].includes(status);
  const isLoading = ["pending", "syncing"].includes(status);
  const Icon = isLoading ? Loader2 : isGood ? CheckCircle2 : XCircle;
  return (
    <span className="inline-flex items-center gap-1 rounded border border-subtle px-2 py-1 text-caption capitalize text-secondary">
      <Icon className={`size-3 ${isLoading ? "animate-spin" : isGood ? "text-success-primary" : "text-danger-primary"}`} />
      {status}
    </span>
  );
}

export default observer(GithubWorkspaceSettingsPage);
