# 电商智能定价平台

电商智能定价平台，采用前后端分离 + 双后端协作架构：

- 前端：Vue 3 + TypeScript + Vite
- 公共业务后端：Spring Boot 3.2 + Java 21
- 内部智能任务后端：FastAPI + Python 3.12 + CrewAI
- 数据层：MySQL 8.4
- 异步派发：RabbitMQ 3.13
- 部署入口：Nginx + Docker Compose

## 文档入口

- [技术栈](./技术栈.md)：按前端、后端、数据库、消息中间件、部署方式整理的完整技术栈清单
- [AGENTS](./AGENTS.md)：仓库内协作和代码变更约束

## 项目结构

- `frontend/`：Vue 3 前端工程，负责页面展示、交互、任务发起和结果查看
- `backend-java/`：Spring Boot 业务 API，负责鉴权、业务编排、SSE 推送、数据读取
- `backend-python/`：FastAPI 内部工作器，负责多智能体定价任务执行，市场情报当前基于本地天猫 CSV 竞品索引
- `database/`：基线建表 SQL 和增量迁移脚本
- `scripts/`：本地开发、部署、回滚、检查、备份等脚本
- `ops/`：运行手册、容量与告警说明

## 运行架构

```text
Browser
  -> Frontend (Vue 3)
    -> Java Backend (:8080, public API + SSE)
      -> RabbitMQ / internal HTTP
        -> Python Worker (:8000, internal only)
          -> MySQL
```

关键边界：

- 浏览器只访问 Java 暴露的 `/api/**`
- Python 是内部服务，不直接暴露给浏览器
- Java 负责 SSE 事件流，前端不直接连 Python
- Python 负责执行智能定价流程并写入任务日志与结果
- Java 读取任务状态、日志和结果并对外提供查询与流式更新

## 核心能力

- 用户登录、刷新、登出与会话管理
- 店铺、商品、SKU、导入数据管理
- 单商品定价任务
- 批量定价任务
- 多智能体定价分析与风控
- 基于本地天猫 CSV 竞品索引的市场情报汇总
- 实时任务流和 Agent 卡片展示
- 历史归档与结果查看
- 用户级模型配置管理

## 本地开发

### 依赖

- Node.js 20+
- Java 21
- Maven 3.9+
- Python 3.12
- MySQL 8+
- RabbitMQ 3.13+

### 推荐启动顺序

1. MySQL
2. RabbitMQ
3. Python worker
4. Java backend
5. Frontend

### 手动启动

```powershell
# Java
cd backend-java
mvn spring-boot:run

# Python
cd backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### 一键启动

```powershell
scripts/start-local-dev.ps1
```

说明：

- 该脚本会拉起前端、Java、Python 三个应用进程
- 基础设施依赖如 MySQL、RabbitMQ 需要预先可用
- 如需提高批量定价任务的并发消费能力，可通过环境变量 `RABBITMQ_WORKER_CONCURRENCY` 调整 Python Worker 的 RabbitMQ consumer 数量；默认值为 `1`
- Windows 本地如遇 uvicorn `accept` / `WinError 10014` 一类问题，可改用 `python run_server.py`，它会补充本仓库使用的 Selector loop 与 `h11` 参数

## 测试与验证

```powershell
# Java
cd backend-java
mvn test

# Python
cd backend-python
python -m pytest tests -q

# Frontend
cd frontend
npm run build

# 全量预发布检查
scripts/run-prelaunch-checks.ps1
```

## 部署

Public Beta 编排入口：

```powershell
docker compose -f docker-compose.public-beta.yml up -d --build
```

相关文件：

- `docker-compose.public-beta.yml`
- `.env.public-beta.example`
- `frontend/nginx.default.conf`
- `scripts/deploy-public-beta.ps1`
- `scripts/rollback-public-beta.ps1`

## 通信与安全

- 前端通过 `Bearer Token` 访问受保护接口
- 会话续期使用 Refresh Token Cookie
- Java 与 Python 间内部调用使用 `X-Internal-Token`
- 主任务派发走 RabbitMQ；Python 内部 HTTP 当前主要用于健康检查、任务状态/详情/日志查询和重试
- 实时任务更新通过 SSE：`GET /api/pricing/tasks/{taskId}/events`
- 生产部署时需要显式配置数据库密钥、JWT 密钥、内部令牌和跨域白名单

## 一句话总结

这是一个以 `Vue 3 + Spring Boot + FastAPI + CrewAI + MySQL + RabbitMQ + Docker + Nginx` 为核心栈构建的电商智能定价平台，其中 Java 是统一对外业务入口，Python 负责内部智能定价执行。
