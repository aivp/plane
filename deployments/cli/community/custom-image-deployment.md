# 自建镜像部署说明

当前服务器之前使用 Plane 官方镜像 `makeplane/plane-*:${APP_RELEASE}` 通过 Docker Compose 部署；本次需要部署本地 checkout 的 PR 代码，因此改为使用自建镜像。


## 1. 业务镜像清单

业务镜像清单：

```text
plane-frontend:xxx
plane-admin:xxx
plane-space:xxx
plane-live:xxx
plane-backend:xxx
plane-proxy:xxx
```

`api`、`worker`、`beat-worker`、`migrator` 都使用同一个 `plane-backend` 镜像，必须保持同一个 tag。

## 2. 变更点

不要直接修改官方 `docker-compose.yaml` 主文件。把 `docker-compose.pr.yml` 放到官方 compose 同目录，通过多文件叠加方式部署。

官方镜像会被替换为：

```text
web         -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-frontend:${PLANE_CUSTOM_IMAGE_TAG}
admin       -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-admin:${PLANE_CUSTOM_IMAGE_TAG}
space       -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-space:${PLANE_CUSTOM_IMAGE_TAG}
live        -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-live:${PLANE_CUSTOM_IMAGE_TAG}
proxy       -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-proxy:${PLANE_CUSTOM_IMAGE_TAG}
api         -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-backend:${PLANE_CUSTOM_IMAGE_TAG}
worker      -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-backend:${PLANE_CUSTOM_IMAGE_TAG}
beat-worker -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-backend:${PLANE_CUSTOM_IMAGE_TAG}
migrator    -> ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-backend:${PLANE_CUSTOM_IMAGE_TAG}
```

数据库、Redis、RabbitMQ、MinIO、数据卷不变，仍沿用官方部署配置。

## 3. 构建与推送镜像

如果运维只负责服务器部署，可以跳过本节，由开发或 CI 完成构建推送。

在构建机进入仓库根目录：

```bash
git branch --show-current
git rev-parse --short HEAD
```

设置镜像仓库和 tag：

```bash
export DOCKER_BUILDKIT=1
export PLANE_CUSTOM_IMAGE_PREFIX=registry.example.com/plane
export PLANE_CUSTOM_IMAGE_TAG=pr-955f3bf1
```

构建镜像：

```bash
docker build -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-frontend:${PLANE_CUSTOM_IMAGE_TAG} -f apps/web/Dockerfile.web .
docker build -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-admin:${PLANE_CUSTOM_IMAGE_TAG} -f apps/admin/Dockerfile.admin .
docker build -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-space:${PLANE_CUSTOM_IMAGE_TAG} -f apps/space/Dockerfile.space .
docker build -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-live:${PLANE_CUSTOM_IMAGE_TAG} -f apps/live/Dockerfile.live .
docker build -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-backend:${PLANE_CUSTOM_IMAGE_TAG} -f apps/api/Dockerfile.api apps/api
docker build -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-proxy:${PLANE_CUSTOM_IMAGE_TAG} -f apps/proxy/Dockerfile.ce apps/proxy
```

如果 `plane-proxy` 构建时访问 Go module proxy 不稳定，可显式指定：

```bash
docker build \
  --build-arg GOPROXY=https://goproxy.cn,direct \
  -t ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-proxy:${PLANE_CUSTOM_IMAGE_TAG} \
  -f apps/proxy/Dockerfile.ce apps/proxy
```

推送镜像：

```bash
for image in plane-frontend plane-admin plane-space plane-live plane-backend plane-proxy; do
  docker push ${PLANE_CUSTOM_IMAGE_PREFIX}/${image}:${PLANE_CUSTOM_IMAGE_TAG}
done
```

## 4. 服务器部署调整

以下假设官方部署目录是 `plane-app`，里面有 `docker-compose.yaml` 和 `plane.env`。如果现场文件名是 `docker-compose.yml`，命令里的文件名按实际情况替换。

进入部署目录并备份环境文件：

```bash
cd plane-app
cp plane.env plane.env.$(date +%Y%m%d%H%M%S).bak
```

把 `docker-compose.pr.yml` 放到当前目录：

```bash
ls -l docker-compose.pr.yml
```

在 `plane.env` 增加或更新：

```env
PLANE_CUSTOM_IMAGE_PREFIX=registry.example.com/plane
PLANE_CUSTOM_IMAGE_TAG=pr-955f3bf1
PLANE_CUSTOM_PULL_POLICY=always
```

说明：

- `PLANE_CUSTOM_IMAGE_PREFIX` 改成实际镜像仓库前缀。
- `PLANE_CUSTOM_IMAGE_TAG` 改成本次发布 tag。
- 服务器能访问镜像仓库时用 `always`；如果通过 `docker save/load` 离线导入镜像，则用 `never`。
- 原来的 `APP_RELEASE` 可以保留，overlay 会覆盖业务镜像。

如需启用本次 PR 的飞书/Lark 功能，再补充：

```env
IS_LARK_ENABLED=1
LARK_CLIENT_ID=
LARK_CLIENT_SECRET=
LARK_BASE_DOMAIN=feishu.cn
LARK_DEFAULT_WORKSPACE_SLUG=
LARK_DEFAULT_WORKSPACE_ROLE=15
LARK_AUTO_SYNC_ENABLED=0
LARK_AUTO_JOIN_NEW_PROJECTS=0
LARK_NOTIFICATIONS_ENABLED=0
PLANE_PUBLIC_BASE_URL=https://your-plane-domain.example.com
```

未启用飞书/Lark 时，`IS_LARK_ENABLED=0` 即可。

变量说明：

| 变量 | 示例/默认值 | 说明 |
| --- | --- | --- |
| `IS_LARK_ENABLED` | `0` 或 `1` | 是否在 Plane 实例中启用飞书/Lark 登录和配置入口。启用时设为 `1`；不启用时设为 `0`。 |
| `LARK_CLIENT_ID` | 飞书应用的 App ID | 飞书/Lark 自建应用的 `App ID`，启用飞书登录时必填。 |
| `LARK_CLIENT_SECRET` | 飞书应用的 App Secret | 飞书/Lark 自建应用的 `App Secret`，启用飞书登录时必填。此值敏感，不要提交到代码仓库。 |
| `LARK_BASE_DOMAIN` | `feishu.cn` | 飞书/Lark API 域名选择。国内飞书通常使用 `feishu.cn`；海外 Lark 通常使用 `larksuite.com`。 |
| `LARK_DEFAULT_WORKSPACE_SLUG` | 工作区 slug | 飞书用户首次登录后自动加入的 Plane 工作区 slug。为空时不会自动加入指定工作区。 |
| `LARK_DEFAULT_WORKSPACE_ROLE` | `15` | 自动加入工作区时分配的角色值。当前默认 `15` 表示成员角色。只有设置了 `LARK_DEFAULT_WORKSPACE_SLUG` 时才有实际影响。 |
| `LARK_AUTO_SYNC_ENABLED` | `0` 或 `1` | 是否开启飞书通讯录定时同步任务。启用时设为 `1`，并需要同时配置 `LARK_DEFAULT_WORKSPACE_SLUG`。 |
| `LARK_AUTO_JOIN_NEW_PROJECTS` | `0` 或 `1` | 是否让已同步/已登录的飞书用户自动加入目标工作区下的新项目。建议先保持 `0`，确认权限策略后再开启。 |
| `LARK_NOTIFICATIONS_ENABLED` | `0` 或 `1` | 是否启用飞书通知发送。启用前需要确认飞书应用权限、回调/机器人能力和线上域名配置。 |
| `PLANE_PUBLIC_BASE_URL` | `https://your-plane-domain.example.com` | Plane 对外访问地址，用于生成飞书通知或 OAuth 流程中的跳转链接。生产环境必须改成真实 HTTPS 域名。 |

最小启用配置通常只需要：

```env
IS_LARK_ENABLED=1
LARK_CLIENT_ID=实际 App ID
LARK_CLIENT_SECRET=实际 App Secret
LARK_BASE_DOMAIN=feishu.cn
PLANE_PUBLIC_BASE_URL=https://your-plane-domain.example.com
```

自动加入工作区、通讯录同步、自动加入项目和飞书通知都属于增强能力，建议上线后分阶段开启。

飞书应用权限配置：

需要添加的应用能力：

| 能力 | 是否需要 | 什么时候需要 | 配置要点 |
| --- | --- | --- | --- |
| 网页应用 | 需要 | 启用飞书网页登录时需要 | 配置 Plane 的访问域名；在安全设置里添加重定向 URL：`https://<Plane 域名>/auth/lark/callback/`。截图里如果已经显示“配置”，说明该能力已添加，进去补配置即可。 |
| 机器人 | 可选 | 只有开启 `LARK_NOTIFICATIONS_ENABLED=1`，需要给用户发送任务通知时才需要 | 添加机器人能力，发布版本后生效；机器人可用范围需要包含接收通知的用户。 |
| 移动应用登录 | 不需要 | 当前 PR 没有接入飞书移动端登录 SDK | Plane 当前走网页 OAuth 回调，不走移动应用登录能力。 |
| 链接预览 | 不需要 | 当前 PR 不处理飞书里的链接预览卡片 | 无需添加。 |
| 工作台小组件 / 云文档小组件 / 多维表格插件 / 原生集成应用 | 不需要 | 当前 PR 没有这些入口或插件形态 | 无需添加。 |

通讯录邀请、通讯录同步不是通过“添加能力”配置，而是在“权限管理”和“通讯录权限范围”里配置。

| 场景 | 需要配置 | 权限标识 | 说明 |
| --- | --- | --- | --- |
| 飞书登录 | 网页应用登录能力；安全设置里添加重定向 URL | `contact:user.basic_profile:readonly`、`contact:user.email:readonly` | 用于获取登录用户的基础信息和邮箱。重定向 URL 需要配置为 `https://<Plane 域名>/auth/lark/callback/`。 |
| 登录时补全企业邮箱 | API 权限；通讯录权限范围 | `contact:contact.base:readonly`、`contact:user.employee:readonly` | 当飞书登录接口没有返回邮箱时，Plane 会用应用身份查询通讯录用户详情，优先取 `enterprise_email`。 |
| 从飞书通讯录邀请成员 | API 权限；通讯录权限范围 | `contact:contact.base:readonly`、`contact:user.base:readonly`、`contact:user.email:readonly`、`contact:user.employee:readonly` | 用于读取可见通讯录范围内的部门、用户、姓名、头像、邮箱、企业邮箱，并在 Plane 中预创建用户和工作区成员。 |
| 定时同步通讯录 | 同上 | 同上 | `LARK_AUTO_SYNC_ENABLED=1` 时使用，权限与“从飞书通讯录邀请成员”一致。 |
| 飞书任务通知 | 机器人能力；API 权限；机器人可用范围 | `im:message:send_as_bot` | `LARK_NOTIFICATIONS_ENABLED=1` 时使用，用应用机器人向用户发送任务分配、状态变更、评论通知卡片。 |

通讯录权限除了开通 API 权限，还需要在飞书应用后台配置“通讯录权限范围”。如果希望同步全公司，需要把应用的通讯录权限范围设到对应的全部部门或全部成员；如果只同步某个部门，只授权该部门即可。

当前 PR 不需要这些权限：

- 不需要 `contact:user.phone:readonly`，代码不读取手机号。
- 不需要 `contact:contact` 或其它写通讯录权限，代码不会创建、修改、删除飞书通讯录用户或部门。
- 不需要消息接收事件，例如 `im.message.receive_v1`，代码只发送消息，不接收用户发给机器人的消息。
- 不需要卡片回调，例如 `card.action.trigger`，当前通知卡片只包含跳转按钮，不处理飞书侧点击回调。

事件与回调配置：

当前 PR 不需要配置飞书事件订阅，也不需要配置回调地址。

| 页面 | 配置方式 |
| --- | --- |
| 事件配置 | 不添加任何事件。若页面必须选择订阅方式，可以保留默认“使用长连接接收事件”，但不要点击“添加事件”。不要选择“将事件发送至开发者服务器”，因为 Plane 当前没有实现飞书事件回调接口。 |
| 回调配置 | 不添加回调。当前通知卡片只跳转到 Plane 页面，不处理飞书卡片点击回调。 |
| 加密策略 | 不需要配置。没有事件/回调时不会用到 Encrypt Key 或 Verification Token。 |

如果后续新增“接收用户发给机器人的消息”或“处理卡片按钮回调”的功能，才需要重新配置事件订阅或回调地址。

## 5. 发布前校验

校验 compose 合并结果：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env config
```

确认业务镜像已经变成自建镜像：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env config \
  | grep -E 'image: .*/plane-(frontend|admin|space|live|backend|proxy):pr-955f3bf1'
```

预拉取镜像：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env pull \
  web space admin live api worker beat-worker migrator proxy
```

## 6. 发布步骤

先执行数据库迁移：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env up -d migrator
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env logs -f migrator
```

确认 `migrator` 正常结束后启动全部服务：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env up -d
```

检查容器状态：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env ps
```

检查关键日志：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env logs --tail=200 \
  api worker beat-worker web proxy
```

发布后访问 Plane 域名，确认登录、工作区、项目列表、创建/查看 issue 等核心功能正常。

## 7. 回滚

回滚到官方镜像时，不删除数据卷，只去掉 overlay：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env down
docker compose -f docker-compose.yaml --env-file plane.env pull
docker compose -f docker-compose.yaml --env-file plane.env up -d
```

如果只是回滚到上一版自建镜像，保留 overlay，把 `plane.env` 里的 `PLANE_CUSTOM_IMAGE_TAG` 改回旧 tag，然后执行：

```bash
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env pull
docker compose -f docker-compose.yaml -f docker-compose.pr.yml --env-file plane.env up -d
```

## 8. 离线部署

如果服务器不能访问镜像仓库，可在构建机导出镜像：

```bash
docker save \
  ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-frontend:${PLANE_CUSTOM_IMAGE_TAG} \
  ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-admin:${PLANE_CUSTOM_IMAGE_TAG} \
  ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-space:${PLANE_CUSTOM_IMAGE_TAG} \
  ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-live:${PLANE_CUSTOM_IMAGE_TAG} \
  ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-backend:${PLANE_CUSTOM_IMAGE_TAG} \
  ${PLANE_CUSTOM_IMAGE_PREFIX}/plane-proxy:${PLANE_CUSTOM_IMAGE_TAG} \
  | gzip > plane-images-${PLANE_CUSTOM_IMAGE_TAG}.tar.gz
```

服务器导入：

```bash
gunzip -c plane-images-pr-955f3bf1.tar.gz | docker load
```

然后在 `plane.env` 设置：

```env
PLANE_CUSTOM_PULL_POLICY=never
```

再按正常发布步骤执行。
