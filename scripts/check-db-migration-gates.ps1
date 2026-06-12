[CmdletBinding()]
param(
    [string]$MigrationsDirectory = 'database',
    [string]$RollbackWaiverFile = 'database/rollback_baseline_waivers.txt',
    [switch]$RequireRollback,
    [switch]$CheckCleanDatabase,
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$migrationRoot = Resolve-Path (Join-Path $repoRoot $MigrationsDirectory)
$schemaPath = Join-Path $migrationRoot 'schema.sql'
if (-not (Test-Path $schemaPath)) {
    throw "Missing base schema: $schemaPath"
}

$migrationFiles = Get-ChildItem -Path $migrationRoot -Filter 'migration_*.sql' | Sort-Object Name
if (-not $migrationFiles) {
    throw "No migration_*.sql files found in $migrationRoot"
}

$waivedRollback = @{}
$waiverPath = Join-Path $repoRoot $RollbackWaiverFile
if (Test-Path $waiverPath) {
    foreach ($line in Get-Content -Path $waiverPath) {
        $trimmed = [string]$line
        $trimmed = $trimmed.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) {
            continue
        }
        $waivedRollback[$trimmed] = $true
    }
}

$missingRollback = @()
$waivedMissingRollback = @()
foreach ($file in $migrationFiles) {
    $suffix = $file.Name.Substring('migration_'.Length)
    $rollbackPath = Join-Path $migrationRoot "rollback_$suffix"
    if (-not (Test-Path $rollbackPath)) {
        if ($waivedRollback.ContainsKey($file.Name)) {
            $waivedMissingRollback += $file.Name
        } else {
            $missingRollback += $file.Name
        }
    }
}

if ($missingRollback.Count -gt 0) {
    $message = "Migrations without rollback pair: $($missingRollback -join ', ')"
    if ($RequireRollback) {
        throw $message
    }
    Write-Warning $message
}
if ($waivedMissingRollback.Count -gt 0) {
    Write-Warning "Historical rollback waivers applied: $($waivedMissingRollback -join ', ')"
}

Write-Host "Schema gate ok: $schemaPath"
Write-Host "Migration order gate ok: $($migrationFiles.Count) migration files"
if ($missingRollback.Count -eq 0) {
    if ($waivedMissingRollback.Count -gt 0) {
        Write-Host "Rollback pair gate ok for new migrations; $($waivedMissingRollback.Count) historical migrations are waived"
    } else {
        Write-Host 'Rollback pair gate ok'
    }
}

if ($CheckCleanDatabase) {
    $applyScript = Join-Path $PSScriptRoot 'apply-db-migrations.ps1'
    if (-not (Test-Path $applyScript)) {
        throw "Missing migration apply script: $applyScript"
    }
    & $applyScript -ComposeFile $ComposeFile -EnvFile $EnvFile -MigrationsDirectory $MigrationsDirectory
    if ($LASTEXITCODE -ne 0) {
        throw 'Clean database migration check failed.'
    }
    Write-Host 'Clean database migration check completed via apply-db-migrations.ps1'
}
