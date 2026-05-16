param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "migrate", "seed", "test-backend", "test-flutter", "check", "smoke-web")]
    [string]$Command
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

switch ($Command) {
    "start" {
        docker compose --project-directory $Root up --build
    }
    "stop" {
        docker compose --project-directory $Root down
    }
    "migrate" {
        docker compose --project-directory $Root exec api alembic upgrade head
    }
    "seed" {
        docker compose --project-directory $Root exec api python -m app.scripts.seed_comics
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
        docker compose --project-directory $Root config --quiet
        Push-Location "$Root\backend"
        try {
            python -m ruff check .
            python -m compileall app alembic tests
        } finally { Pop-Location }
    }
    "smoke-web" {
        & "$Root\scripts\dev-smoke-web.ps1"
    }
}
