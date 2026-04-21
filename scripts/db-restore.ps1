[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$BackupFile,
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [switch]$Force,
    [switch]$SkipPreBackup,
    [switch]$SkipMigrations
)

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

$resolvedBackupFile = Resolve-RepoPath $BackupFile
if (-not (Test-Path $resolvedBackupFile)) {
    throw "Backup file not found: $resolvedBackupFile"
}

if (-not $Force) {
    throw "Database restore is destructive. Re-run with -Force to continue."
}

if (-not $SkipPreBackup) {
    & (Join-Path $PSScriptRoot 'db-backup.ps1') -ComposeFile $ComposeFile -EnvFile $EnvFile | Out-Null
}

Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @('up', '-d', 'mysql')
Wait-Until -Description 'MySQL to accept connections' -Test {
    Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql 'SELECT 1;' -AllowFailure | Out-Null
    return $LASTEXITCODE -eq 0
}

$containerPath = "/tmp/$([System.IO.Path]::GetFileName($resolvedBackupFile))"
Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @('cp', $resolvedBackupFile, "mysql:$containerPath")
Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @(
    'exec',
    '-T',
    'mysql',
    'sh',
    '-lc',
    "mysql --default-character-set=utf8mb4 -uroot -p`"`$MYSQL_ROOT_PASSWORD`" < $containerPath && rm -f $containerPath"
)

if (-not $SkipMigrations) {
    & (Join-Path $PSScriptRoot 'apply-db-migrations.ps1') -ComposeFile $ComposeFile -EnvFile $EnvFile
}

Write-Host "Database restore completed from $resolvedBackupFile"
