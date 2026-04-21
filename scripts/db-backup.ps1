[CmdletBinding()]
param(
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [string]$OutputDirectory = 'backups/public-beta',
    [string]$FileName
)

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

$envMap = Read-EnvFile -Path $EnvFile
$databaseName = if ($envMap.ContainsKey('MYSQL_DATABASE') -and $envMap['MYSQL_DATABASE']) {
    $envMap['MYSQL_DATABASE']
} else {
    'pricing_system2.0'
}

$backupDirectory = Get-BackupDirectory -Path $OutputDirectory
if (-not $FileName) {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $FileName = "$databaseName-$timestamp.sql"
}
$backupPath = Join-Path $backupDirectory $FileName

$composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + @(
    'exec',
    '-T',
    'mysql',
    'sh',
    '-lc',
    'mysqldump --default-character-set=utf8mb4 --databases "$MYSQL_DATABASE" --single-transaction --set-gtid-purged=OFF --routines --triggers -uroot -p"$MYSQL_ROOT_PASSWORD"'
)

Assert-CommandAvailable 'docker'
& docker @composeArgs | Out-File -FilePath $backupPath -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create backup at $backupPath"
}

Write-Host "Backup written to $backupPath"
