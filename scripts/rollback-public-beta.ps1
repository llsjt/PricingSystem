[CmdletBinding()]
param(
    [string]$BackupFile,
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [string]$BackupDirectory = 'backups/public-beta'
)

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

if (-not $BackupFile) {
    $backupRoot = Get-BackupDirectory -Path $BackupDirectory
    $latestBackup = Get-ChildItem -Path $backupRoot -Filter '*.sql' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if (-not $latestBackup) {
        throw "No backup file was provided and no backup was found in $backupRoot"
    }
    $BackupFile = $latestBackup.FullName
}

& (Join-Path $PSScriptRoot 'db-restore.ps1') `
    -BackupFile $BackupFile `
    -ComposeFile $ComposeFile `
    -EnvFile $EnvFile `
    -Force `
    -SkipPreBackup

Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @('up', '-d', 'backend-python', 'backend-java', 'frontend')

Write-Host "Rollback completed with backup $BackupFile"
