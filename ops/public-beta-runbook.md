# Public Beta Runbook

## 1. Prepare secrets

1. Copy `.env.public-beta.example` to `.env.public-beta`.
2. Replace every placeholder value with production-safe secrets.
3. Set `ALLOWED_ORIGINS` to the real frontend domain.

## 2. Deploy

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-public-beta.ps1
```

What it does:

- validates required env vars
- starts the Docker Compose stack
- waits for MySQL, Python, Java, and frontend readiness
- applies pending SQL migrations exactly once

Frontend runtime note:

- The current local Docker Compose stack runs the frontend as `node:20-alpine` with Vite dev server, mounting `frontend/` into the container for hot reload.
- After changing from an older Nginx/static frontend container, recreate the stack once:

```powershell
docker compose --env-file .env.public-beta -f docker-compose.public-beta.yml up -d --build --force-recreate
```

- In `docker ps`, the hot-reload frontend should map `FRONTEND_PUBLIC_PORT` to container port `5173`, not `80`.

## 3. Back up the database

```powershell
powershell -ExecutionPolicy Bypass -File scripts/db-backup.ps1
```

Backups are written to `backups/public-beta/`.

## 4. Restore from a backup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/db-restore.ps1 -BackupFile backups/public-beta/<file>.sql -Force
```

The restore script creates a safety backup first unless `-SkipPreBackup` is passed.

## 5. Roll back the release

```powershell
powershell -ExecutionPolicy Bypass -File scripts/rollback-public-beta.ps1 -BackupFile backups/public-beta/<file>.sql
```

If `-BackupFile` is omitted, the latest backup in `backups/public-beta/` is used.

## 6. Apply migrations without redeploying

```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply-db-migrations.ps1
```

Migration state is tracked in `schema_migration_history`.

Before a release, run the migration gate check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-db-migration-gates.ps1
```

- Use `-RequireRollback` for new schema-changing releases. Historical migrations in `database/rollback_baseline_waivers.txt` predate the rollback gate; do not add new migrations to that waiver file.
- Use `-CheckCleanDatabase` only against an isolated staging or disposable database; it invokes the migration apply script and records the result through `schema_migration_history`.
- This agent architecture hardening pass does not add a new SQL migration, so no new rollback SQL is required for these code-only changes.

For an isolated clean database rehearsal, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-clean-db-migrations.ps1
```

This creates a temporary database, applies `schema.sql` and every ordered `migration_*.sql`, then drops the temporary database unless `-KeepDatabase` is passed.

## 7. Pricing worker rollout gates

- Keep `PYTHON_AUTO_SCHEMA_PATCH=false` in production. Python startup must only check schema readiness; schema changes must be applied by `database/schema.sql` plus ordered `migration_*.sql` files.
- Deploy the Java/frontend compatibility version before rolling out Python worker changes that clear `current_execution_id` on terminal finalization.
- Start the Python worker gray rollout with `RABBITMQ_PREFETCH=1` and `RABBITMQ_WORKER_CONCURRENCY=1`.
- Verify SSE terminal behavior before expanding workers: `MANUAL_REVIEW/COMPLETED` should end the browser stream without waiting for four completed cards; `FAILED/CANCELLED` should emit `task_failed`.
- Watch `queueDepth`, `activeExecutions`, `staleRunningTasks`, `consumerRetryCount`, `retryPublishFailureCount`, `casConflictCount`, `progressPublishFailureCount`, `llmTimeoutCount`, `manualReviewWithoutResultCount`, and `manualReview` for 30-60 minutes before scaling out.
- `sseTerminalLatencyMs` is a reserved rollout metric name until terminal DB-write and SSE-send timestamps are collected; do not use it as a go/no-go threshold without that instrumentation.
- Record the observation window with:

```powershell
python scripts/observe-gray-rollout.py --duration-minutes 30 --interval-seconds 60
```

The script writes JSONL samples and a summary under `ops/reports/runtime/`. Any threshold breach is a no-go for scaling out.

## 8. Retry and recovery notes

- Browser/user retry should go through Java. Python `/internal/tasks/{taskId}/retry` is an internal compatibility/ops entry.
- If Python internal retry marks a task `RETRYING` but RabbitMQ publish fails, it must compensate the task to `FAILED`; investigate RabbitMQ before retrying again.
- Redelivered RabbitMQ messages with a live `current_execution_id` are expected to be acked and dropped. Only stale leases should be reclaimed.
- Java `/api/health/ready` no longer fails solely because Python Worker is down. Treat `pythonWorker=down` in readiness/metrics as an operations alert, not a Java gateway outage.
