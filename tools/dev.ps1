param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "migrate", "seed", "test-backend", "test-flutter", "check", "smoke-web", "smoke-providers", "reset-pipeline", "clean-state")]
    [string]$Command,
    [switch]$UseWslDocker
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

. (Join-Path $Root "scripts\lib-dev.ps1")
Initialize-CollectarrDocker -UseWslDocker:$UseWslDocker

function Invoke-Compose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    Invoke-ComposeChecked -Arguments $Arguments
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
        & "$Root\scripts\dev-smoke-web.ps1" -UseWslDocker:$UseWslDocker
    }
    "smoke-providers" {
        & "$Root\scripts\dev-smoke-providers.ps1" -UseWslDocker:$UseWslDocker
    }
    "reset-pipeline" {
        & "$Root\scripts\dev-reset-pipeline.ps1" -Force -UseWslDocker:$UseWslDocker
    }
    "clean-state" {
        & "$Root\scripts\dev-clean-state.ps1" -All -Force -UseWslDocker:$UseWslDocker
    }
}
