param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "migrate", "seed", "seed-providers", "seed-showcase", "test", "check", "smoke-providers", "reset-stack", "clean-state")]
    [string]$Command,
    [switch]$UseWslDocker,
    [switch]$WithSync
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

    $prefixArguments = @()
    if ($WithSync) {
        $prefixArguments = @("-f", "docker-compose.yml", "-f", "docker-compose.devstack.yml")
    }
    Invoke-ComposeChecked -PrefixArguments $prefixArguments -Arguments $Arguments
}

switch ($Command) {
    "start" {
        Invoke-Compose @("up", "--build")
    }
    "stop" {
        Invoke-Compose @("down")
    }
    "migrate" {
        Invoke-CollectarrSchemaSetup -RepoRoot $Root -WithSync:$WithSync
    }
    "seed" {
        Invoke-Compose @("exec", "api", "python", "-m", "app.scripts.seed_full", "--wipe")
    }
    "seed-providers" {
        Invoke-Compose @("exec", "api", "python", "-m", "app.scripts.seed_provider_catalog", "--profile", "smoke", "--skip-existing")
    }
    "seed-showcase" {
        Invoke-Compose @("exec", "api", "python", "-m", "app.scripts.seed_provider_catalog", "--profile", "showcase", "--skip-existing")
    }
    "test" {
        python -m pytest
    }
    "check" {
        Invoke-Compose @("config", "--quiet")
        python -m ruff check .
        python -m compileall app alembic tests
    }
    "smoke-providers" {
        & "$Root\scripts\dev-smoke-providers.ps1" -UseWslDocker:$UseWslDocker
    }
    "reset-stack" {
        & "$Root\scripts\dev-reset-stack.ps1" -Force -UseWslDocker:$UseWslDocker -WithSync:$WithSync
    }
    "clean-state" {
        & "$Root\scripts\dev-clean-state.ps1" -All -Force -UseWslDocker:$UseWslDocker -WithSync:$WithSync
    }
}
