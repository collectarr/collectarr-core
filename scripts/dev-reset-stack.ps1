param(
  [switch]$KeepImages,
  [switch]$KeepSearchIndex,
  [switch]$UseWslDocker,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib-dev.ps1")
Set-Location $repoRoot

if (-not (Test-Path "docker-compose.yml")) {
  throw "Run this script from the Collectarr repository."
}

Initialize-CollectarrDocker -UseWslDocker:$UseWslDocker

if (-not $Force) {
  Write-Host "This will stop Collectarr and delete the local PostgreSQL dev volume." -ForegroundColor Yellow
  Write-Host "Use -KeepImages to preserve MinIO images and -KeepSearchIndex to preserve Meilisearch data."
  $answer = Read-Host "Type RESET to continue"
  if ($answer -ne "RESET") {
    Write-Host "Cancelled."
    exit 0
  }
}

function Invoke-Compose {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  Invoke-ComposeChecked -Arguments $Arguments
}

Invoke-Compose @("down")

$volumes = @("collectarr_postgres_data")
if (-not $KeepSearchIndex) {
  $volumes += "collectarr_meili_data"
}
if (-not $KeepImages) {
  $volumes += "collectarr_minio_data"
}

foreach ($volume in $volumes) {
  $existing = Invoke-DockerText @("volume", "ls", "--quiet", "--filter", "name=^$volume$")
  if ($existing) {
    Invoke-Docker @("volume", "rm", $volume) | Out-Host
    if ($LASTEXITCODE -ne 0) {
      throw "docker volume rm $volume failed with exit code $LASTEXITCODE"
    }
  }
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

Invoke-Compose @("up", "--build", "-d", "postgres", "redis", "meilisearch", "minio")
Invoke-Compose @("run", "--rm", "api", "alembic", "upgrade", "head")
Invoke-Compose @("run", "--rm", "api", "python", "-m", "app.scripts.seed_comics")
Invoke-Compose @("up", "--build", "-d")

Write-Host "Collectarr dev stack reset complete." -ForegroundColor Green
Write-Host "API:  http://localhost:8010"
