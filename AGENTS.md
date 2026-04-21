# AGENTS.md

Guidance for coding agents working in this repository.

## High-Value Docs

- `README.md`: repo entrypoint and runtime overview
- `技术栈.md`: full stack inventory by layer

Keep these root docs aligned when architecture, startup flow, or deployment assumptions change.

## Project Overview

This is an e-commerce intelligent pricing platform with a split runtime:

- `frontend/`: Vue 3 + TypeScript + Vite + Element Plus
- `backend-java/`: Spring Boot 3.2 (Java 21) business API
- `backend-python/`: FastAPI internal worker with CrewAI orchestration
- `database/`: base schema + incremental migrations
- `scripts/`, `ops/`: deployment, checks, backup/restore, runbooks

## Runtime Architecture

```text
Frontend (Vite dev / Nginx static site)
  -> Java Backend (:8080, public API + SSE)
    -> RabbitMQ and internal HTTP
      -> Python Worker (:8000, internal API only)
        -> multi-agent pricing workflow
          -> MySQL (pricing_system2.0)
```

Hard boundaries:

- Frontend must call only Java (`/api/**`)
- Java is the only browser-facing backend
- Python is internal and must stay protected by `X-Internal-Token`
- Real-time browser updates are Java SSE, not Python sockets
- Python writes task logs/results to MySQL; Java reads and streams them

## Real-Time Task Contract

Stream endpoint:

- `GET /api/pricing/tasks/{taskId}/events` (Java `SseEmitter`)

Event types (message payload `type`):

- `task_started`
- `agent_card`
- `task_completed`
- `task_failed`

Task status lifecycle used across frontend, Java, and Python:

- `QUEUED` -> `RUNNING` -> `COMPLETED`
- failure/retry path: `RUNNING` -> `RETRYING` -> `RUNNING`
- terminal non-success: `MANUAL_REVIEW`, `FAILED`, `CANCELLED`

When changing statuses or stream payloads, update all three sides:

- Java: `DecisionTaskServiceImpl`, `PricingTaskStreamService`
- Python: `dispatch_service.py`, `task_repo.py`
- Frontend: `src/api/decision.ts`, `src/views/PricingLab.vue`

## API Surface

Java (`backend-java`):

- Auth/session: `/api/user/login`, `/api/user/refresh`, `/api/user/logout`
- User management: `/api/user/list`, `/api/user/add`, `/api/user/{id}`, batch delete
- User LLM config: `/api/user/llm-config` (`GET/PUT/DELETE`), `/verify`
- Shops: `/api/shops`
- Products/import/trend: `/api/products/**`
- Decision APIs (legacy-compatible): `/api/decision/**`
- Pricing task APIs: `/api/pricing/tasks/**`
- Batch pricing APIs: `/api/pricing/batches/**`
- Health/metrics: `/api/health`, `/api/health/live`, `/api/health/ready`, `/api/health/metrics`

Python (`backend-python`):

- Internal task APIs: `/internal/tasks/dispatch`, `/{taskId}/retry`, `/{taskId}/status`, `/{taskId}/detail`, `/{taskId}/logs`
- Health/metrics: `/health`, `/health/live`, `/health/ready`, `/health/metrics`

## Database and Migrations

Initialize in order:

1. `database/schema.sql`
2. migrations by filename order (`migration_*.sql`)

Current migrations:

1. `migration_20260327_external_product.sql`
2. `migration_20260329_agent_card_mvp.sql`
3. `migration_20260329_simplify_agent_run_log.sql`
4. `migration_20260405_product_status_cn.sql`
5. `migration_20260407_launch_hardening.sql`
6. `migration_20260408_task_recovery.sql`
7. `migration_20260411_user_llm_config.sql`
8. `migration_20260411_user_llm_config_comment_fix.sql`
9. `migration_20260412_force_manual_review_strategy.sql`
10. `migration_20260413_agent_stage.sql`
11. `migration_20260413_stage_failed_backfill.sql`
12. `migration_20260418_agent_run_attempt.sql`
13. `migration_20260418_product_category_titles.sql`
14. `migration_20260419_agent_raw_output.sql`
15. `migration_20260420_pricing_batch.sql`
16. `migration_20260421_rabbitmq_async.sql`

Core tables:

- `pricing_task`
- `agent_run_log`
- `pricing_result`
- `pricing_batch`
- `pricing_batch_item`
- `user_llm_config`
- `auth_refresh_session`
- `login_audit_log`
- `schema_migration_history`

## Local Development

Recommended startup order:

1. MySQL
2. RabbitMQ
3. Python worker
4. Java backend
5. Frontend

Manual commands:

```bash
# Java
cd backend-java
mvn spring-boot:run

# Python
cd backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_server.py

# Frontend
cd frontend
npm install
npm run dev
```

One-click local startup (Windows): `scripts/start-local-dev.ps1`

Note:

- `scripts/start-local-dev.ps1` launches the three app processes
- infra dependencies such as MySQL and RabbitMQ must already be available

## Testing and Verification

Use these before concluding substantial changes:

- Java tests: `cd backend-java && mvn test`
- Python tests: `cd backend-python && python -m pytest tests -q`
- Frontend build check: `cd frontend && npm run build`
- Full prelaunch checks: `scripts/run-prelaunch-checks.ps1`

## Security and Production Guardrails

Java startup validation fails in `prod` for unsafe config, including:

- blank/weak DB password or JWT secret
- blank internal token
- dev bootstrap enabled
- localhost-only or unsafe allowed origins

Python internal token rules:

- in `prod`, internal token must be validated
- dev bypass exists only when token is blank and `ALLOW_DEV_INTERNAL_TOKEN_BYPASS=true`

Public beta deployment uses:

- `docker-compose.public-beta.yml`
- `.env.public-beta` (from `.env.public-beta.example`)
- migration/backup/rollback scripts under `scripts/`

## Code Conventions

- Java: controller -> service -> mapper layering; MyBatis-Plus; Lombok `@Data`
- Python: SQLAlchemy models + repository/service split; workers claim tasks from DB or queue
- Frontend: Vue 3 Composition API + Pinia + Axios + Vue Router
- Frontend proxy keeps backend access under `/api`

## Change Coordination Rules

When changing these areas, keep cross-module consistency:

- Auth/session: `JwtAuthInterceptor`, refresh cookie handling, frontend token refresh interceptor
- LLM config: Java encryption/decryption (`AesGcmUtil`), `user_llm_config` schema, frontend personal center APIs
- Task dispatch: Java publisher/client payloads must match Python dispatch schemas and worker expectations
- SSE contracts: Java emitter payloads must stay compatible with frontend stream handlers
- Metrics/health: Java `/api/health/ready` depends on Python `/health/ready`; do not break readiness semantics
- RabbitMQ async flow: Java publisher, Python consumer, DB retry fields, and health checks must stay in sync

## Ops and Runbooks

High-value files:

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
