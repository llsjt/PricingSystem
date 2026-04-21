param(
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [int]$LoginAuditRetentionDays = 180,
    [int]$RefreshSessionRetentionDays = 30,
    [int]$TaskRetentionDays = 365,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

$loginAuditRetentionDays = [Math]::Max($LoginAuditRetentionDays, 1)
$refreshSessionRetentionDays = [Math]::Max($RefreshSessionRetentionDays, 1)
$taskRetentionDays = [Math]::Max($TaskRetentionDays, 1)

$previewSql = @"
SELECT 'login_audit_log', COUNT(*) FROM login_audit_log
 WHERE created_at < DATE_SUB(NOW(), INTERVAL $loginAuditRetentionDays DAY)
UNION ALL
SELECT 'auth_refresh_session', COUNT(*) FROM auth_refresh_session
 WHERE expires_at < NOW() OR created_at < DATE_SUB(NOW(), INTERVAL $refreshSessionRetentionDays DAY)
UNION ALL
SELECT 'terminal_pricing_task', COUNT(*) FROM pricing_task
 WHERE task_status IN ('COMPLETED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED')
   AND completed_at IS NOT NULL
   AND completed_at < DATE_SUB(NOW(), INTERVAL $taskRetentionDays DAY);
"@

Write-Host 'Retention preview:'
Invoke-MysqlQuery -Sql $previewSql -ComposeFile $ComposeFile -EnvFile $EnvFile

if (-not $Apply) {
    Write-Host 'Preview only. Re-run with -Apply to delete expired rows.'
    return
}

$deleteSql = @"
START TRANSACTION;
DELETE FROM login_audit_log
 WHERE created_at < DATE_SUB(NOW(), INTERVAL $loginAuditRetentionDays DAY);

DELETE FROM auth_refresh_session
 WHERE expires_at < NOW()
    OR created_at < DATE_SUB(NOW(), INTERVAL $refreshSessionRetentionDays DAY);

DELETE pr FROM pricing_result pr
JOIN pricing_task pt ON pt.id = pr.task_id
WHERE pt.task_status IN ('COMPLETED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED')
  AND pt.completed_at IS NOT NULL
  AND pt.completed_at < DATE_SUB(NOW(), INTERVAL $taskRetentionDays DAY);

DELETE arl FROM agent_run_log arl
JOIN pricing_task pt ON pt.id = arl.task_id
WHERE pt.task_status IN ('COMPLETED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED')
  AND pt.completed_at IS NOT NULL
  AND pt.completed_at < DATE_SUB(NOW(), INTERVAL $taskRetentionDays DAY);

DELETE FROM pricing_task
 WHERE task_status IN ('COMPLETED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED')
   AND completed_at IS NOT NULL
   AND completed_at < DATE_SUB(NOW(), INTERVAL $taskRetentionDays DAY);
COMMIT;
"@

Invoke-MysqlQuery -Sql $deleteSql -ComposeFile $ComposeFile -EnvFile $EnvFile | Out-Null
Write-Host 'Retention policy applied successfully.'
