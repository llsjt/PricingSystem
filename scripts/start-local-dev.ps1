$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot 'frontend'
$javaDir = Join-Path $repoRoot 'backend-java'
$pythonDir = Join-Path $repoRoot 'backend-python'
$venvPython = Join-Path $pythonDir '.venv\Scripts\python.exe'

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}
if (-not (Test-Path $javaDir)) {
    throw "Java backend directory not found: $javaDir"
}
if (-not (Test-Path $pythonDir)) {
    throw "Python backend directory not found: $pythonDir"
}
if (-not (Test-Path $venvPython)) {
    throw "Python virtual environment not found: $venvPython"
}

function Start-LegacyPowerShellWindow {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    Start-Process powershell `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList @(
            '-NoExit',
            '-ExecutionPolicy', 'Bypass',
            '-Command', $Command
        )
}

$tabSpecs = @(
    @{
        Title = 'Frontend'
        Directory = $frontendDir
        Command = 'npm.cmd run dev'
    },
    @{
        Title = 'Backend-Java'
        Directory = $javaDir
        Command = 'mvn.cmd spring-boot:run'
    },
    @{
        Title = 'Backend-Python'
        Directory = $pythonDir
        Command = ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
    }
)

$wtCommand = Get-Command wt.exe -ErrorAction SilentlyContinue
if ($wtCommand) {
    $wtArgs = @()

    foreach ($tab in $tabSpecs) {
        if ($wtArgs.Count -gt 0) {
            $wtArgs += ';'
        }

        $wtArgs += @(
            'new-tab',
            '--title', $tab.Title,
            '-d', $tab.Directory,
            'powershell',
            '-NoExit',
            '-ExecutionPolicy', 'Bypass',
            '-Command', $tab.Command
        )
    }

    & $wtCommand.Source @wtArgs
    return
}

foreach ($tab in $tabSpecs) {
    Start-LegacyPowerShellWindow -WorkingDirectory $tab.Directory -Command $tab.Command
}
