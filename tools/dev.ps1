param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "migrate", "seed", "test-backend", "test-flutter", "check", "smoke-web", "smoke-providers", "reset-pipeline", "clean-state")]
    [string]$Command
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$script:UseWslDockerResolved = $false
& docker version --format "{{.Server.Version}}" *> $null
if ($LASTEXITCODE -ne 0) {
    & wsl docker version --format "{{.Server.Version}}" *> $null
    if ($LASTEXITCODE -eq 0) {
        $script:UseWslDockerResolved = $true
        Write-Host "Using WSL Docker Engine." -ForegroundColor Cyan
    }
}

function Invoke-Docker {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    if ($script:UseWslDockerResolved) {
        & wsl docker @Arguments
    } else {
        & docker @Arguments
    }
}

function Invoke-Compose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    $composeArgs = @("compose") + $Arguments
    Invoke-Docker @composeArgs
}

switch ($Command) {
    "start" {
        Invoke-Compose @("up", "--build")
    }
    "stop" {
        Invoke-Compose @("down")
    }
    "migrate" {
        Invoke-Compose @("exec", "api", "alembic", "upgrade", "head")
    }
    "seed" {
        Invoke-Compose @("exec", "api", "python", "-m", "app.scripts.seed_comics")
    }
    "test-backend" {
        Push-Location "$Root\backend"
        try { python -m pytest } finally { Pop-Location }
    }
    "test-flutter" {
        Push-Location "$Root\frontend"
        try {
            flutter pub get
            dart run build_runner build --delete-conflicting-outputs
            flutter analyze
            flutter test
        } finally { Pop-Location }
    }
    "check" {
        Invoke-Compose @("config", "--quiet")
        Push-Location "$Root\backend"
        try {
            python -m ruff check .
            python -m compileall app alembic tests
        } finally { Pop-Location }
    }
    "smoke-web" {
        & "$Root\scripts\dev-smoke-web.ps1"
    }
    "smoke-providers" {
        & "$Root\scripts\dev-smoke-providers.ps1"
    }
    "reset-pipeline" {
        & "$Root\scripts\dev-reset-pipeline.ps1" -Force
    }
    "clean-state" {
        & "$Root\scripts\dev-clean-state.ps1" -All -Force
    }
}
