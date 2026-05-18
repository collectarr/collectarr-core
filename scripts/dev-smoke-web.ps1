param(
  [int]$WebPort = 8083,
  [string]$ApiBaseUrl = "http://localhost:8010",
  [string]$SyncBaseUrl = "http://localhost:8020",
  [string]$SyncKey = "collectarr-sync-dev-key",
  [switch]$SkipDocker,
  [switch]$SkipMigrate,
  [switch]$SkipSeed,
  [switch]$SkipBuild,
  [switch]$SkipSmoke,
  [switch]$UseWslDocker
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"
$envExamplePath = Join-Path $repoRoot ".env.example"
$buildDir = Join-Path $repoRoot "frontend\build\web"
$logDir = Join-Path $repoRoot ".dev\logs"
$webOriginLocalhost = "http://localhost:$WebPort"
$webOriginLoopback = "http://127.0.0.1:$WebPort"

. (Join-Path $PSScriptRoot "lib-dev.ps1")
Set-Location $repoRoot

if (-not (Test-Path $envPath)) {
  Copy-Item $envExamplePath $envPath
}

Initialize-CollectarrDocker -UseWslDocker:$UseWslDocker

function Invoke-Compose {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  Invoke-ComposeChecked -PrefixArguments @("--profile", "sync") -Arguments $Arguments
}

function Test-Endpoint {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url
  )

  try {
    Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 12 | Out-Null
    Write-Host "OK  $Url" -ForegroundColor Green
  } catch {
    Write-Host "WARN $Url is not reachable yet: $($_.Exception.Message)" -ForegroundColor Yellow
  }
}

Update-CorsOrigins -Path $envPath -Origins @($webOriginLocalhost, $webOriginLoopback)

if (-not $SkipDocker) {
  Invoke-Compose @("up", "--build", "-d", "postgres", "redis", "meilisearch", "minio", "api", "sync")
  if (-not $SkipMigrate) {
    Invoke-Compose @("exec", "-T", "api", "alembic", "upgrade", "head")
  }
  if (-not $SkipSeed) {
    Invoke-Compose @("exec", "-T", "api", "python", "-m", "app.scripts.seed_comics")
  }
  Invoke-Compose @("up", "--build", "-d", "worker")
}

if (-not $SkipBuild) {
  Push-Location (Join-Path $repoRoot "frontend")
  try {
    flutter build web `
      --dart-define=COLLECTARR_API_BASE_URL=$ApiBaseUrl `
      --dart-define=COLLECTARR_SYNC_BASE_URL=$SyncBaseUrl `
      --dart-define=COLLECTARR_SYNC_KEY=$SyncKey
  } finally {
    Pop-Location
  }
}

if (-not (Test-Path (Join-Path $buildDir "index.html"))) {
  throw "Flutter web build not found at $buildDir. Run without -SkipBuild first."
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$existingListener = Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue |
  Select-Object -First 1
if ($existingListener) {
  $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($existingListener.OwningProcess)"
  $commandLine = $process.CommandLine
  if ($commandLine -and $commandLine.Contains("http.server") -and $commandLine.Contains($buildDir)) {
    Write-Host "Flutter web is already served on $webOriginLoopback" -ForegroundColor Green
  } else {
    Write-Host "Port $WebPort is already in use by PID $($existingListener.OwningProcess). Reusing it." -ForegroundColor Yellow
  }
} else {
  $python = (Get-Command python -ErrorAction Stop).Source
  $outLog = Join-Path $logDir "flutter-web-$WebPort.out.log"
  $errLog = Join-Path $logDir "flutter-web-$WebPort.err.log"
  $process = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "http.server", $WebPort.ToString(), "--bind", "127.0.0.1", "--directory", $buildDir) `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru
  Write-Host "Started Flutter web static server PID $($process.Id)" -ForegroundColor Green
}

if (-not $SkipSmoke) {
  Test-Endpoint "$ApiBaseUrl/health"
  Test-Endpoint "$ApiBaseUrl/metadata/media-types"
  Test-Endpoint "$SyncBaseUrl/health"
  Test-Endpoint $webOriginLoopback
}

Write-Host ""
Write-Host "Flutter web: $webOriginLoopback" -ForegroundColor Cyan
Write-Host "Core API:    $ApiBaseUrl"
Write-Host "Sync:        $SyncBaseUrl"
