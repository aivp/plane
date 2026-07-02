# AI Coding Agent Plane API

本文档只描述外部 AI Coding Agent 需要调用的 Plane API，用于从 Plane 领取待处理卡片，并把 PR 或错误信息写回 Plane。

本文档不包含 GitHub 凭证、GitHub 仓库、GitHub 分支管理 API。Agent 如需访问 GitHub，应使用自身运行环境中的 GitHub 凭证或独立配置；Plane 只向 Agent 提供任务上下文和写回入口。

## 生产环境地址

当前部署环境：

```text
https://plane.aidong-ai.com
```

Workspace slug：

```text
aidong
```

完整 API 地址：

```http
GET https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/
POST https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/{issue_id}/claim/
PATCH https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/{issue_id}/
```

## 认证

所有 Agent API 路径前缀为 `/api/v1/...`，请求必须携带有效 Plane API Key：

```http
X-Api-Key: plane_api_xxx
```

支持两类 Token：

- Workspace 服务 Token：`is_service=true`，且绑定当前 workspace。
- 个人 Token：`is_service=false`，且 Token 所属用户必须是当前 workspace 的活跃成员。

通用要求：

- Token 必须处于启用状态。
- Token 不能过期。
- 不要把真实 API Key 提交到文档或代码仓库；示例统一使用 `plane_api_xxx` 占位。

错误：

- `401`：API Key 缺失或认证失败。
- `403`：API Key 不属于当前 workspace，或个人 Token 所属用户不是当前 workspace 的活跃成员。

## 状态语义

Agent 只处理 `pending` 任务，并只允许写回 `completed` 或 `failed`。

```text
pending    等待中，可被 Agent 领取
running    执行中，已被 Agent 领取
completed  已完成，Agent 已写回 PR
failed     失败，Agent 已写回错误信息
cancelled  已取消，不会被 Agent 领取
```

只读列表不会修改状态。只有领取单个 issue 成功后，Plane 才会把状态从 `pending` 更新为 `running`。

## 获取匹配 Issue

```http
GET /api/v1/workspaces/{slug}/agent/issues/
```

用途：获取当前匹配的 AI Coding Agent issue 列表，不修改任何状态。

默认筛选：

- Agent 状态为 `pending`。
- 已配置 `repository`。
- 已配置 `base_branch`。

查询参数：

```text
status        可选，默认 pending。支持 pending/running/completed/failed/cancelled。
project_id    可选，按项目过滤。
repository_id 可选，按仓库过滤。
base_branch   可选，按目标分支过滤。
ready         可选，默认 true。为 false 时不强制要求 repository/base_branch 完整。
limit         可选，默认 100，范围 1..100。
```

响应：

```json
{
  "results": [
    {
      "issue": {
        "id": "issue-id",
        "project_id": "project-id",
        "sequence_id": 123,
        "name": "Fix login error",
        "description_html": "<p>...</p>",
        "assignee_ids": ["user-id"],
        "comments": [
          {
            "id": "comment-id",
            "comment_html": "<p>需要同时检查筛选项。</p>",
            "comment_stripped": "需要同时检查筛选项。",
            "comment_json": {},
            "attachments": [],
            "access": "INTERNAL",
            "actor": "user-id",
            "actor_detail": {
              "id": "user-id",
              "display_name": "Owner"
            },
            "comment_reactions": [],
            "created_at": "2026-07-02T10:00:00Z",
            "updated_at": "2026-07-02T10:00:00Z"
          }
        ]
      },
      "status": "pending",
      "repository": {
        "id": "repository-id",
        "full_name": "aidong/plane",
        "html_url": "https://github.com/aidong/plane"
      },
      "base_branch": "main",
      "work_branch": null
    }
  ]
}
```

没有匹配 issue 时：

```json
{
  "results": []
}
```

列表规则：

- `GET` 只是候选快照，不做并发锁定，不保证返回后仍可领取。
- Agent 应从列表中选择一个 `issue.id`，再调用单个 issue 的领取接口。
- 如果领取时返回 `409`，说明该 issue 已被其他 Agent 领取或状态已变化，应跳过并选择下一个。
- `issue.comments` 返回该 issue 的全部评论，按 `created_at` 升序排列，字段结构复用 Plane 的 `IssueCommentSerializer`。

## 领取单个 Issue

```http
POST /api/v1/workspaces/{slug}/agent/issues/{issue_id}/claim/
```

用途：领取指定 issue。只有这个接口会修改状态。

请求：

```json
{
  "agent_id": "coding-agent-01"
}
```

字段说明：

- `agent_id`：必填，调用方 Agent 实例标识。Plane 会写入 `claimed_by`。

响应：

```json
{
  "issue": {
    "id": "issue-id",
    "project_id": "project-id",
    "sequence_id": 123,
    "name": "Fix login error",
    "description_html": "<p>...</p>",
    "assignee_ids": ["user-id"],
    "comments": [
      {
        "id": "comment-id",
        "comment_html": "<p>需要同时检查筛选项。</p>",
        "comment_stripped": "需要同时检查筛选项。",
        "comment_json": {},
        "attachments": [],
        "access": "INTERNAL",
        "actor": "user-id",
        "actor_detail": {
          "id": "user-id",
          "display_name": "Owner"
        },
        "comment_reactions": [],
        "created_at": "2026-07-02T10:00:00Z",
        "updated_at": "2026-07-02T10:00:00Z"
      }
    ]
  },
  "status": "running",
  "repository": {
    "id": "repository-id",
    "full_name": "aidong/plane",
    "html_url": "https://github.com/aidong/plane"
  },
  "base_branch": "main",
  "work_branch": "ai/WEB-123-fix-login-error"
}
```

领取规则：

- 只允许领取 Agent 状态为 `pending` 的 issue。
- 只允许领取已配置 `repository` 和 `base_branch` 的 issue。
- `issue.comments` 返回该 issue 的全部评论，按 `created_at` 升序排列，字段结构复用 Plane 的 `IssueCommentSerializer`。
- 后端使用 `select_for_update` 原子领取，避免多个 Agent 领取同一个 issue。
- 领取时 Plane 会写入 `running`、`claimed_by`、`claimed_at`、`started_at`。
- `work_branch` 由 Plane 生成，格式为 `ai/{project_identifier}-{sequence_id}-{slug}`。

## 写回 Issue

```http
PATCH /api/v1/workspaces/{slug}/agent/issues/{issue_id}/
```

写回要求：

- `issue_id` 必须属于当前 workspace。
- 该 issue 必须已经配置 AI Coding Agent 状态。
- issue 当前 Agent 状态必须是 `running`。
- 如果请求体携带 `agent_id`，必须与领取时的 `claimed_by` 一致。
- 已完成 issue 不能再次通过 Agent API 写回。

### 写回完成

请求：

```json
{
  "agent_id": "coding-agent-01",
  "status": "completed",
  "work_branch": "ai/WEB-123-fix-login-error",
  "pr_url": "https://github.com/aidong/plane/pull/456"
}
```

字段说明：

- `status`：必填，必须是 `completed`。
- `pr_url`：必填，必须是合法 URL。
- `work_branch`：可选；如果传入，会覆盖领取时生成的工作分支。
- `agent_id`：建议传入，用于防止其他 Agent 误写回当前任务。

成功后 Plane 会：

- 保存 `pr_url`。
- 清空 `last_error`。
- 写入 `completed_at`。
- 创建 issue activity。
- 通知负责人。

响应：

```json
{
  "issue": {
    "id": "issue-id",
    "project_id": "project-id",
    "sequence_id": 123,
    "name": "Fix login error",
    "description_html": "<p>...</p>",
    "assignee_ids": ["user-id"],
    "comments": [
      {
        "id": "comment-id",
        "comment_html": "<p>需要同时检查筛选项。</p>",
        "comment_stripped": "需要同时检查筛选项。",
        "comment_json": {},
        "attachments": [],
        "access": "INTERNAL",
        "actor": "user-id",
        "actor_detail": {
          "id": "user-id",
          "display_name": "Owner"
        },
        "comment_reactions": [],
        "created_at": "2026-07-02T10:00:00Z",
        "updated_at": "2026-07-02T10:00:00Z"
      }
    ]
  },
  "status": "completed",
  "repository": {
    "id": "repository-id",
    "full_name": "aidong/plane",
    "html_url": "https://github.com/aidong/plane"
  },
  "base_branch": "main",
  "work_branch": "ai/WEB-123-fix-login-error"
}
```

### 写回失败

请求：

```json
{
  "agent_id": "coding-agent-01",
  "status": "failed",
  "last_error": "Type check failed in packages/types/src/issues/issue.ts"
}
```

字段说明：

- `status`：必填，必须是 `failed`。
- `last_error`：必填，保存给负责人查看的错误摘要。
- `agent_id`：建议传入，用于防止其他 Agent 误写回当前任务。

成功后 Plane 会：

- 保存 `last_error`。
- 清空 `completed_at`。
- 创建 issue activity。
- 通知负责人。

## 错误码

- `400`：请求字段缺失、状态非法、`limit` 非数字、`pr_url` 不合法。
- `401`：API Key 缺失或认证失败。
- `403`：API Key 不允许访问当前 workspace。
- `404`：issue 不存在，或该 issue 没有 AI Coding Agent 状态记录。
- `409`：issue Agent 状态不是 `running`、已完成，或已被其他 Agent 领取。

## cURL 示例

获取匹配 issue：

```bash
curl -X GET "https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/?status=pending&limit=100" \
  -H "X-Api-Key: plane_api_xxx"
```

领取单个 issue：

```bash
curl -X POST "https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/issue-id/claim/" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: plane_api_xxx" \
  -d '{
    "agent_id": "coding-agent-01"
  }'
```

写回 PR：

```bash
curl -X PATCH "https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/issue-id/" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: plane_api_xxx" \
  -d '{
    "agent_id": "coding-agent-01",
    "status": "completed",
    "work_branch": "ai/WEB-123-fix-login-error",
    "pr_url": "https://github.com/aidong/plane/pull/456"
  }'
```

写回失败：

```bash
curl -X PATCH "https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/issue-id/" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: plane_api_xxx" \
  -d '{
    "agent_id": "coding-agent-01",
    "status": "failed",
    "last_error": "Type check failed in packages/types/src/issues/issue.ts"
  }'
```

可用性测试：

```bash
curl -X PATCH "https://plane.aidong-ai.com/api/v1/workspaces/aidong/agent/issues/00000000-0000-0000-0000-000000000000/" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: plane_api_xxx" \
  -d '{
    "agent_id": "coding-agent-smoke-test",
    "status": "failed",
    "last_error": "smoke test"
  }'
```

预期结果：

- `404 Issue agent state not found.`：认证、workspace 权限和路由正常，只是测试 issue 不存在或没有 AI Coding Agent 状态记录。
- `403 Token is not allowed for this workspace.`：API Key 有效，但不允许访问 `aidong` workspace。服务 Token 需要绑定该 workspace；个人 Token 所属用户需要是该 workspace 活跃成员。
- `403 Given API token is not valid`：API Key 无效、过期或已停用。
