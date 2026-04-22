# Python Agent Worker

这个目录是智能定价平台的 Python 内部 Worker，负责执行 4 个定价 Agent，并把过程日志和最终结果写入数据库。

## 角色定位

- 接收 Java 创建后经 RabbitMQ 派发的内部任务
- 从 MySQL 中认领 `QUEUED/RETRYING` 任务
- 执行多 Agent 定价编排
- 写入 `agent_run_log` 和 `pricing_result`
- 提供健康检查和任务指标接口

## 架构位置

```text
Frontend
  -> Java Backend
    -> Python Worker
      -> CrewAI / 定价 Agent
        -> MySQL
```

说明：

- 浏览器不直接访问 Python
- 实时展示由 Java 的 SSE 接口负责
- Python 只负责内部执行和写库

## 启动

```bash
cd backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Windows 本地如遇 uvicorn `accept` / `WinError 10014` 一类问题，可改用：

```bash
python run_server.py
```

## 环境变量

至少需要配置：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DB`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `MODEL`
- `INTERNAL_API_TOKEN`

队列相关参数：

- `AGENT_WORKER_CONCURRENCY`
- `AGENT_QUEUE_MAXSIZE`
- `AGENT_POLL_INTERVAL_MS`
- `AGENT_MAX_RETRIES`

## API

内部任务接口前缀：

- `/internal/tasks`

主要接口：

- `POST /internal/tasks/{taskId}/retry`
- `GET /internal/tasks/{taskId}/status`
- `GET /internal/tasks/{taskId}/detail`
- `GET /internal/tasks/{taskId}/logs`

说明：

- 主任务创建不经过 Python HTTP dispatch 接口，当前由 Java 发布 RabbitMQ 消息，Python Worker 异步消费

健康与指标：

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /health/metrics`

## 调度模型

当前不是浏览器实时服务，而是数据库认领式 worker：

1. Java 创建任务并写入 `pricing_task`
2. Java 发布 RabbitMQ 派发消息
3. Python Worker 消费消息并把任务推进到 `QUEUED/RUNNING`
4. 执行完成后写入 `agent_run_log` / `pricing_result`
5. Java 读取数据库和异步进度，并通过 SSE 推给前端

## 可观测性

Python 日志已经接入：

- `traceId`
- `taskId`
- HTTP 请求开始/结束日志
- worker 执行日志

任务指标通过 `/health/metrics` 提供，包含：

- 队列深度
- 活跃执行数
- 终态任务数量
- 超时未完成任务数量
- 平均和最大执行时长
