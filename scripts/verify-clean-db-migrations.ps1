[CmdletBinding()]
param(
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [string]$MigrationsDirectory = 'database',
    [string]$DatabaseName = '',
    [string]$ReportDirectory = 'ops/reports/runtime',
    [switch]$KeepDatabase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

function Invoke-MysqlNoDatabase {
    param(
        [Parameter(Mandatory)]
        [string]$Sql
    )

    $composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + @(
        'exec',
        '-T',
        'mysql',
        'sh',
        '-lc',
        'mysql --default-character-set=utf8mb4 -N -B -uroot -p"$MYSQL_ROOT_PASSWORD"'
    )
    $Sql | & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'MySQL command failed.'
    }
}

function Invoke-MysqlDatabase {
    param(
        [Parameter(Mandatory)]
        [string]$Sql,
        [Parameter(Mandatory)]
        [string]$TargetDatabase
    )

    $composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + @(
        'exec',
        '-T',
        '-e',
        "MYSQL_TARGET_DATABASE=$TargetDatabase",
        'mysql',
        'sh',
        '-lc',
        'mysql --default-character-set=utf8mb4 -N -B -uroot -p"$MYSQL_ROOT_PASSWORD" -D "$MYSQL_TARGET_DATABASE"'
    )
    $Sql | & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'MySQL command failed.'
    }
}

function Invoke-MysqlFile {
    param(
        [Parameter(Mandatory)]
        [System.IO.FileInfo]$File,
        [Parameter(Mandatory)]
        [string]$TargetDatabase
    )

    $sql = Get-Content -Path $File.FullName -Raw -Encoding UTF8
    $sql = $sql -replace '`pricing_system2\.0`', "``$TargetDatabase``"
    $composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + @(
        'exec',
        '-T',
        '-e',
        "MYSQL_TARGET_DATABASE=$TargetDatabase",
        'mysql',
        'sh',
        '-lc',
        'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" -D "$MYSQL_TARGET_DATABASE"'
    )
    $sql | & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to apply SQL file: $($File.Name)"
    }
}

Assert-CommandAvailable 'docker'

$migrationRoot = Resolve-RepoPath $MigrationsDirectory
$schemaPath = Join-Path $migrationRoot 'schema.sql'
if (-not (Test-Path $schemaPath)) {
    throw "Missing base schema: $schemaPath"
}

$schemaFile = Get-Item $schemaPath
$migrationFiles = Get-ChildItem -Path $migrationRoot -Filter 'migration_*.sql' | Sort-Object Name
$targetDatabase = if ([string]::IsNullOrWhiteSpace($DatabaseName)) {
    "pricing_clean_verify_$((Get-Date).ToString('yyyyMMddHHmmss'))"
} else {
    $DatabaseName.Trim()
}
$databaseCreated = $false
$startedAt = (Get-Date).ToUniversalTime()
$reportRoot = Resolve-RepoPath $ReportDirectory
if (-not (Test-Path $reportRoot)) {
    New-Item -ItemType Directory -Path $reportRoot | Out-Null
}
$reportPath = Join-Path $reportRoot "clean-db-verification-$($startedAt.ToString('yyyyMMddTHHmmssZ')).json"
$status = 'failed'
$errorMessage = $null
$appliedMigrations = @()
$skippedMigrations = @()
$checksumRecordedMigrations = @()

if ($targetDatabase -notmatch '^[A-Za-z0-9_]+$') {
    throw "DatabaseName may only contain letters, numbers, and underscores: $targetDatabase"
}

try {
    Invoke-MysqlNoDatabase -Sql "DROP DATABASE IF EXISTS ``$targetDatabase``; CREATE DATABASE ``$targetDatabase`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    $databaseCreated = $true
    Write-Host "Created clean verification database: $targetDatabase"

    Invoke-MysqlFile -File $schemaFile -TargetDatabase $targetDatabase
    Write-Host "Applied schema.sql"

    foreach ($file in $migrationFiles) {
        $version = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
        $checksum = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $historyOutput = Invoke-MysqlDatabase -TargetDatabase $targetDatabase -Sql "SELECT checksum FROM schema_migration_history WHERE version = '$version';"
        $existingChecksum = ''
        foreach ($line in @($historyOutput)) {
            $trimmed = ([string]$line).Trim()
            if ($trimmed) {
                $existingChecksum = $trimmed
                break
            }
        }

        if ($existingChecksum) {
            if ($existingChecksum -eq ('0' * 64)) {
                Invoke-MysqlDatabase -TargetDatabase $targetDatabase -Sql "UPDATE schema_migration_history SET checksum = '$checksum' WHERE version = '$version';"
                $checksumRecordedMigrations += $file.Name
                Write-Host "Baseline migration checksum recorded: $($file.Name)"
            } elseif ($existingChecksum -ne $checksum) {
                throw "Checksum mismatch for baseline migration '$version'. Expected $existingChecksum but local file is $checksum."
            } else {
                Write-Host "Migration already represented in schema baseline: $($file.Name)"
            }
            $skippedMigrations += $file.Name
            continue
        }

        Invoke-MysqlFile -File $file -TargetDatabase $targetDatabase
        Invoke-MysqlDatabase -TargetDatabase $targetDatabase -Sql "INSERT INTO schema_migration_history (version, checksum, description) VALUES ('$version', '$checksum', '$version');"
        $appliedMigrations += $file.Name
        Write-Host "Applied migration: $($file.Name)"
    }

    $status = 'passed'
    Write-Host "Clean database verification passed: $targetDatabase"
} catch {
    $errorMessage = $_.Exception.Message
    throw
} finally {
    if ($databaseCreated -and -not $KeepDatabase) {
        try {
            Invoke-MysqlNoDatabase -Sql "DROP DATABASE IF EXISTS ``$targetDatabase``;"
            Write-Host "Dropped clean verification database: $targetDatabase"
        } catch {
            Write-Warning "Failed to drop clean verification database '$targetDatabase': $($_.Exception.Message)"
        }
    }
    $finishedAt = (Get-Date).ToUniversalTime()
    $report = [ordered]@{
        startedAt = $startedAt.ToString('o')
        finishedAt = $finishedAt.ToString('o')
        status = $status
        databaseName = $targetDatabase
        schema = 'schema.sql'
        migrationCount = $migrationFiles.Count
        appliedMigrations = $appliedMigrations
        skippedBaselineMigrations = $skippedMigrations
        checksumRecordedMigrations = $checksumRecordedMigrations
        keptDatabase = [bool]$KeepDatabase
        error = $errorMessage
    }
    $report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding UTF8
    Write-Host "Clean database verification report: $reportPath"
}
