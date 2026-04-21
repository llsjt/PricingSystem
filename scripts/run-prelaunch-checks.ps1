[CmdletBinding()]
param(
    [string]$EnvFile = '.env.public-beta',
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [switch]$SkipComposeValidation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

function Write-Step {
    param(
        [Parameter(Mandatory)]
        [string]$Message
    )

    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param(
        [Parameter(Mandatory)]
        [string]$Message
    )

    Write-Host "OK   $Message" -ForegroundColor Green
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)]
        [string]$Description,
        [Parameter(Mandatory)]
        [scriptblock]$Command
    )

    Write-Step $Description
    & $Command
    Write-Success $Description
}

function Get-RepoPython {
    $venvPython = Resolve-RepoPath 'backend-python/.venv/Scripts/python.exe'
    if (Test-Path $venvPython) {
        return $venvPython
    }

    Assert-CommandAvailable 'python'
    return 'python'
}

function Get-RepoNodeCommand {
    Assert-CommandAvailable 'npm.cmd'
    return 'npm.cmd'
}

function Get-RepoMavenCommand {
    Assert-CommandAvailable 'mvn.cmd'
    return 'mvn.cmd'
}

function Test-PowerShellScripts {
    $scriptFiles = Get-ChildItem (Resolve-RepoPath 'scripts') -Filter '*.ps1' | Sort-Object Name
    foreach ($file in $scriptFiles) {
        $tokens = $null
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $file.FullName,
            [ref]$tokens,
            [ref]$errors
        ) | Out-Null
        if ($errors.Count -gt 0) {
            $errors | ForEach-Object { Write-Error $_ }
            throw "PowerShell parse failed: $($file.FullName)"
        }
    }
}

$repoRoot = Get-RepoRoot
$pythonCommand = Get-RepoPython
$npmCommand = Get-RepoNodeCommand
$mavenCommand = Get-RepoMavenCommand
$resolvedEnvFile = Resolve-RepoPath $EnvFile
$resolvedComposeFile = Resolve-RepoPath $ComposeFile

Invoke-CheckedCommand -Description 'Validate public beta env file' -Command {
    $envMap = Read-EnvFile -Path $EnvFile
    Assert-RequiredPublicBetaVariables -EnvMap $envMap
}

if (-not $SkipComposeValidation) {
    Invoke-CheckedCommand -Description 'Validate docker compose config' -Command {
        & docker compose --env-file $resolvedEnvFile -f $resolvedComposeFile config | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'docker compose config failed.'
        }
    }
}

Invoke-CheckedCommand -Description 'Validate PowerShell scripts' -Command {
    Test-PowerShellScripts
}

Invoke-CheckedCommand -Description 'Validate Python ops scripts' -Command {
    & $pythonCommand -m py_compile `
        (Resolve-RepoPath 'scripts/load-test-public-beta.py') `
        (Resolve-RepoPath 'scripts/check-operational-alerts.py')
    if ($LASTEXITCODE -ne 0) {
        throw 'Python ops script compilation failed.'
    }
}

Invoke-CheckedCommand -Description 'Run Java tests' -Command {
    Push-Location (Resolve-RepoPath 'backend-java')
    try {
        & $mavenCommand -q test
        if ($LASTEXITCODE -ne 0) {
            throw 'Java tests failed.'
        }
    } finally {
        Pop-Location
    }
}

Invoke-CheckedCommand -Description 'Run Python tests' -Command {
    Push-Location (Resolve-RepoPath 'backend-python')
    try {
        & $pythonCommand -m pytest tests -q
        if ($LASTEXITCODE -ne 0) {
            throw 'Python tests failed.'
        }
    } finally {
        Pop-Location
    }
}

Invoke-CheckedCommand -Description 'Compile Python app' -Command {
    Push-Location (Resolve-RepoPath 'backend-python')
    try {
        & $pythonCommand -m compileall app
        if ($LASTEXITCODE -ne 0) {
            throw 'Python compileall failed.'
        }
    } finally {
        Pop-Location
    }
}

Invoke-CheckedCommand -Description 'Build frontend' -Command {
    Push-Location (Resolve-RepoPath 'frontend')
    try {
        & $npmCommand run build
        if ($LASTEXITCODE -ne 0) {
            throw 'Frontend build failed.'
        }
    } finally {
        Pop-Location
    }
}

Write-Host ''
Write-Host 'All pre-launch automated checks passed.' -ForegroundColor Green
Write-Host "Repo root: $repoRoot"
Write-Host "Env file: $resolvedEnvFile"
Write-Host "Compose file: $resolvedComposeFile"
