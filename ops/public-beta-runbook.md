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
