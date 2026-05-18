param(
  [switch]$All,
  [switch]$CoreDb,
  [switch]$SearchIndex,
  [switch]$Images,
  [switch]$Sync,
  [switch]$FlutterBuild,
  [switch]$Logs,
  [switch]$StopStack,
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

if ($All) {
  $CoreDb = $true
  $SearchIndex = $true
  $Images = $true
  $Sync = $true
  $FlutterBuild = $true
  $Logs = $true
  $StopStack = $true
}

if (-not ($CoreDb -or $SearchIndex -or $Images -or $Sync -or $FlutterBuild -or $Logs)) {
  Write-Host "Nothing selected. Use -CoreDb, -SearchIndex, -Images, -Sync, -FlutterBuild, -Logs, or -All." -ForegroundColor Yellow
  exit 0
}

function Get-AbsolutePath {
  param([Parameter(Mandatory = $true)][string]$Path)
  return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
}

function Assert-WithinRepo {
  param([Parameter(Mandatory = $true)][string]$Path)
  $absolute = Get-AbsolutePath $Path
  $root = [System.IO.Path]::GetFullPath($repoRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
  if (-not $absolute.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to delete outside repository: $absolute"
  }
  return $absolute
}

function Remove-DirectoryIfPresent {
  param([Parameter(Mandatory = $true)][string]$Path)
  $absolute = Assert-WithinRepo $Path
  if (Test-Path -LiteralPath $absolute) {
    Write-Host "Removing $absolute" -ForegroundColor Yellow
    $lastError = $null
    for ($attempt = 1; $attempt -le 8; $attempt++) {
      try {
        Remove-Item -LiteralPath $absolute -Recurse -Force
        return
      } catch {
        $lastError = $_
        Start-Sleep -Milliseconds (250 * $attempt)
      }
    }
    throw $lastError
  }
}

function Stop-RepoWebServers {
  $buildPath = Assert-WithinRepo "frontend\build\web"
  $buildPathAlt = $buildPath.Replace("\", "/")
  $relativePath = "frontend\build\web"
  $relativePathAlt = "frontend/build/web"
  $legacyPorts = 8081..8085 | ForEach-Object { "http.server $_" }
  $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $commandLine = $_.CommandLine
      $commandLine -and
      $commandLine.Contains("http.server") -and
      (
        $commandLine.Contains($buildPath) -or
        $commandLine.Contains($buildPathAlt) -or
        $commandLine.Contains($relativePath) -or
        $commandLine.Contains($relativePathAlt) -or
        ($legacyPorts | Where-Object { $commandLine.Contains($_) })
      )
    }
  foreach ($process in $processes) {
    Write-Host "Stopping Flutter web static server PID $($process.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
  }
}

$selected = @()
if ($CoreDb) { $selected += "Postgres volume" }
if ($SearchIndex) { $selected += "Meilisearch volume" }
if ($Images) { $selected += "MinIO image volume" }
if ($Sync) { $selected += "Sync SQLite volume" }
if ($FlutterBuild) { $selected += "Flutter web build" }
if ($Logs) { $selected += ".dev logs" }

if (-not $Force) {
  Write-Host "This will clean: $($selected -join ', ')." -ForegroundColor Yellow
  $answer = Read-Host "Type CLEAN to continue"
  if ($answer -ne "CLEAN") {
    Write-Host "Cancelled."
    exit 0
  }
}

if ($StopStack -or $CoreDb -or $SearchIndex -or $Images -or $Sync) {
  Invoke-Docker @("compose", "--profile", "sync", "down")
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose down failed with exit code $LASTEXITCODE"
  }
}

$volumes = @()
if ($CoreDb) { $volumes += "collectarr_postgres_data" }
if ($SearchIndex) { $volumes += "collectarr_meili_data" }
if ($Images) { $volumes += "collectarr_minio_data" }
if ($Sync) { $volumes += "collectarr_sync_data" }

foreach ($volume in $volumes) {
  $existing = Invoke-DockerText @("volume", "ls", "--quiet", "--filter", "name=^$volume$")
  if ($existing) {
    Write-Host "Removing Docker volume $volume" -ForegroundColor Yellow
    Invoke-Docker @("volume", "rm", $volume) | Out-Host
    if ($LASTEXITCODE -ne 0) {
      throw "docker volume rm $volume failed with exit code $LASTEXITCODE"
    }
  }
}

if ($FlutterBuild) {
  Stop-RepoWebServers
  Remove-DirectoryIfPresent "frontend\build\web"
}

if ($Logs) {
  Remove-DirectoryIfPresent ".dev\logs"
}

Write-Host "Collectarr local state cleanup complete." -ForegroundColor Green
