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

## 构建并推送镜像

在构建机或 CI 上执行：

```bash
export PLANE_IMAGE_REGISTRY=registry.example.com/aidong
export PLANE_IMAGE_TAG=feishu-lark-$(date +%Y%m%d%H%M)

cp .env.custom.example .env.custom
sed -i "s|^PLANE_IMAGE_REGISTRY=.*|PLANE_IMAGE_REGISTRY=${PLANE_IMAGE_REGISTRY}|" .env.custom
sed -i "s|^PLANE_IMAGE_TAG=.*|PLANE_IMAGE_TAG=${PLANE_IMAGE_TAG}|" .env.custom

docker compose --env-file .env.custom -f docker-compose.custom.yml build \
  web admin space live api proxy

docker compose --env-file .env.custom -f docker-compose.custom.yml push \
  web admin space live api proxy
```

`worker`、`beat-worker`、`migrator`、`lark-connector` 共用 `plane-backend` 镜像，不需要单独构建。

## 生产升级

在生产服务器现有 Plane 部署目录执行。先备份数据库：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml exec -T plane-db \
  pg_dump -U "${POSTGRES_USER:-plane}" "${POSTGRES_DB:-plane}" > "plane-backup-$(date +%Y%m%d%H%M).sql"
```

拉取新镜像：

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml pull \
  web admin space live api proxy
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

如果启用飞书长连接，确认 `.env.custom` 包含：

```bash
COMPOSE_PROFILES=lark
IS_LARK_ENABLED=1
LARK_CONNECTOR_ENABLED=1
```

## 飞书后台配置

飞书开放平台只配置国内飞书：

- OAuth 回调：`https://<APP_DOMAIN>/auth/lark/callback/`
- Space OAuth 回调：`https://<APP_DOMAIN>/auth/spaces/lark/callback/`
- 事件订阅：启用长连接模式。
- 通讯录事件：启用用户和部门变更事件。

Plane 后台配置入口：

```text
https://<APP_DOMAIN>/god-mode/authentication/lark
```

在后台保存 App ID / App Secret 后，执行 Test connection，确认 tenant token 和通讯录 scope 可用。

## 验证

```bash
docker compose --env-file .env.custom -f docker-compose.custom.yml ps
docker compose --env-file .env.custom -f docker-compose.custom.yml logs --tail=200 api worker lark-connector
```

检查项：

- `api`、`worker`、`beat-worker`、`web`、`admin`、`space`、`live`、`proxy` 处于 running。
- `lark-connector` 在启用飞书时处于 running，且日志没有重复拿锁失败。
- 后台 `/god-mode/authentication/lark` 连接测试成功。
- Web 登录页出现 Feishu 登录入口。
- Workspace 成员页管理员可打开 Feishu 导入弹窗。

## 回滚

如果只需要回滚镜像：

```bash
vim .env.custom  # 把 PLANE_IMAGE_TAG 改回上一版
docker compose --env-file .env.custom -f docker-compose.custom.yml pull
docker compose --env-file .env.custom -f docker-compose.custom.yml up -d
```

如果数据库迁移后需要完全回滚，先停止服务，再用升级前备份恢复数据库。恢复前必须确认没有新数据需要保留。
