param(
  [string]$ApiBaseUrl = "http://localhost:8010",
  [string]$SyncBaseUrl = "http://localhost:8020",
  [string]$SyncKey = "collectarr-sync-dev-key",
  [string]$AdminEmail = "",
  [string]$AdminPassword = "password123",
  [switch]$SkipProviderSearch,
  [switch]$SkipIngestFlow,
  [switch]$SkipSyncSmoke,
  [switch]$SkipAdminPromote,
  [switch]$UseWslDocker,
  [string]$ReportPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

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

function Read-DotEnv {
  param([Parameter(Mandatory = $true)][string]$Path)
  $values = @{}
  if (-not (Test-Path -LiteralPath $Path)) {
    return $values
  }
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
      continue
    }
    $parts = $trimmed.Split("=", 2)
    $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
  }
  return $values
}

function Get-HttpStatusCode {
  param([Parameter(Mandatory = $true)]$ErrorRecord)
  $response = $ErrorRecord.Exception.Response
  if ($null -eq $response) {
    return $null
  }
  if ($response.StatusCode -is [int]) {
    return [int]$response.StatusCode
  }
  return [int]$response.StatusCode.value__
}

function Invoke-Json {
  param(
    [ValidateSet("Get", "Post", "Patch")]
    [string]$Method = "Get",
    [Parameter(Mandatory = $true)]
    [string]$Url,
    $Body = $null,
    [string]$Token = "",
    [hashtable]$Headers = @{}
  )
  $requestHeaders = @{}
  foreach ($key in $Headers.Keys) {
    $requestHeaders[$key] = $Headers[$key]
  }
  if ($Token) {
    $requestHeaders["Authorization"] = "Bearer $Token"
  }
  $parameters = @{
    Uri = $Url
    Method = $Method
    Headers = $requestHeaders
    TimeoutSec = 45
  }
  if ($null -ne $Body) {
    $parameters["Body"] = ($Body | ConvertTo-Json -Depth 20)
    $parameters["ContentType"] = "application/json"
  }
  $response = Invoke-RestMethod @parameters
  return $response
}

function Get-ApiUrl {
  param([Parameter(Mandatory = $true)][string]$Path)
  return "$($ApiBaseUrl.TrimEnd('/'))$Path"
}

function Get-SyncUrl {
  param([Parameter(Mandatory = $true)][string]$Path)
  return "$($SyncBaseUrl.TrimEnd('/'))$Path"
}

function Get-AdminEmailFromEnv {
  param([hashtable]$EnvValues)
  if ($AdminEmail) {
    return $AdminEmail
  }
  $raw = $EnvValues["BOOTSTRAP_ADMIN_EMAILS"]
  if ($raw) {
    try {
      $parsed = $raw | ConvertFrom-Json
      if ($parsed -is [array] -and $parsed.Count -gt 0) {
        return [string]$parsed[0]
      }
      if ($parsed) {
        return [string]$parsed
      }
    } catch {
      $csv = @($raw.Split(",") | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
      if ($csv.Count -gt 0) {
        return $csv[0]
      }
    }
  }
  return "user@example.com"
}

function Get-AuthToken {
  param(
    [Parameter(Mandatory = $true)][string]$Email,
    [Parameter(Mandatory = $true)][string]$Password
  )
  $registerBody = @{
    email = $Email
    password = $Password
    display_name = "Collectarr Dev Admin"
  }
  try {
    $registered = Invoke-Json -Method Post -Url (Get-ApiUrl "/auth/register") -Body $registerBody
    return $registered.access_token
  } catch {
    $statusCode = Get-HttpStatusCode $_
    if ($statusCode -ne 409) {
      throw
    }
  }
  $loginBody = @{ email = $Email; password = $Password }
  $loggedIn = Invoke-Json -Method Post -Url (Get-ApiUrl "/auth/login") -Body $loginBody
  return $loggedIn.access_token
}

function Enable-AdminIfNeeded {
  param([Parameter(Mandatory = $true)][string]$Email)
  if ($SkipAdminPromote) {
    return
  }
  Invoke-Docker @("compose", "exec", "-T", "api", "python", "-m", "app.commands.set_admin", $Email, "true")
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to promote $Email to admin."
  }
}

function Add-SmokeResult {
  param(
    $Results = $null,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Status,
    [string]$Detail = "",
    $Data = $null
  )
  if ($null -eq $Results) {
    $Results = $script:SmokeResults
  }
  $Results.Add([ordered]@{
      name = $Name
      status = $Status
      detail = $Detail
      data = $Data
    }) | Out-Null
  $color = switch ($Status) {
    "pass" { "Green" }
    "skip" { "Yellow" }
    default { "Red" }
  }
  Write-Host ("{0,-5} {1} {2}" -f $Status.ToUpperInvariant(), $Name, $Detail) -ForegroundColor $color
}

$envValues = Read-DotEnv (Join-Path $repoRoot ".env")
$email = Get-AdminEmailFromEnv $envValues
$script:SmokeResults = [System.Collections.Generic.List[object]]::new()
$results = $script:SmokeResults

Invoke-Json -Url (Get-ApiUrl "/health") | Out-Null
Add-SmokeResult -Results $results -Name "Core health" -Status "pass" -Detail $ApiBaseUrl

$token = Get-AuthToken -Email $email -Password $AdminPassword
try {
  Invoke-Json -Url (Get-ApiUrl "/admin/providers") -Token $token | Out-Null
} catch {
  if ((Get-HttpStatusCode $_) -eq 403) {
    Enable-AdminIfNeeded -Email $email
    $token = Get-AuthToken -Email $email -Password $AdminPassword
  } else {
    throw
  }
}

$me = Invoke-Json -Url (Get-ApiUrl "/auth/me") -Token $token
Add-SmokeResult -Results $results -Name "Auth/admin session" -Status "pass" -Detail "$($me.email)"

$mediaTypes = Invoke-Json -Url (Get-ApiUrl "/metadata/media-types")
Add-SmokeResult -Results $results -Name "Media catalog" -Status "pass" -Detail "$($mediaTypes.Count) media types"

$providerStatuses = Invoke-Json -Url (Get-ApiUrl "/admin/providers") -Token $token
$statusByProvider = @{}
foreach ($status in $providerStatuses) {
  $statusByProvider[$status.name] = $status
}
Add-SmokeResult -Results $results -Name "Provider status" -Status "pass" -Detail "$($providerStatuses.Count) providers"

$providerCases = @(
  @{ name = "Comics GCD"; provider = "gcd"; kind = "comic"; query = "Batman 1"; required = $true },
  @{ name = "Comics ComicVine"; provider = "comicvine"; kind = "comic"; query = "Over the Garden Wall #1"; requiresConfigured = $true },
  @{ name = "Manga AniList"; provider = "anilist"; kind = "manga"; query = "Naruto"; required = $true },
  @{ name = "Anime AniList"; provider = "anilist"; kind = "anime"; query = "Cowboy Bebop"; required = $true },
  @{ name = "Books OpenLibrary"; provider = "openlibrary"; kind = "book"; query = "Dune"; required = $true },
  @{ name = "Movies TMDb"; provider = "tmdb"; kind = "movie"; query = "Blade Runner"; requiresConfigured = $true },
  @{ name = "TV TMDb"; provider = "tmdb"; kind = "tv"; query = "Breaking Bad"; requiresConfigured = $true },
  @{ name = "Games IGDB"; provider = "igdb"; kind = "game"; query = "The Legend of Zelda"; requiresConfigured = $true },
  @{ name = "Board Games BGG"; provider = "bgg"; kind = "boardgame"; query = "Catan"; requiresConfigured = $true },
  @{ name = "Music MusicBrainz"; provider = "musicbrainz"; kind = "music"; query = "OK Computer"; required = $true }
)

$firstGcdCandidate = $null
if (-not $SkipProviderSearch) {
  foreach ($case in $providerCases) {
    $providerStatus = $statusByProvider[$case.provider]
    if ($case.requiresConfigured -and $providerStatus -and -not $providerStatus.is_configured) {
      Add-SmokeResult -Results $results -Name $case.name -Status "skip" -Detail "provider not configured"
      continue
    }
    $query = [System.Uri]::EscapeDataString($case.query)
    $kind = [System.Uri]::EscapeDataString($case.kind)
    $url = Get-ApiUrl "/metadata/providers/$($case.provider)/search?q=$query&kind=$kind"
    try {
      $rows = @(Invoke-Json -Url $url -Token $token)
      if ($rows.Count -eq 0) {
        $status = if ($case.required) { "fail" } else { "skip" }
        Add-SmokeResult -Results $results -Name $case.name -Status $status -Detail "0 results"
        continue
      }
      $first = $rows[0]
      if ($case.provider -eq "gcd" -and $null -eq $firstGcdCandidate) {
        $firstGcdCandidate = $first
      }
      $stub = if ($first.provider_item_id -like "stub-*") { " stub" } else { "" }
      Add-SmokeResult -Results $results -Name $case.name -Status "pass" -Detail "$($rows.Count) results$stub; first=$($first.title)"
    } catch {
      $status = if ($case.required) { "fail" } else { "skip" }
      Add-SmokeResult -Results $results -Name $case.name -Status $status -Detail $_.Exception.Message
    }
  }
}

if (-not $SkipIngestFlow) {
  if ($null -eq $firstGcdCandidate) {
    Add-SmokeResult -Results $results -Name "Provider candidate -> ingest flow" -Status "skip" -Detail "no GCD candidate"
  } else {
    $proposal = Invoke-Json -Method Post -Url (Get-ApiUrl "/metadata/proposals") -Token $token -Body @{
      provider = $firstGcdCandidate.provider
      provider_item_id = $firstGcdCandidate.provider_item_id
      query = "Batman 1"
      title = $firstGcdCandidate.title
      summary = $firstGcdCandidate.summary
      image_url = $firstGcdCandidate.image_url
    }
    Add-SmokeResult -Results $results -Name "Metadata proposal" -Status "pass" -Detail "$($proposal.id)"

    $job = Invoke-Json -Method Post -Url (Get-ApiUrl "/admin/providers/ingest/jobs") -Token $token -Body @{
      provider = $firstGcdCandidate.provider
      provider_item_id = $firstGcdCandidate.provider_item_id
      max_attempts = 2
    }
    Add-SmokeResult -Results $results -Name "Provider ingest job queued" -Status "pass" -Detail "$($job.id)"

    $run = Invoke-Json -Method Post -Url (Get-ApiUrl "/admin/providers/ingest/jobs/run-pending?limit=3") -Token $token
    $runJobs = @($run.jobs)
    $done = @($runJobs | Where-Object { $_.status -eq "done" })
    if ($done.Count -gt 0) {
      Add-SmokeResult -Results $results -Name "Provider ingest job run" -Status "pass" -Detail "$($done[0].item_id)"
      Start-Sleep -Seconds 2
      $searchQuery = [System.Uri]::EscapeDataString($firstGcdCandidate.title)
      $searchRows = @(Invoke-Json -Url (Get-ApiUrl "/search?q=$searchQuery&kind=comic&limit=5"))
      if ($searchRows.Count -gt 0) {
        Add-SmokeResult -Results $results -Name "Core search after ingest" -Status "pass" -Detail "$($searchRows[0].title)"
      } else {
        Add-SmokeResult -Results $results -Name "Core search after ingest" -Status "fail" -Detail "no indexed/catalog result"
      }
    } else {
      $failed = @($runJobs | Where-Object { $_.status -eq "failed" })
      $detail = if ($failed.Count -gt 0) { $failed[0].last_error } else { "processed=$($run.processed)" }
      Add-SmokeResult -Results $results -Name "Provider ingest job run" -Status "fail" -Detail $detail
    }
  }
}

if (-not $SkipSyncSmoke) {
  $headers = @{ "X-Collectarr-Sync-Key" = $SyncKey }
  Invoke-Json -Url (Get-SyncUrl "/health") | Out-Null
  $changedAt = (Get-Date).ToUniversalTime().ToString("o")
  $entityId = "smoke-snapshot-$([guid]::NewGuid().ToString('N'))"
  $push = Invoke-Json -Method Post -Url (Get-SyncUrl "/sync/push") -Headers $headers -Body @{
    device_id = "dev-smoke"
    changes = @(
      @{
        entity_type = "library_item_snapshot"
        entity_id = $entityId
        action = "upsert"
        client_changed_at = $changedAt
        payload = @{
          snapshot_version = 1
          kind = "movie"
          title = "Smoke Physical Edition"
          edition_title = "4K test"
          physical_format = "4k-uhd"
          physical_format_label = "4K UHD"
          barcode = "883929087129"
          variant = "4K UHD"
        }
      }
    )
  }
  if (@($push.accepted).Count -ne 1) {
    Add-SmokeResult -Results $results -Name "Sync push snapshot" -Status "fail" -Detail "accepted=$(@($push.accepted).Count)"
  } else {
    Add-SmokeResult -Results $results -Name "Sync push snapshot" -Status "pass" -Detail $entityId
  }
  $pull = Invoke-Json -Method Post -Url (Get-SyncUrl "/sync/pull") -Headers $headers -Body @{}
  $match = @($pull.entities | Where-Object { $_.entity_id -eq $entityId })
  if ($match.Count -eq 1) {
    Add-SmokeResult -Results $results -Name "Sync pull snapshot" -Status "pass" -Detail $match[0].payload.physical_format_label
  } else {
    Add-SmokeResult -Results $results -Name "Sync pull snapshot" -Status "fail" -Detail "snapshot not returned"
  }
}

$failed = @($results | Where-Object { $_.status -eq "fail" })
$report = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  api_base_url = $ApiBaseUrl
  sync_base_url = $SyncBaseUrl
  results = $results
}

if (-not $ReportPath) {
  $reportDir = Join-Path $repoRoot ".dev\reports"
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  $ReportPath = Join-Path $reportDir "provider-smoke.json"
}

$report | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $ReportPath
Write-Host "Smoke report: $ReportPath" -ForegroundColor Cyan

if ($failed.Count -gt 0) {
  throw "$($failed.Count) smoke checks failed."
}
