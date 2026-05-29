function Initialize-CollectarrDocker {
  param([switch]$UseWslDocker)

  $script:CollectarrUseWslDockerResolved = $UseWslDocker.IsPresent
  if (-not $script:CollectarrUseWslDockerResolved) {
    & docker version --format "{{.Server.Version}}" *> $null
    if ($LASTEXITCODE -ne 0) {
      & wsl docker version --format "{{.Server.Version}}" *> $null
      if ($LASTEXITCODE -eq 0) {
        $script:CollectarrUseWslDockerResolved = $true
        Write-Host "Using WSL Docker Engine." -ForegroundColor Cyan
      }
    }
  }
}

function Test-CollectarrWslDocker {
  return [bool]$script:CollectarrUseWslDockerResolved
}

function Invoke-Docker {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  if ($script:CollectarrUseWslDockerResolved) {
    & wsl docker @Arguments
  } else {
    & docker @Arguments
  }
}

function Invoke-DockerText {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  if ($script:CollectarrUseWslDockerResolved) {
    return (& wsl docker @Arguments)
  }
  return (& docker @Arguments)
}

function Invoke-ComposeChecked {
  param(
    [string[]]$PrefixArguments = @(),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  $composeArgs = @("compose") + $PrefixArguments + $Arguments
  Invoke-Docker @composeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
  }
}

function Test-CollectarrHasAlembicVersions {
  param([Parameter(Mandatory = $true)][string]$RepoRoot)

  $versionsPath = Join-Path $RepoRoot "alembic\versions"
  if (-not (Test-Path -LiteralPath $versionsPath)) {
    return $false
  }

  $versionFiles = Get-ChildItem -LiteralPath $versionsPath -Filter "*.py" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "__init__.py" }
  return [bool]($versionFiles | Select-Object -First 1)
}

function Invoke-CollectarrSchemaSetup {
  param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [switch]$WithSync
  )

  $prefixArguments = @()
  if ($WithSync) {
    $prefixArguments = @("-f", "docker-compose.yml", "-f", "docker-compose.devstack.yml")
  }

  if (Test-CollectarrHasAlembicVersions -RepoRoot $RepoRoot) {
    Invoke-ComposeChecked -PrefixArguments $prefixArguments -Arguments @("run", "--rm", "api", "python", "-m", "app.scripts.bootstrap_alembic")
    return
  }

  Write-Host "No Alembic versions found; bootstrapping schema from SQLAlchemy metadata instead." -ForegroundColor Yellow
  $bootstrapSchemaScript = @'
import asyncio

from app.db.session import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


asyncio.run(main())
'@

  $composeArgs = @("compose") + $prefixArguments + @("run", "--rm", "-T", "api", "python", "-")
  if ($script:CollectarrUseWslDockerResolved) {
    $bootstrapSchemaScript | & wsl docker @composeArgs
  } else {
    $bootstrapSchemaScript | & docker @composeArgs
  }
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose run --rm -T api python - failed with exit code $LASTEXITCODE"
  }
}

function Read-DotEnv {
  param([Parameter(Mandatory = $true)][string]$Path)

  $values = @{}
  if (-not (Test-Path -LiteralPath $Path)) {
    return $values
  }
  foreach ($line in Get-Content -LiteralPath $Path) {
    if ($line -notmatch '^\s*([^#=\s][^=]*?)\s*=\s*(.*)\s*$') {
      continue
    }
    $key = $Matches[1].Trim()
    $value = $Matches[2].Trim().Trim('"').Trim("'")
    if ($key) {
      $values[$key] = $value
    }
  }
  return $values
}

function ConvertTo-JsonArrayLiteral {
  param([string[]]$Values)

  $encodedItems = foreach ($value in $Values) {
    ConvertTo-Json -InputObject ([string]$value) -Compress
  }
  return "[$($encodedItems -join ',')]"
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
  $raw = ""
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*CORS_ORIGINS\s*=\s*(.*)\s*$') {
      $index = $i
      $raw = $Matches[1].Trim()
      break
    }
  }

  $current = @()
  if ($index -ge 0 -and $raw) {
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
  $encoded = ConvertTo-JsonArrayLiteral -Values $next.ToArray()

  if ($index -ge 0) {
    $lines[$index] = "CORS_ORIGINS=$encoded"
  } else {
    $lines += "CORS_ORIGINS=$encoded"
  }
  Set-Content -LiteralPath $Path -Value $lines
}
