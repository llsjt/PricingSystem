[CmdletBinding()]
param(
    [string]$ComposeFile = 'docker-compose.public-beta.yml',
    [string]$EnvFile = '.env.public-beta',
    [switch]$SkipBuild,
    [switch]$SkipMigrations
)

. (Join-Path $PSScriptRoot 'public-beta-common.ps1')

$envMap = Read-EnvFile -Path $EnvFile
Assert-RequiredPublicBetaVariables -EnvMap $envMap

$javaPort = 8080
if ($envMap.ContainsKey('JAVA_PUBLIC_PORT') -and $envMap['JAVA_PUBLIC_PORT']) {
    $javaPort = [int][string]$envMap['JAVA_PUBLIC_PORT']
}

$frontendPort = 8081
if ($envMap.ContainsKey('FRONTEND_PUBLIC_PORT') -and $envMap['FRONTEND_PUBLIC_PORT']) {
    $frontendPort = [int][string]$envMap['FRONTEND_PUBLIC_PORT']
}

$upArguments = @('up', '-d')
if (-not $SkipBuild) {
    $upArguments += '--build'
}

Invoke-DockerCompose -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments $upArguments

Wait-Until -Description 'MySQL' -Test {
    Invoke-MysqlQuery -ComposeFile $ComposeFile -EnvFile $EnvFile -Sql 'SELECT 1;' -AllowFailure | Out-Null
    return $LASTEXITCODE -eq 0
}

if (-not $SkipMigrations) {
    & (Join-Path $PSScriptRoot 'apply-db-migrations.ps1') -ComposeFile $ComposeFile -EnvFile $EnvFile
}

Wait-Until -Description 'Python worker health endpoint' -Test {
    $output = Invoke-DockerComposeCapture -ComposeFile $ComposeFile -EnvFile $EnvFile -Arguments @(
        'exec',
        '-T',
        'backend-python',
        'python',
        '-c',
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5)"
    ) -AllowFailure
    return $LASTEXITCODE -eq 0
}

Wait-Until -Description 'Java backend readiness endpoint' -Test {
    return Test-HttpReady -Url "http://127.0.0.1:$javaPort/api/health/ready"
}

Wait-Until -Description 'Frontend readiness endpoint' -Test {
    return Test-HttpReady -Url "http://127.0.0.1:$frontendPort/"
}

Write-Host "Public beta stack is ready."
Write-Host "Java API: http://127.0.0.1:$javaPort"
Write-Host "Frontend: http://127.0.0.1:$frontendPort"
