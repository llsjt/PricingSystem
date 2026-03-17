# Starts the frontend, Java backend, and Python agent for local development.

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Start Development Environment" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendJavaDir = Join-Path $projectRoot "backend-java"
$backendPythonDir = Join-Path $projectRoot "backend-python"
$frontendDir = Join-Path $projectRoot "frontend"
$venvPython = Join-Path $backendPythonDir ".venv\Scripts\python.exe"

Write-Host "`n[1/5] Checking Java..." -ForegroundColor Yellow
try {
    $javaVersion = java -version 2>&1 | Select-String "version"
    Write-Host "OK Java installed: $javaVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Java was not found. Please install JDK 21+." -ForegroundColor Red
    exit 1
}

Write-Host "`n[2/5] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "OK Node.js installed: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Node.js was not found." -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/5] Checking Python..." -ForegroundColor Yellow
try {
    if (Test-Path $venvPython) {
        $pythonVersion = & $venvPython --version
        Write-Host "OK Project venv Python installed: $pythonVersion" -ForegroundColor Green
    } else {
        $pythonVersion = python --version
        Write-Host "OK Python installed: $pythonVersion" -ForegroundColor Green
    }
} catch {
    Write-Host "Error: Python was not found." -ForegroundColor Red
    exit 1
}

Write-Host "`n[4/5] Checking database..." -ForegroundColor Yellow
Write-Host "Make sure MySQL is running and database 'pricing_system' exists." -ForegroundColor Gray
Write-Host "If needed, initialize it with database\\schema.sql" -ForegroundColor Gray

Write-Host "`n[5/5] Starting services..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd '$backendJavaDir'
Write-Host 'Starting Spring Boot backend...' -ForegroundColor Green
mvn spring-boot:run
"@

Start-Sleep -Seconds 5

Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd '$backendPythonDir'
Write-Host 'Starting Python agent service...' -ForegroundColor Green
if (Test-Path '$venvPython') {
    & '$venvPython' -m app.main
} else {
    python -m app.main
}
"@

Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd '$frontendDir'
Write-Host 'Starting Vite frontend...' -ForegroundColor Green
npm run dev
"@

Write-Host "`nAll services have been started." -ForegroundColor Green
Write-Host "Frontend:      http://localhost:5173" -ForegroundColor Cyan
Write-Host "Java backend:  http://localhost:8080" -ForegroundColor Cyan
Write-Host "Python agent:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend proxy: /api -> http://localhost:8080" -ForegroundColor Cyan
Write-Host "`nClose the spawned PowerShell windows or press Ctrl+C there to stop services." -ForegroundColor Yellow
Write-Host "=====================================`n" -ForegroundColor Cyan
