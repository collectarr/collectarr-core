param(
  [switch]$WithSync,
  [switch]$KeepImages,
  [switch]$KeepSearchIndex,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path "docker-compose.yml")) {
  throw "Run this script from the Collectarr repository."
}

if (-not $Force) {
  Write-Host "This will stop Collectarr and delete the local PostgreSQL dev volume." -ForegroundColor Yellow
  Write-Host "Use -KeepImages to preserve MinIO images and -KeepSearchIndex to preserve Meilisearch data."
  $answer = Read-Host "Type RESET to continue"
  if ($answer -ne "RESET") {
    Write-Host "Cancelled."
    exit 0
  }
}

$composeProfileArgs = @()
if ($WithSync) {
  $composeProfileArgs = @("--profile", "sync")
}

function Invoke-Compose {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  & docker @("compose") @composeProfileArgs @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
  }
}

Invoke-Compose down

$volumes = @("collectarr_postgres_data")
if (-not $KeepSearchIndex) {
  $volumes += "collectarr_meili_data"
}
if (-not $KeepImages) {
  $volumes += "collectarr_minio_data"
}
if ($WithSync) {
  $volumes += "collectarr_sync_data"
}

foreach ($volume in $volumes) {
  $existing = docker volume ls --quiet --filter "name=^$volume$"
  if ($existing) {
    docker volume rm $volume | Out-Host
  }
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

Invoke-Compose up --build -d postgres redis meilisearch minio
Invoke-Compose run --rm api alembic upgrade head
Invoke-Compose run --rm api python -m app.commands.seed_comics
Invoke-Compose up --build -d

Write-Host "Collectarr dev stack reset complete." -ForegroundColor Green
Write-Host "API:  http://localhost:8010"
Write-Host "Sync: http://localhost:8020 (when -WithSync is used)"
