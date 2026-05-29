# Plane Feishu Connector

独立飞书长连接进程。它不处理业务逻辑，只通过飞书官方 `lark-oapi` SDK 接收事件，写入 Django 的 `lark_events` 表并触发 Celery 任务。

启动示例：

```bash
cd apps/lark-connector
python main.py
```

该进程复用 `apps/api` 的 Python 依赖和 Django 配置，需要与 API/Celery 指向同一套数据库、Redis 和消息队列。
