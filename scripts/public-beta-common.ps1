Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Resolve-RepoPath {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path (Get-RepoRoot) $Path
}

function Assert-CommandAvailable {
    param(
        [Parameter(Mandatory)]
        [string]$Command
    )

    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Required command '$Command' was not found in PATH."
    }
}

function Read-EnvFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $resolvedPath = Resolve-RepoPath $Path
    if (-not (Test-Path $resolvedPath)) {
        throw "Env file not found: $resolvedPath"
    }

    $envMap = @{}
    foreach ($line in Get-Content $resolvedPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf('=')
        if ($separatorIndex -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $envMap[$key] = $value
    }

    return $envMap
}

function Get-ComposeArguments {
    param(
        [string]$ComposeFile = 'docker-compose.public-beta.yml',
        [string]$EnvFile = '.env.public-beta'
    )

    $resolvedComposeFile = Resolve-RepoPath $ComposeFile
    $resolvedEnvFile = Resolve-RepoPath $EnvFile

    if (-not (Test-Path $resolvedComposeFile)) {
        throw "Compose file not found: $resolvedComposeFile"
    }
    if (-not (Test-Path $resolvedEnvFile)) {
        throw "Env file not found: $resolvedEnvFile"
    }

    return @('compose', '--env-file', $resolvedEnvFile, '-f', $resolvedComposeFile)
}

function Invoke-DockerCompose {
    param(
        [string]$ComposeFile = 'docker-compose.public-beta.yml',
        [string]$EnvFile = '.env.public-beta',
        [Parameter(Mandatory)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )

    Assert-CommandAvailable 'docker'
    $composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + $Arguments
    & docker @composeArgs
    if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
        throw "docker compose command failed: $($Arguments -join ' ')"
    }
}

function Invoke-DockerComposeCapture {
    param(
        [string]$ComposeFile = 'docker-compose.public-beta.yml',
        [string]$EnvFile = '.env.public-beta',
        [Parameter(Mandatory)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )

    Assert-CommandAvailable 'docker'
    $composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + $Arguments
    $output = & docker @composeArgs
    if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
        throw "docker compose command failed: $($Arguments -join ' ')"
    }
    return $output
}

function Invoke-MysqlQuery {
    param(
        [Parameter(Mandatory)]
        [string]$Sql,
        [string]$ComposeFile = 'docker-compose.public-beta.yml',
        [string]$EnvFile = '.env.public-beta',
        [switch]$WithoutDatabase,
        [switch]$AllowFailure
    )

    $mysqlCommand = if ($WithoutDatabase) {
        'mysql --default-character-set=utf8mb4 -N -B -uroot -p"$MYSQL_ROOT_PASSWORD"'
    } else {
        'mysql --default-character-set=utf8mb4 -N -B -uroot -p"$MYSQL_ROOT_PASSWORD" -D "$MYSQL_DATABASE"'
    }

    $composeArgs = (Get-ComposeArguments -ComposeFile $ComposeFile -EnvFile $EnvFile) + @('exec', '-T', 'mysql', 'sh', '-lc', $mysqlCommand)
    $output = $Sql | & docker @composeArgs
    if (-not $AllowFailure -and $LASTEXITCODE -ne 0) {
        throw "MySQL command failed."
    }
    return $output
}

function Wait-Until {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Test,
        [Parameter(Mandatory)]
        [string]$Description,
        [int]$TimeoutSeconds = 120,
        [int]$IntervalSeconds = 3
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            if (& $Test) {
                return
            }
        } catch {
        }
        Start-Sleep -Seconds $IntervalSeconds
    }

    throw "Timed out while waiting for $Description."
}

function Test-HttpReady {
    param(
        [Parameter(Mandatory)]
        [string]$Url
    )

    $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 5 -UseBasicParsing
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 300
}

function Get-BackupDirectory {
    param(
        [string]$Path = 'backups/public-beta'
    )

    $resolved = Resolve-RepoPath $Path
    if (-not (Test-Path $resolved)) {
        New-Item -ItemType Directory -Path $resolved | Out-Null
    }
    return $resolved
}

function Get-RequiredPublicBetaVariables {
    return @(
        'DB_PASSWORD',
        'JWT_SECRET',
        'JWT_REFRESH_SECRET',
        'INTERNAL_API_TOKEN',
        'ALLOWED_ORIGINS'
    )
}

function Assert-RequiredPublicBetaVariables {
    param(
        [Parameter(Mandatory)]
        [hashtable]$EnvMap
    )

    foreach ($key in Get-RequiredPublicBetaVariables) {
        $value = ''
        if ($EnvMap.ContainsKey($key) -and $EnvMap[$key]) {
            $value = [string]$EnvMap[$key]
        }
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "Required env var '$key' is missing or blank in the public beta env file."
        }
        if ($value -match 'change-me|example|replace|your-') {
            throw "Required env var '$key' still looks like a placeholder value."
        }
    }
}
