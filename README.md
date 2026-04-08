# 智能定价平台

这是一个“前端 + Java 业务后端 + Python Agent Worker”的电商智能定价系统。

## 架构

```text
Frontend (Vue3, :5173)
  -> Java Backend (Spring Boot, :8080)
    -> Python Worker (FastAPI, :8000)
      -> 4 个定价 Agent
        -> MySQL (pricing_system2.0)
```

当前实时链路已经统一为 `SSE/实时流`：

- 前端只访问 Java
- Java 从数据库读取任务状态、Agent 日志和最终结果
- Java 通过 `/api/pricing/tasks/{taskId}/events` 向前端推送 SSE 事件
- Python 不再向浏览器提供旧版双向实时接口

## 目录结构

```text
graduation_project/
  frontend/
  backend-java/
  backend-python/
  database/
  scripts/
  ops/
```

## 启动方式

### Java

```bash
cd backend-java
mvn spring-boot:run
```

### Python

```bash
cd backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

也可以直接使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local-dev.ps1
```

## 数据库

初始化或新环境：

1. 执行 `database/schema.sql`
2. 再按日期顺序执行 `database/migration_*.sql`

关键表：

- `pricing_task`
- `agent_run_log`
- `pricing_result`
- `auth_refresh_session`
- `login_audit_log`

## 关键能力

- 显式角色鉴权、refresh/logout、登录审计、登录限流
- Java 统一公网入口
- Python 基于数据库认领的 worker 调度
- 任务状态支持 `QUEUED/RUNNING/RETRYING/MANUAL_REVIEW/FAILED/CANCELLED`
- 支持取消任务和取消后重新配置
- 支持人工审核后再应用建议价格
- SSE 实时展示 Agent 分析过程

## 健康检查与指标

### Java

- `GET /api/health/live`
- `GET /api/health/ready`
- `GET /api/health/metrics`

### Python

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /health/metrics`

当前指标重点关注：

- 队列深度
- 活跃执行数
- `MANUAL_REVIEW` / `FAILED` / `CANCELLED` 数量
- 超时未完成任务数量
- 平均执行时长和最大执行时长

## 运维脚本

- 公测部署：`scripts/deploy-public-beta.ps1`
- 数据库迁移：`scripts/apply-db-migrations.ps1`
- 数据库备份：`scripts/db-backup.ps1`
- 数据库恢复：`scripts/db-restore.ps1`
- 回滚：`scripts/rollback-public-beta.ps1`
- 数据保留清理：`scripts/apply-retention-policy.ps1`
- 压测：`scripts/load-test-public-beta.py`
- 告警阈值检查：`scripts/check-operational-alerts.py`

## 运维文档

- 公测 runbook：`ops/public-beta-runbook.md`
- 压测说明：`ops/load-test-runbook.md`
- 告警阈值：`ops/alert-thresholds.md`
- 隐私与数据保留策略：`ops/privacy-retention-policy.md`

## 当前边界

以下两项仍未纳入当前交付范围：

- 验证码
- 灰度发布机制
