# AGENTS.md

本文件为在本仓库中工作的编码 Agent 提供项目规则与协作约束。

## 项目定位

本项目是一个电商智能定价平台，采用前端与双后端协作架构：

- `frontend/`：Vue 3 + TypeScript + Vite + Element Plus
- `backend-java/`：Spring Boot 3.2 + Java 21 对外业务后端
- `backend-python/`：FastAPI + CrewAI 内部 AI Worker
- `database/`：MySQL 基线 schema 与增量迁移
- `scripts/`、`ops/`：本地启动、部署、备份恢复、回滚、检查与运维手册

核心运行链路：

```text
Browser
  -> Frontend
  -> Java Backend /api/**
  -> RabbitMQ and internal HTTP
  -> Python Worker
  -> MySQL
```

硬性边界：

- 浏览器与前端代码只能调用 Java 后端的 `/api/**`。
- Java 是唯一面向浏览器的业务后端。
- Python 是内部服务，必须由 `X-Internal-Token` 保护。
- 浏览器实时更新使用 Java SSE，不使用 WebSocket，也不直连 Python socket。
- 主任务执行通过 RabbitMQ 异步派发。
- Python 将任务状态、Agent 日志、定价结果写入 MySQL。
- Java 从 MySQL 读取结果，并将进度和结果推送给前端。

## 高价值文档

- `README.md`：仓库入口、运行概览与本地使用说明
- `技术栈.md`：按层梳理的完整技术栈
- `AGENTS.md`：编码 Agent 规则与跨模块契约
- `ops/public-beta-runbook.md`：公测部署与运维流程
- `ops/load-test-runbook.md`：压测流程
- `ops/alert-thresholds.md`：运维告警阈值
- `ops/privacy-retention-policy.md`：隐私与数据保留规则

当架构、启动流程、部署假设、任务契约、数据库迁移或安全要求发生变化时，必须同步更新相关文档。

## 前端规则

技术栈：

- 使用 Vue 3 + TypeScript + Vite。
- Vue 单文件组件必须使用 `<script setup lang="ts">`。
- 状态管理使用 Pinia。
- 禁止引入 Vuex。
- HTTP 请求使用 Axios。
- 图表使用 ECharts。
- UI 组件库使用 Element Plus。

目录职责：

```text
frontend/src/api/          API 请求模块与请求客户端
frontend/src/stores/       Pinia 状态模块
frontend/src/views/        页面级视图
frontend/src/components/   可复用 UI 组件
frontend/src/composables/  Composition API 组合逻辑
frontend/src/utils/        纯工具函数
frontend/src/router/       Vue Router 配置
frontend/src/config/       前端配置
```

请求规则：

- 普通 HTTP 调用必须通过 `frontend/src/api/request.ts`。
- 请求客户端负责 base URL、认证头、refresh token、401 重试与错误信息归一化。
- 前端 API 模块必须指向 `/api/**`。
- 不得在前端代码中硬编码 Python Worker 地址。
- 前端不得直接连接 RabbitMQ。

实时规则：

- 定价任务进度使用 Java SSE：

```text
GET /api/pricing/tasks/{taskId}/events
Accept: text/event-stream
```

- 前端消费 Java SSE 流。
- 前端不得直接连接 Python 获取任务进度。

代码风格：

- 当前 Vue 组件文件约定使用 PascalCase，例如 `PricingLab.vue`。
- 当前 composable 文件约定使用 `useXxx.ts`，例如 `useEChart.ts`。
- 当前 API/helper 文件允许使用 camelCase，例如 `pricingBatch.ts`。
- 变量和函数使用 camelCase。
- 组件、类、TypeScript 类型使用 PascalCase。
- Vue/TS 缩进使用 2 个空格。

分层建议：

- View 可以组合 API、Store 和 Composable，但复杂业务逻辑应下沉到 composable 或 utils。
- 可复用图表逻辑应放入 composables。
- 可复用格式化、归一化逻辑应放入 utils。
- Store 只保存跨页面共享状态，不承载大型业务流程。

## Java 后端规则

技术栈：

- 使用 Spring Boot 3.2+。
- 使用 Java 21。
- 使用 MyBatis-Plus 进行 ORM/数据访问。
- 使用 Lombok 简化样板代码。
- 使用 RabbitMQ 进行异步任务派发与进度传递。
- 对外提供 REST API 与 Java SSE。

目录职责：

```text
controller/     HTTP Controller
service/        服务接口与独立服务
service/impl/   服务实现
mapper/         MyBatis-Plus Mapper
entity/         数据库实体
dto/            请求 DTO、跨服务 DTO、消息 DTO
vo/             响应视图对象
common/         通用工具、Result、JWT、CORS、拦截器
config/         Spring 配置
security/       安全、登录、会话、生产校验
exception/      全局异常处理
```

Controller 规则：

- 普通业务接口应返回 `Result<T>`。
- 健康检查、文件下载、导出和 SSE 接口可以返回 `Map`、`void`、`SseEmitter` 等特殊类型。
- 新增普通业务接口不得直接返回裸对象。
- Controller 应保持轻量，只负责参数接收、用户身份读取、参数校验、调用 Service 与返回结果。
- 新增业务逻辑不得在 Controller 中直接访问 Mapper。

分层规则：

```text
Controller -> Service -> Mapper
```

- Mapper 只负责数据库访问。
- Service 负责事务、业务规则和任务状态流转。
- DTO/VO 转换应靠近 Service 层，或放入职责明确的 helper。

ORM 规则：

- Mapper 应继承 `BaseMapper<T>`。
- Entity 类应使用 Lombok `@Data`。
- 不得引入 Hibernate/JPA。
- 不得新增用于业务查询的原生 JDBC。
- 如健康检查需要 DB ping，应将其隔离为基础设施逻辑，或优先使用已有 Mapper。

依赖注入：

- 优先使用构造器注入。
- 推荐使用 `@RequiredArgsConstructor` + `final` 字段。
- 项目中允许已有的 `@Autowired`，但新增代码在简单场景下应避免字段注入。

实时与跨服务规则：

- Java 在 `GET /api/pricing/tasks/{taskId}/events` 暴露 SSE。
- Java 将任务派发消息发布到 RabbitMQ。
- Java 消费 Python/RabbitMQ 进度事件，并转换为 SSE payload。
- Java 调用 Python 内部 HTTP API 仅用于健康检查、状态、日志、详情、重试、恢复等辅助能力。
- 跨服务消息必须使用明确 DTO，例如 `TaskDispatchEvent`、`TaskProgressEvent`。

## Python Worker 规则

技术栈：

- 使用 Python 3.10+；当前 Docker 运行时为 Python 3.12。
- 使用 FastAPI 提供内部 HTTP API。
- 使用 CrewAI 进行多智能体编排。
- 使用 SQLAlchemy + PyMySQL 访问 MySQL。
- 使用 Pydantic 定义 Schema/DTO。
- 使用 aio-pika 访问 RabbitMQ。
- 使用 pytest 编写与运行测试。

目录职责：

```text
app/api/          FastAPI 路由
app/core/         配置、安全、日志、trace 上下文
app/models/       SQLAlchemy 模型
app/repos/        数据库 Repository
app/schemas/      Pydantic Schema 与 DTO
app/services/     应用服务与 Worker
app/application/  兼容性的应用层入口
app/domain/       确定性领域规则
app/agents/       CrewAI Agent 定义
app/crew/         CrewAI Crew、Task 与 Runtime
app/tools/        Agent 工具
app/agent_tools/  Agent 工具注册
app/utils/        工具函数
tests/            测试套件
```

内部 API 规则：

- Python HTTP API 仅供内部调用。
- 内部路由必须校验 `X-Internal-Token`。
- 生产环境不得启用 token 绕过。
- HTTP 路由覆盖 health、ready、live、metrics、任务状态、任务详情、任务日志、重试与恢复。

执行规则：

- 主定价任务通过 RabbitMQ Worker 执行。
- Python 从 MySQL 读取任务上下文。
- Python 执行 CrewAI 多 Agent 定价工作流。
- Python 写入 `pricing_task`、`agent_run_log`、`pricing_result`。
- Python 将进度事件发布到 RabbitMQ；Java 再推送到浏览器。

代码风格：

- Python 文件、函数、变量使用 snake_case。
- Python 类使用 PascalCase。
- 与 Java/前端 camelCase payload 交互的 Pydantic Schema 应定义明确 alias。
- Python 缩进使用 4 个空格。
- 复杂 SQL 应封装在 repos 中，不应散落在 services 中。

## 实时任务契约

流式端点：

- `GET /api/pricing/tasks/{taskId}/events`（Java `SseEmitter`）

消息 payload 中的 `type` 事件类型：

- `task_started`
- `agent_card`
- `task_completed`
- `task_failed`

任务状态生命周期：

- 正常路径：`QUEUED` -> `RUNNING` -> `COMPLETED`
- 重试路径：`RUNNING` -> `RETRYING` -> `RUNNING`
- 非成功终态：`MANUAL_REVIEW`、`FAILED`、`CANCELLED`

修改状态、事件类型、Agent 卡片 payload、结果 payload、重试语义或恢复语义时，必须同步更新所有受影响模块：

- Java：`DecisionTaskServiceImpl`、`PricingTaskStreamService`、DTO、mapper/service 等
- Python：`dispatch_service.py`、`task_repo.py`、`orchestration_service.py`、schema/repo 等
- Frontend：`src/api/decision.ts`、`src/views/PricingLab.vue`、相关 utils/composables

## API Surface

Java 对外 API：

- 认证/会话：`/api/user/login`、`/api/user/refresh`、`/api/user/logout`
- 用户管理：`/api/user/list`、`/api/user/add`、`/api/user/{id}`、批量删除
- 用户 LLM 配置：`/api/user/llm-config`（`GET/PUT/DELETE`）、`/verify`
- 店铺：`/api/shops`
- 商品/导入/趋势：`/api/products/**`
- 决策 API，保留旧版兼容：`/api/decision/**`
- 定价任务：`/api/pricing/tasks/**`
- 批量定价：`/api/pricing/batches/**`
- 健康检查/指标：`/api/health`、`/api/health/live`、`/api/health/ready`、`/api/health/metrics`

Python 内部 API：

- 任务状态：`/internal/tasks/{taskId}/status`
- 任务详情：`/internal/tasks/{taskId}/detail`
- 任务日志：`/internal/tasks/{taskId}/logs`
- 任务重试：`/internal/tasks/{taskId}/retry`
- 任务恢复：`/internal/tasks/recover-stale`
- 健康检查/指标：`/health`、`/health/live`、`/health/ready`、`/health/metrics`

主任务派发：

- Java 将任务消息发布到 RabbitMQ。
- Python 从 RabbitMQ 消费任务。
- 不要假设主执行路径是 Java 直接通过 HTTP 调用 Python dispatch。

## 数据库与迁移规则

数据库：

- 使用 MySQL 8.x。
- 使用 InnoDB。
- 使用 utf8mb4。
- 基线 schema 位于 `database/schema.sql`。
- 增量迁移位于 `database/migration_*.sql`。

初始化顺序：

1. `database/schema.sql`
2. 按文件名顺序执行 `database/migration_*.sql`

核心表：

- `pricing_task`
- `agent_run_log`
- `pricing_result`
- `pricing_batch`
- `pricing_batch_item`
- `user_llm_config`
- `auth_refresh_session`
- `login_audit_log`
- `schema_migration_history`

迁移规则：

- 新增表、字段、索引和约束必须提供 SQL 迁移。
- 数据库变更必须同步更新相关 Java entity/mapper/service。
- 数据库变更必须同步更新相关 Python model/repo/schema。
- payload 或展示字段变化时，必须同步更新前端字段使用。
- 不得只改 entity/model 而不处理 schema 或迁移。
- 不得只加迁移而不更新依赖该结构的代码模型。

## 基础设施规则

当前运行基础设施：

- MySQL 8.4
- RabbitMQ 3.13
- Java Backend
- Python Worker
- Frontend Vite dev server 或 Nginx 静态托管
- Docker Compose

当前不属于运行依赖：

- Redis
- Chroma / ChromaDB

除非实际引入 Redis 或 Chroma，否则不得在文档中将其描述为当前活跃依赖。未来如需引入，必须补齐完整运行面：

- 依赖声明
- Docker Compose 服务
- 环境变量
- 健康检查/就绪检查
- 代码集成
- `README.md` 与 `技术栈.md` 更新
- 部署和 runbook 更新

本地启动顺序：

1. MySQL
2. RabbitMQ
3. Python Worker
4. Java Backend
5. Frontend

Windows 一键本地启动：

- `scripts/start-local-dev.ps1`

在 Windows 上，当 Python Worker 需要仓库内的 selector loop / `h11` uvicorn 包装时，`python run_server.py` 仍作为 fallback。

## 安全规则

必须保护以下值：

- DB password
- JWT secret
- refresh token secret
- internal API token
- LLM key encryption secret
- 用户 LLM API Key

生产环境必须拒绝或避免：

- 空 DB password
- 弱 JWT secret
- 空 internal token
- dev bootstrap
- 不安全 CORS origin
- Python internal-token bypass

LLM Key 规则：

- 用户 LLM API Key 必须加密存储。
- Java 与 Python 必须使用同一个 `LLM_KEY_ENCRYPTION_SECRET`。
- 不得记录明文 LLM API Key 日志。
- 除受控编辑流程明确需要外，前端响应只应暴露 masked API Key。

## 代码风格规则

通用规则：

- 变更应聚焦且小而准。
- 引入新模式前，应优先匹配已有代码风格。
- 不做无关重构。
- 只有在能减少真实复杂度或符合既有本地模式时，才新增抽象。

Java：

- 文件名和类名使用 PascalCase。
- 变量和方法使用 camelCase。
- 常量使用 UPPER_SNAKE_CASE。
- 缩进使用 4 个空格。

Python：

- 文件、变量、函数使用 snake_case。
- 类使用 PascalCase。
- 缩进使用 4 个空格。

TypeScript/Vue：

- 变量和函数使用 camelCase。
- 组件、类、类型使用 PascalCase。
- 缩进使用 2 个空格。

## 变更协同规则

跨模块变更必须显式检查兼容性：

- Auth/session：`JwtAuthInterceptor`、refresh cookie、前端 token refresh interceptor
- LLM config：Java 加密/解密、Python 解密、`user_llm_config`、前端模型管理 API
- RabbitMQ dispatch payload：Java publisher、Python consumer、DTO/schema 兼容性
- Progress event payload：Python publisher、Java subscriber/SSE mapper、前端 stream handler
- SSE contract：Java emitter payload 与前端 stream 解析
- Task status：Java service、Python repo/service、前端类型/UI
- Pricing result structure：DB、Java VO/service、Python schema/repo、前端展示
- Batch pricing logic：Java batch service、任务创建、前端批量页面
- Database schema：迁移、Java entity/mapper、Python model/repo
- Health/readiness semantics：Java/Python health endpoint、Docker healthcheck、运维告警
- Production security validation：Java 启动检查、Python 配置校验、部署环境变量示例

## 测试与验证

完成较大改动前，应优先运行聚焦检查：

- Java 测试：`cd backend-java && mvn test`
- Python 测试：`cd backend-python && python -m pytest tests -q`
- 前端构建：`cd frontend && npm run build`
- 完整预发布检查：`scripts/run-prelaunch-checks.ps1`

按变更类型推荐验证：

- Java 业务逻辑：运行相关 Java 测试。
- Python 任务/Agent 执行：运行相关 Python 测试。
- 前端 UI/API 类型变更：运行前端 build。
- 数据库迁移变更：运行迁移校验脚本。
- SSE/任务状态变更：验证 Pricing Lab 流程。
- 批量定价变更：验证批量创建、详情、取消、失败展示和结果展示。

## 运维与 Runbook

高价值运维文件：

- `docker-compose.public-beta.yml`
- `scripts/deploy-public-beta.ps1`
- `scripts/rollback-public-beta.ps1`
- `scripts/apply-db-migrations.ps1`
- `scripts/db-backup.ps1`
- `scripts/db-restore.ps1`
- `scripts/load-test-public-beta.py`
- `scripts/check-operational-alerts.py`
- `scripts/apply-retention-policy.ps1`
- `ops/public-beta-runbook.md`
- `ops/load-test-runbook.md`
- `ops/alert-thresholds.md`
- `ops/privacy-retention-policy.md`

当部署行为、环境变量、健康检查、数据保留、告警、备份或回滚行为发生变化时，必须更新对应 runbook 或脚本文档。
