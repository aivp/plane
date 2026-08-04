# 自定义镜像 Docker Compose 升级手册

本文档给运维使用，用于从官方 `makeplane/*` 镜像部署切换到本仓库修改后的自定义镜像部署。

## 文件

- `docker-compose.custom.yml`：独立部署文件，不依赖官方 Plane 应用镜像。
- `.env.custom.example`：自定义部署环境变量模板。

生产环境建议把这两个文件放到现有 Plane 部署目录，并保持 `COMPOSE_PROJECT_NAME=plane`。如果项目名变了，Docker volume 名也会变，旧数据库卷不会被自动复用。

## 一次性准备

```bash
cp .env.custom.example .env.custom
vim .env.custom
```

必须修改：

- `APP_DOMAIN`
- `PLANE_IMAGE_REGISTRY`
- `PLANE_IMAGE_TAG`
- `PLANE_IMAGE_PULL_POLICY`
- `SECRET_KEY`
- `LIVE_SERVER_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `RABBITMQ_PASSWORD`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `LARK_CLIENT_ID` / `LARK_CLIENT_SECRET`
- `LARK_DEFAULT_WORKSPACE_SLUG`

国内构建建议保留：

```bash
NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
LARK_BASE_DOMAIN=feishu.cn
```

如果在生产服务器直接从当前源码构建部署，使用：

```bash
PLANE_IMAGE_REGISTRY=local
PLANE_IMAGE_PULL_POLICY=never
```

如果由 CI 构建并推送到私有镜像仓库，生产服务器只拉镜像，使用：

```bash
PLANE_IMAGE_REGISTRY=registry.example.com/aidong
PLANE_IMAGE_PULL_POLICY=always
```

## 方式一：生产服务器直接构建部署

适合单机部署或运维直接拿源码包上线。

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml build \
  web admin space live api mcp proxy
```

`worker`、`beat-worker`、`migrator`、`lark-connector` 共用 `plane-backend` 镜像，不需要单独构建。

然后按下面的“生产升级”执行迁移和启动。此方式不要执行 `docker compose pull`。

## 方式二：CI 构建并推送镜像

在构建机或 CI 上执行：

```bash
export PLANE_IMAGE_REGISTRY=registry.example.com/aidong
export PLANE_IMAGE_TAG=feishu-lark-$(date +%Y%m%d%H%M)
export PLANE_IMAGE_PULL_POLICY=never

cp .env.custom.example .env.custom
sed -i "s|^PLANE_IMAGE_REGISTRY=.*|PLANE_IMAGE_REGISTRY=${PLANE_IMAGE_REGISTRY}|" .env.custom
sed -i "s|^PLANE_IMAGE_TAG=.*|PLANE_IMAGE_TAG=${PLANE_IMAGE_TAG}|" .env.custom
sed -i "s|^PLANE_IMAGE_PULL_POLICY=.*|PLANE_IMAGE_PULL_POLICY=${PLANE_IMAGE_PULL_POLICY}|" .env.custom

docker compose --env-file .env.custom -f docker-compose.custom.yml build \
  web admin space live api mcp proxy

docker compose --env-file .env.custom -f docker-compose.custom.yml push \
  web admin space live api mcp proxy
```

`worker`、`beat-worker`、`migrator`、`lark-connector` 共用 `plane-backend` 镜像，不需要单独构建。

## 生产升级

在生产服务器现有 Plane 部署目录执行。先备份数据库：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml exec -T plane-db \
  pg_dump -U "${POSTGRES_USER:-plane}" "${POSTGRES_DB:-plane}" > "plane-backup-$(date +%Y%m%d%H%M).sql"
```

如果生产服务器使用私有镜像仓库，拉取新镜像：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml pull \
  web admin space live api mcp proxy
```

如果生产服务器直接构建镜像，跳过 pull，改为确认镜像已构建：

```bash
docker images | grep plane-
```

执行数据库迁移：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml up -d plane-db plane-redis plane-mq plane-minio
docker compose --env-file .env.custom -f docker-compose.custom.yml --profile migration run --rm migrator
```

启动服务：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml up -d
```

飞书登录和主动通知不需要启动 `lark-connector`。保留以下配置即可：

```bash
IS_LARK_ENABLED=1
LARK_NOTIFICATIONS_ENABLED=1
LARK_CONNECTOR_ENABLED=0
```

如果之后需要启用飞书事件订阅长连接，再额外确认 `.env.custom` 包含：

```bash
COMPOSE_PROFILES=lark-connector
LARK_CONNECTOR_ENABLED=1
```

## 飞书后台配置

飞书开放平台只配置国内飞书。未启用长连接时，可以先不配置事件订阅：

- OAuth 回调：`https://<APP_DOMAIN>/auth/lark/callback/`
- Space OAuth 回调：`https://<APP_DOMAIN>/auth/spaces/lark/callback/`
- 事件订阅：仅启用 `lark-connector` 时配置长连接模式。
- 通讯录事件：仅启用 `lark-connector` 时配置用户和部门变更事件。

Plane 后台配置入口：

```text
https://<APP_DOMAIN>/god-mode/authentication/lark
```

在后台保存 App ID / App Secret 后，执行 Test connection，确认 tenant token 和通讯录 scope 可用。

## Remote MCP

`mcp` 服务默认随 Compose 启动，由 Caddy 暴露在 `https://<APP_DOMAIN>/mcp`。部署端不配置、保存或固定任何 Plane API Key、Workspace Slug 或 Plane Host，也不需要 OAuth Client。

推荐调用方在每次 MCP HTTP 请求中发送三个 Header：

```text
X-Plane-Api-Key: <调用方的 API Key>
X-Plane-Workspace-Slug: <调用方的 Workspace Slug>
X-Plane-Api-Host-Url: https://<调用方的 Plane 域名>
```

只支持可解析到公网 IP 的 HTTPS Plane 根地址；不接受路径、查询参数、本机或私网地址。这是为了防止公开 MCP 入口被滥用为 SSRF/内网探测代理。

只支持 stdio MCP 的客户端可使用 `mcp-remote`。以下配置正好只需要设置三个调用方参数：

```json
{
  "mcpServers": {
    "plane": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://plane.aidong-ai.com/mcp",
        "--header",
        "X-Plane-Api-Key:${PLANE_API_KEY}",
        "--header",
        "X-Plane-Workspace-Slug:${PLANE_WORKSPACE_SLUG}",
        "--header",
        "X-Plane-Api-Host-Url:${PLANE_API_HOST_URL}"
      ],
      "env": {
        "PLANE_API_KEY": "<你的 API_KEY>",
        "PLANE_WORKSPACE_SLUG": "aidong",
        "PLANE_API_HOST_URL": "https://plane.aidong-ai.com"
      }
    }
  }
}
```

`mcp-remote` 的 `--header` 和环境变量替换语法见其[官方说明](https://github.com/geelen/mcp-remote#custom-headers)。API Key 应只放在调用方的密钥配置中，不要提交到仓库。

### 原生 Streamable HTTP 与 Query 兼容模式

原生支持 Remote MCP 的客户端应直接使用 `streamable-http` 连接，不需要 `mcp-remote`：

```json
{
  "mcpServers": {
    "plane": {
      "type": "streamable-http",
      "url": "https://plane.aidong-ai.com/mcp",
      "headers": {
        "X-Plane-Api-Key": "<你的 API_KEY>",
        "X-Plane-Workspace-Slug": "aidong",
        "X-Plane-Api-Host-Url": "https://plane.aidong-ai.com"
      }
    }
  }
}
```

如果调用平台不能发送自定义 Header，可使用 Query String 兼容模式：

```json
{
  "mcpServers": {
    "plane": {
      "type": "streamable-http",
      "url": "https://plane.aidong-ai.com/mcp?PLANE_API_KEY=<URL编码后的API_KEY>&PLANE_WORKSPACE_SLUG=aidong"
    }
  }
}
```

当 Plane API 与 MCP 使用同一个域名时，可以省略 `PLANE_API_HOST_URL`，网关会从当前 MCP 请求推导 `https://plane.aidong-ai.com`。如果目标 Plane 是其它域名，再增加 URL 编码后的 `PLANE_API_HOST_URL`：

```text
&PLANE_API_HOST_URL=https%3A%2F%2Fother-plane.example.com
```

Query 参数名不区分大小写，也可写成 `plane_api_key`、`plane_workspace_slug` 和 `plane_api_host_url`。Header 和 Query 同时出现时必须值相同，否则请求会被拒绝。

> 安全提示：URL Query 可能被客户端、CDN、反向代理或 APM 记录。MCP 容器已关闭 Uvicorn access log，但无法控制外部平台日志；支持 Header 时仍应优先使用 Header。不要把含真实 API Key 的完整 URL 提交到仓库、工单或聊天记录。

## 验证

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml ps
docker compose --env-file .env.custom -f docker-compose.custom.yml logs --tail=200 api worker mcp
curl -fsS "https://${APP_DOMAIN}/mcp/healthz"
```

启用长连接时，再查看 `lark-connector` 日志：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml logs --tail=200 lark-connector
```

检查项：

- `api`、`worker`、`beat-worker`、`web`、`admin`、`space`、`live`、`mcp`、`proxy` 处于 running。
- `https://<APP_DOMAIN>/mcp/healthz` 返回 `{"status":"ok"}`。
- 未启用长连接时，`lark-connector` 不应出现在 running 服务中。
- 启用长连接时，`lark-connector` 处于 running，且日志没有重复拿锁失败。
- 后台 `/god-mode/authentication/lark` 连接测试成功。
- Web 登录页出现 Feishu 登录入口。
- Workspace 成员页管理员可打开 Feishu 导入弹窗。

## 回滚

如果只需要回滚镜像：

```bash
vim .env.custom  # 把 PLANE_IMAGE_TAG 改回上一版
docker compose --env-file .env.custom -f docker-compose.custom.yml pull  # 私有仓库方式需要；本机构建方式跳过
docker compose --env-file .env.custom -f docker-compose.custom.yml up -d
```

如果数据库迁移后需要完全回滚，先停止服务，再用升级前备份恢复数据库。恢复前必须确认没有新数据需要保留。
