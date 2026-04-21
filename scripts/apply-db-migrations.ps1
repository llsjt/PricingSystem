[CmdletBinding()]
param(
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [string]$MigrationsDirectory = 'database'
)

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

$envMap = Read-EnvFile -Path $EnvFile
$databaseName = if ($envMap.ContainsKey('MYSQL_DATABASE') -and $envMap['MYSQL_DATABASE']) {
    $envMap['MYSQL_DATABASE']
} else {
    'pricing_system2.0'
}

Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -WithoutDatabase -Sql "CREATE DATABASE IF NOT EXISTS ``$databaseName``;"
Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql @"
CREATE TABLE IF NOT EXISTS schema_migration_history (
    version VARCHAR(128) PRIMARY KEY,
    checksum CHAR(64) NOT NULL,
    description VARCHAR(255) NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"@

$migrationRoot = Resolve-RepoPath $MigrationsDirectory
$migrationFiles = Get-ChildItem -Path $migrationRoot -Filter 'migration_*.sql' | Sort-Object Name

$historyRowCount = [int][string](Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql 'SELECT COUNT(*) FROM schema_migration_history;')
$coreTableCount = [int][string](Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -WithoutDatabase -Sql @"
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = '$databaseName'
  AND table_name IN ('sys_user', 'product', 'pricing_task');
"@)

if ($historyRowCount -eq 0 -and $coreTableCount -gt 0) {
    foreach ($file in $migrationFiles) {
        $version = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
        Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql @"
INSERT IGNORE INTO schema_migration_history (version, checksum, description)
VALUES ('$version', REPEAT('0', 64), 'auto-baselined existing schema');
"@
    }
    Write-Host 'Existing schema detected without migration history. Historical migrations were baselined automatically.'
}

$appliedVersions = @{}
$historyOutput = Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql 'SELECT version, checksum FROM schema_migration_history ORDER BY version;'
foreach ($line in @($historyOutput)) {
    $trimmed = [string]$line
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        continue
    }
    $parts = $trimmed -split "`t"
    if ($parts.Length -ge 2) {
        $appliedVersions[$parts[0]] = $parts[1]
    }
}

foreach ($file in $migrationFiles) {
    $version = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $checksum = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $existingChecksum = ''
    if ($appliedVersions.ContainsKey($version) -and $appliedVersions[$version]) {
        $existingChecksum = [string]$appliedVersions[$version]
    }

    if ($existingChecksum) {
        if ($existingChecksum -eq ('0' * 64)) {
            Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql "UPDATE schema_migration_history SET checksum = '$checksum' WHERE version = '$version';"
            Write-Host "Baseline migration checksum recorded: $version"
            continue
        }
        if ($existingChecksum -ne $checksum) {
            throw "Checksum mismatch for applied migration '$version'. Expected $existingChecksum but local file is $checksum."
        }

        Write-Host "Migration already applied: $version"
        continue
    }

    $targetPath = "/tmp/$($file.Name)"
    Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @('cp', $file.FullName, "mysql:$targetPath")
    Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @(
        'exec',
        '-T',
        'mysql',
        'sh',
        '-lc',
        "mysql --default-character-set=utf8mb4 -uroot -p`"`$MYSQL_ROOT_PASSWORD`" -D `"`$MYSQL_DATABASE`" < $targetPath && rm -f $targetPath"
    )
    Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql "INSERT INTO schema_migration_history (version, checksum, description) VALUES ('$version', '$checksum', '$version');"
    Write-Host "Applied migration: $version"
}
