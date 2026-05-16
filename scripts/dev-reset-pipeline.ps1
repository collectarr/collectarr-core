param(
  [int]$WebPort = 8083,
  [string]$ApiBaseUrl = "http://localhost:8010",
  [string]$SyncBaseUrl = "http://localhost:8020",
  [string]$SyncKey = "collectarr-sync-dev-key",
  [switch]$KeepImages,
  [switch]$KeepSearchIndex,
  [switch]$KeepSyncData,
  [switch]$SkipSeed,
  [switch]$SkipFlutterBuild,
  [switch]$SkipProviderSmoke,
  [switch]$SkipIngestFlow,
  [switch]$UseWslDocker,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"
$envExamplePath = Join-Path $repoRoot ".env.example"
$webOriginLocalhost = "http://localhost:$WebPort"
$webOriginLoopback = "http://127.0.0.1:$WebPort"
Set-Location $repoRoot

if (-not (Test-Path "docker-compose.yml")) {
  throw "Run this script from the Collectarr repository."
}

if (-not (Test-Path $envPath)) {
  Copy-Item $envExamplePath $envPath
}

$script:UseWslDockerResolved = $UseWslDocker.IsPresent
if (-not $script:UseWslDockerResolved) {
  & docker version --format "{{.Server.Version}}" *> $null
  if ($LASTEXITCODE -ne 0) {
    & wsl docker version --format "{{.Server.Version}}" *> $null
    if ($LASTEXITCODE -eq 0) {
      $script:UseWslDockerResolved = $true
      Write-Host "Using WSL Docker Engine." -ForegroundColor Cyan
    }
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

  $composeArgs = @("compose", "--profile", "sync") + $Arguments
  Invoke-Docker @composeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
  }
}

function Wait-Endpoint {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$TimeoutSeconds = 120
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      Invoke-RestMethod -Uri $Url -TimeoutSec 8 | Out-Null
      Write-Host "OK  $Url" -ForegroundColor Green
      return
    } catch {
      Start-Sleep -Seconds 3
    }
  } while ((Get-Date) -lt $deadline)
  throw "Timed out waiting for $Url"
}

function Update-CorsOrigins {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string[]]$Origins
  )

  $lines = @(Get-Content -LiteralPath $Path)
  $index = -1
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -like "CORS_ORIGINS=*") {
      $index = $i
      break
    }
  }

  $current = @()
  if ($index -ge 0) {
    $raw = $lines[$index].Substring("CORS_ORIGINS=".Length)
    try {
      $parsed = $raw | ConvertFrom-Json
      if ($parsed -is [array]) {
        $current = @($parsed)
      } elseif ($parsed) {
        $current = @([string]$parsed)
      }
    } catch {
      $current = @()
    }
  }

  $next = New-Object System.Collections.Generic.List[string]
  foreach ($origin in @($current + $Origins)) {
    $value = [string]$origin
    if ($value -and -not $next.Contains($value)) {
      $next.Add($value)
    }
  }
  $encoded = $next.ToArray() | ConvertTo-Json -Compress

  if ($index -ge 0) {
    $lines[$index] = "CORS_ORIGINS=$encoded"
  } else {
    $lines += "CORS_ORIGINS=$encoded"
  }
  Set-Content -LiteralPath $Path -Value $lines
}

$cleanArgs = @{
  CoreDb = $true
  FlutterBuild = $true
  Logs = $true
  StopStack = $true
}
if (-not $KeepSearchIndex) {
  $cleanArgs["SearchIndex"] = $true
}
if (-not $KeepImages) {
  $cleanArgs["Images"] = $true
}
if (-not $KeepSyncData) {
  $cleanArgs["Sync"] = $true
}
if ($Force) {
  $cleanArgs["Force"] = $true
}
if ($script:UseWslDockerResolved) {
  $cleanArgs["UseWslDocker"] = $true
}

& (Join-Path $PSScriptRoot "dev-clean-state.ps1") @cleanArgs
Update-CorsOrigins -Path $envPath -Origins @($webOriginLocalhost, $webOriginLoopback)

Invoke-Compose @("up", "--build", "-d", "postgres", "redis", "meilisearch", "minio", "api", "sync")

Wait-Endpoint "$ApiBaseUrl/health"
Wait-Endpoint "$SyncBaseUrl/health"

Invoke-Compose @("exec", "-T", "api", "alembic", "upgrade", "head")
if (-not $SkipSeed) {
  Invoke-Compose @("exec", "-T", "api", "python", "-m", "app.scripts.seed_comics")
}
Invoke-Compose @("up", "--build", "-d", "worker")

$webArgs = @{
  WebPort = $WebPort
  ApiBaseUrl = $ApiBaseUrl
  SyncBaseUrl = $SyncBaseUrl
  SyncKey = $SyncKey
  SkipDocker = $true
  SkipMigrate = $true
  SkipSeed = $true
}
if ($SkipFlutterBuild) {
  $webArgs["SkipBuild"] = $true
}

& (Join-Path $PSScriptRoot "dev-smoke-web.ps1") @webArgs

if (-not $SkipProviderSmoke) {
  $providerArgs = @{
    ApiBaseUrl = $ApiBaseUrl
    SyncBaseUrl = $SyncBaseUrl
    SyncKey = $SyncKey
  }
  if ($SkipIngestFlow) {
    $providerArgs["SkipIngestFlow"] = $true
  }
  if ($script:UseWslDockerResolved) {
    $providerArgs["UseWslDocker"] = $true
  }
  & (Join-Path $PSScriptRoot "dev-smoke-providers.ps1") @providerArgs
}

Write-Host ""
Write-Host "Collectarr pipeline reset complete." -ForegroundColor Green
Write-Host "Flutter web: http://127.0.0.1:$WebPort" -ForegroundColor Cyan
Write-Host "Core API:    $ApiBaseUrl"
Write-Host "Sync:        $SyncBaseUrl"
