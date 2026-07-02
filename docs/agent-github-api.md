# Agent GitHub API

本文档描述 Agent 任务卡片标志、GitHub 凭证/仓库/分支管理 API，以及外部 Coding Agent 领取和写回任务的 API。

## 认证与权限

- App UI API 使用 Plane 登录态，路径前缀为 `/api/workspaces/...`。
- 外部 Agent API 使用 `X-Api-Key`，路径前缀为 `/api/v1/...`。
- 外部 Agent Token 必须是当前 workspace 下 `is_service=true` 的服务 Token。
- GitHub 凭证管理仅 Workspace Admin 可访问。
- 仓库和分支读取对活跃 workspace 成员开放，用于卡片选择。
- 卡片 Agent task 写入要求 Project Admin/Member；Guest 只读。
- 凭证响应永不返回 token 明文或加密密文，只返回 `token_last_four`。

## GitHub 凭证

### 获取凭证列表

```http
GET /api/workspaces/{slug}/github/credentials/
```

响应：

```json
[
  {
    "id": "credential-id",
    "name": "Aidong GitHub Bot",
    "provider": "github",
    "token_last_four": "abcd",
    "status": "active",
    "last_verified_at": "2026-07-02T10:00:00Z",
    "last_error": null,
    "created_at": "2026-07-02T09:58:00Z",
    "updated_at": "2026-07-02T10:00:00Z"
  }
]
```

### 新增凭证

```http
POST /api/workspaces/{slug}/github/credentials/
```

请求：

```json
{
  "name": "Aidong GitHub Bot",
  "token": "github_pat_xxx"
}
```

### 更新凭证

```http
PATCH /api/workspaces/{slug}/github/credentials/{credential_id}/
```

可更新 `name`，也可以重新提交 `token`。旧 token 不支持读取。

### 验证凭证

```http
POST /api/workspaces/{slug}/github/credentials/{credential_id}/verify/
```

验证失败时返回 `status=invalid` 和简短 `last_error`，不会返回 token 内容。

### 删除凭证

```http
DELETE /api/workspaces/{slug}/github/credentials/{credential_id}/
```

如果仍有手动仓库引用该凭证，返回 `409 Conflict`。

## GitHub 仓库

仓库来源：

- `github_app`：从现有 GitHub App repository sync 记录自动同步，只允许查看和刷新分支。
- `manual`：管理员手动新增，必须绑定凭证档案。

### 获取仓库列表

```http
GET /api/workspaces/{slug}/github/repositories/
```

响应：

```json
[
  {
    "id": "repository-id",
    "source": "manual",
    "owner": "aidong",
    "name": "plane",
    "full_name": "aidong/plane",
    "html_url": "https://github.com/aidong/plane",
    "default_branch": "main",
    "visibility": "private",
    "sync_status": "synced",
    "last_synced_at": "2026-07-02T10:00:00Z",
    "last_sync_error": null,
    "branch_count": 42
  }
]
```

### 新增手动仓库

```http
POST /api/workspaces/{slug}/github/repositories/
```

请求：

```json
{
  "source": "manual",
  "credential_profile_id": "credential-id",
  "owner": "aidong",
  "name": "plane",
  "html_url": "https://github.com/aidong/plane"
}
```

不允许通过该接口手动创建 `github_app` 来源仓库。

### 刷新分支

```http
POST /api/workspaces/{slug}/github/repositories/{repository_id}/sync-branches/
```

刷新失败只更新 `sync_status=failed` 和 `last_sync_error`，旧分支缓存保留。

### 获取分支

```http
GET /api/workspaces/{slug}/github/repositories/{repository_id}/branches/
```

响应：

```json
{
  "results": [
    {
      "id": "branch-id",
      "name": "main",
      "sha": "abc123",
      "protected": true,
      "is_default": true,
      "last_seen_at": "2026-07-02T10:00:00Z"
    }
  ]
}
```

## 卡片 AI Coding Agent 任务

### 获取任务配置

```http
GET /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/agent-task/
```

未配置时返回 `null`。

### 创建或更新任务

```http
PUT /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/agent-task/
PATCH /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/agent-task/
```

请求：

```json
{
  "repository_id": null,
  "base_branch": "",
  "status": "pending"
}
```

也可以在选择仓库和分支后写入完整目标：

```json
{
  "repository_id": "repository-id",
  "base_branch": "main",
  "status": "pending"
}
```

响应：

```json
{
  "id": "task-id",
  "status": "pending",
  "repository": {
    "id": "repository-id",
    "full_name": "aidong/plane",
    "html_url": "https://github.com/aidong/plane"
  },
  "base_branch": "main",
  "work_branch": null,
  "pr_url": null,
  "last_error": null,
  "claimed_by": null,
  "claimed_at": null,
  "completed_at": null,
  "retry_count": 0
}
```

规则：

- `status` 支持 `pending`、`running`、`completed`、`failed`、`cancelled`，卡片侧允许用户手动修改。
- `repository_id` 可以为空；为空时 `base_branch` 也必须为空。
- `repository_id` 不为空时，仓库必须属于当前 workspace。
- `base_branch` 不为空时，必须存在于该仓库的分支缓存。
- 未选择仓库/分支的 `pending` 任务只作为卡片标记保存，不会被外部 Agent 领取。
- `failed` 可重试，重试会把状态改回 `pending`、清空 `last_error`、`retry_count + 1`。
- `completed` 改成其他状态时会清空 PR、工作分支、完成时间和错误信息。

### 取消任务

```http
DELETE /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/agent-task/
```

卡片页面不再提供单独的取消按钮，推荐通过 `PATCH` 把 `status` 改为 `cancelled`。旧的 `DELETE` 接口仍会把任务标记为 `cancelled`，但 `running` 和 `completed` 任务不能通过 `DELETE` 取消。

## 外部 Agent API

所有请求必须携带：

```http
X-Api-Key: plane_api_xxx
```

### 领取任务

```http
POST /api/v1/workspaces/{slug}/agent/tasks/claim/
```

请求：

```json
{
  "agent_id": "coding-agent-01",
  "limit": 1
}
```

响应：

```json
{
  "results": [
    {
      "task_id": "task-id",
      "issue": {
        "id": "issue-id",
        "project_id": "project-id",
        "sequence_id": 123,
        "name": "Fix login error",
        "description_html": "<p>...</p>",
        "assignee_ids": ["user-id"]
      },
      "repository": {
        "id": "repository-id",
        "full_name": "aidong/plane",
        "html_url": "https://github.com/aidong/plane"
      },
      "base_branch": "main",
      "work_branch": "ai/WEB-123-fix-login-error"
    }
  ]
}
```

领取使用 `select_for_update(skip_locked=True)`，只领取 `pending` 且已配置仓库和目标分支的任务。领取成功后立即写入 `running`、`claimed_by`、`claimed_at`、`started_at` 和后端生成的 `work_branch`。

### 完成任务

```http
PATCH /api/v1/workspaces/{slug}/agent/tasks/{task_id}/
```

请求：

```json
{
  "status": "completed",
  "work_branch": "ai/WEB-123-fix-login-error",
  "pr_url": "https://github.com/aidong/plane/pull/456"
}
```

### 标记失败

```http
PATCH /api/v1/workspaces/{slug}/agent/tasks/{task_id}/
```

请求：

```json
{
  "status": "failed",
  "last_error": "Type check failed in packages/types/src/issues/issue.ts"
}
```

写回要求任务当前为 `running`。如果请求体携带 `agent_id`，必须与领取时的 `claimed_by` 一致。

错误码：

- `400`：状态非法、缺少必填字段或 PR URL 不合法。
- `401`：API Key 无效或缺失。
- `403`：API Key 不是当前 workspace 的服务 Token。
- `404`：任务不存在。
- `409`：任务不是运行中、已完成，或已被其他 Agent 领取。
