[CmdletBinding()]
param(
    [string]$RuntimeReportDirectory = 'ops/reports/runtime',
    [switch]$RequireExternalEvidence
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

function Test-PathGate {
    param(
        [Parameter(Mandatory)]
        [string]$Id,
        [Parameter(Mandatory)]
        [string]$Description,
        [Parameter(Mandatory)]
        [string[]]$Paths,
        [bool]$Required = $true
    )

    $missing = @()
    foreach ($path in $Paths) {
        $resolved = Resolve-RepoPath $path
        if (-not (Test-Path $resolved)) {
            $missing += $path
        }
    }

    return [ordered]@{
        id = $Id
        description = $Description
        status = if ($missing.Count -eq 0) { 'passed' } elseif ($Required) { 'failed' } else { 'missing_external_evidence' }
        missing = $missing
    }
}

function Test-ReportPatternGate {
    param(
        [Parameter(Mandatory)]
        [string]$Id,
        [Parameter(Mandatory)]
        [string]$Description,
        [Parameter(Mandatory)]
        [string]$Directory,
        [Parameter(Mandatory)]
        [string]$Pattern,
        [bool]$Required = $true
    )

    $resolvedDir = Resolve-RepoPath $Directory
    $matches = @()
    if (Test-Path $resolvedDir) {
        $matches = @(Get-ChildItem -Path $resolvedDir -Filter $Pattern -File)
    }

    return [ordered]@{
        id = $Id
        description = $Description
        status = if ($matches.Count -gt 0) { 'passed' } elseif ($Required) { 'failed' } else { 'missing_external_evidence' }
        missing = if ($matches.Count -gt 0) { @() } else { @("$Directory/$Pattern") }
    }
}

function Test-JsonReportGate {
    param(
        [Parameter(Mandatory)]
        [string]$Id,
        [Parameter(Mandatory)]
        [string]$Description,
        [Parameter(Mandatory)]
        [string]$Directory,
        [Parameter(Mandatory)]
        [string]$Pattern,
        [Parameter(Mandatory)]
        [scriptblock]$Predicate,
        [bool]$Required = $true
    )

    $resolvedDir = Resolve-RepoPath $Directory
    $matches = @()
    if (Test-Path $resolvedDir) {
        $matches = @(Get-ChildItem -Path $resolvedDir -Filter $Pattern -File | Sort-Object LastWriteTimeUtc -Descending)
    }
    if ($matches.Count -eq 0) {
        return [ordered]@{
            id = $Id
            description = $Description
            status = if ($Required) { 'failed' } else { 'missing_external_evidence' }
            missing = @("$Directory/$Pattern")
        }
    }

    foreach ($file in $matches) {
        try {
            $json = Get-Content -Raw -Path $file.FullName | ConvertFrom-Json
            if (& $Predicate $json) {
                return [ordered]@{
                    id = $Id
                    description = $Description
                    status = 'passed'
                    missing = @()
                    evidence = $file.FullName
                }
            }
        } catch {
        }
    }

    return [ordered]@{
        id = $Id
        description = $Description
        status = if ($Required) { 'failed' } else { 'missing_external_evidence' }
        missing = @("$Directory/$Pattern with passing content")
    }
}

$externalRequired = [bool]$RequireExternalEvidence
$checks = @(
    (Test-PathGate -Id 'S0-S3-code' -Description 'P0/P1 core implementation files exist' -Paths @(
        'backend-python/app/services/result_finalization_service.py',
        'backend-python/app/domain/final_decision_verifier.py',
        'backend-python/app/services/resume_fingerprint.py',
        'backend-python/app/services/runtime_metrics.py',
        'backend-java/src/main/java/com/example/pricing/service/PricingTaskStreamService.java',
        'frontend/src/utils/agentOpinion.ts'
    )),
    (Test-PathGate -Id 'S1-tests' -Description 'Regression and contract tests exist' -Paths @(
        'backend-python/tests/test_result_finalization_service.py',
        'backend-python/tests/test_final_decision_verifier.py',
        'backend-python/tests/test_resume_service.py',
        'backend-python/tests/test_progress_event_service.py',
        'backend-java/src/test/java/com/example/pricing/service/PricingTaskStreamServiceTest.java',
        'frontend/dev/test-decision-display.mjs'
    )),
    (Test-PathGate -Id 'S5-ops-scripts' -Description 'DB, alert, and gray rollout scripts exist' -Paths @(
        'scripts/check-db-migration-gates.ps1',
        'scripts/verify-clean-db-migrations.ps1',
        'scripts/check-operational-alerts.py',
        'scripts/observe-gray-rollout.py',
        'database/rollback_baseline_waivers.txt'
    )),
    (Test-PathGate -Id 'S5-docs' -Description 'Runbooks and progress records exist' -Paths @(
        'ops/public-beta-runbook.md',
        'ops/alert-thresholds.md',
        'ops/pre-launch-checklist.md',
        'task_plan.md',
        'findings.md',
        'progress.md'
    )),
    (Test-PathGate -Id 'M4-P2-physical-split' -Description 'P2 Agent output and prompt modules exist' -Paths @(
        'backend-python/app/application/dispatch_service.py',
        'backend-python/app/application/task_execution_service.py',
        'backend-python/app/application/result_finalization_service.py',
        'backend-python/app/application/task_recovery_service.py',
        'backend-python/app/agent/definitions.py',
        'backend-python/app/agent/orchestration_service.py',
        'backend-python/app/agent_outputs/parser.py',
        'backend-python/app/agent_outputs/normalizer.py',
        'backend-python/app/agent_outputs/card_mapper.py',
        'backend-python/app/agent_prompts/pricing_prompt_builder.py',
        'backend-python/app/agent_prompts/prompt_versions.py',
        'backend-python/app/agent_tools/registry.py',
        'backend-python/app/agent_tools/pricing_tools.py',
        'backend-python/app/infra/rabbitmq_worker.py',
        'backend-python/app/infra/progress_event_publisher.py'
    )),
    (Test-PathGate -Id 'M3-failover-and-cancellation' -Description 'LLM failover and graceful cancellation modules/tests exist' -Paths @(
        'backend-python/app/infra/llm_client.py',
        'backend-python/app/application/cancellation_checker.py',
        'backend-python/tests/test_llm_failover.py',
        'backend-python/tests/test_concurrency_race.py',
        'backend-python/tests/test_session_isolation.py',
        'backend-python/tests/manual/test_llm_prompt_regression.py'
    )),
    (Test-PathGate -Id 'S7-record-template' -Description 'S7 external evidence template exists' -Paths @(
        'ops/reports/runtime/s7-gray-rollout-record.template.md'
    )),
    (Test-JsonReportGate -Id 'S7-gray-summary' -Description '30-60 minute gray rollout summary passed' -Directory $RuntimeReportDirectory -Pattern 'gray-rollout-summary-*.json' -Required $externalRequired -Predicate {
        param($json)
        [int]$json.breachCount -eq 0 -and [double]$json.durationSeconds -ge 1800
    }),
    (Test-ReportPatternGate -Id 'S7-gray-samples' -Description '30-60 minute gray rollout samples exist' -Directory $RuntimeReportDirectory -Pattern 'gray-rollout-samples-*.jsonl' -Required $externalRequired),
    (Test-JsonReportGate -Id 'S7-clean-db' -Description 'Clean database schema+migration rehearsal passed' -Directory $RuntimeReportDirectory -Pattern 'clean-db-verification-*.json' -Required $externalRequired -Predicate {
        param($json)
        [string]$json.status -eq 'passed'
    }),
    (Test-ReportPatternGate -Id 'S7-backup' -Description 'Production/staging database backup artifact exists' -Directory 'backups/public-beta' -Pattern '*.sql' -Required $externalRequired),
    (Test-ReportPatternGate -Id 'S7-filled-record' -Description 'Filled S7 rollout record exists' -Directory $RuntimeReportDirectory -Pattern 's7-gray-rollout-record-*.md' -Required $externalRequired)
)

$failed = @($checks | Where-Object { $_.status -eq 'failed' })
$missingExternal = @($checks | Where-Object { $_.status -eq 'missing_external_evidence' })
$report = [ordered]@{
    generatedAt = (Get-Date).ToUniversalTime().ToString('o')
    requireExternalEvidence = $externalRequired
    status = if ($failed.Count -eq 0 -and $missingExternal.Count -eq 0) {
        'complete'
    } elseif ($failed.Count -eq 0) {
        'local_gates_passed_external_evidence_missing'
    } else {
        'failed'
    }
    checks = $checks
}

$json = $report | ConvertTo-Json -Depth 8
Write-Output $json

if ($failed.Count -gt 0 -or ($externalRequired -and $missingExternal.Count -gt 0)) {
    exit 1
}
