param(
  [string]$Version = "1.2.0-beta.1",
  [string]$OutputRoot = "",
  [switch]$SkipBackend,
  [switch]$SkipFlutter,
  [switch]$NoZip,
  [switch]$NoSmoke
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Script
  )
  Write-Host ""
  Write-Host "==> $Name" -ForegroundColor Cyan
  & $Script
}

function Assert-LastExitCode {
  param([string]$Message)
  if ($LASTEXITCODE -ne 0) {
    throw "$Message (exit code $LASTEXITCODE)"
  }
}

function Invoke-WithRefCheckerSecretEnvironmentCleared {
  param([scriptblock]$Script)
  $names = @(
    "REFCHECKER_SPRINGER_API_KEY",
    "REFCHECKER_IEEE_API_KEY",
    "REFCHECKER_CORE_API_KEY"
  )
  $oldValues = @{}
  foreach ($name in $names) {
    $oldValues[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    Set-Item -Path "Env:$name" -Value ""
  }
  try {
    & $Script
  } finally {
    foreach ($name in $names) {
      if ($null -eq $oldValues[$name]) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
      } else {
        Set-Item -Path "Env:$name" -Value $oldValues[$name]
      }
    }
  }
}

function Assert-NoPackagedSecrets {
  param([string]$PackagePath)

  $forbiddenNames = @(
    "settings.json",
    "custom_rest_profiles.json",
    ".env",
    "run.log"
  )
  $forbiddenExtensions = @(".pem", ".pfx", ".p12", ".key", ".crt")
  $allFiles = Get-ChildItem -LiteralPath $PackagePath -Recurse -Force -File
  $badFiles = @()
  foreach ($file in $allFiles) {
    $lowerName = $file.Name.ToLowerInvariant()
    $lowerExt = $file.Extension.ToLowerInvariant()
    if ($forbiddenNames -contains $lowerName -or $forbiddenExtensions -contains $lowerExt) {
      $badFiles += $file.FullName
      continue
    }
    if ($lowerName -match '(api[-_]?key|secret|token|credential|password).*\.(json|txt|env|ini|toml|ya?ml)$') {
      $badFiles += $file.FullName
    }
  }
  if ($badFiles.Count -gt 0) {
    throw "Potential secret/config files were included in package:`n$($badFiles -join [Environment]::NewLine)"
  }

  $textExtensions = @(".json", ".txt", ".md", ".ini", ".toml", ".yaml", ".yml", ".env", ".config", ".ps1", ".bat", ".cmd")
  $textFiles = $allFiles | Where-Object { $textExtensions -contains $_.Extension.ToLowerInvariant() }
  $secretPatterns = @(
    '(?i)"(apiKey|springerApiKey|ieeeApiKey|coreApiKey)"\s*:\s*"(?!\s*")([^"]{8,})"',
    '(?i)(REFCHECKER_(SPRINGER|IEEE|CORE)_API_KEY)\s*=',
    '(?i)(sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,})'
  )
  foreach ($pattern in $secretPatterns) {
    $matches = Select-String -Path ($textFiles | ForEach-Object { $_.FullName }) -Pattern $pattern -ErrorAction SilentlyContinue
    if ($matches) {
      $locations = $matches | ForEach-Object { "$($_.Path):$($_.LineNumber)" }
      throw "Potential secret text was detected in package:`n$($locations -join [Environment]::NewLine)"
    }
  }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
Set-Location $root

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
  $OutputRoot = Join-Path $root "dist_portable"
}
$OutputRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$safeVersion = $Version -replace '[^A-Za-z0-9._-]', '_'
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageDir = Join-Path $OutputRoot "RefChecker_portable_v${safeVersion}_$stamp"
$zipPath = "$packageDir.zip"

$venvPython = Join-Path $root ".venv_build\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$backendExe = Join-Path $root "backend\refchecker_backend.exe"
$httpServerExe = Join-Path $root "backend\refchecker_http_server.exe"
$releaseDir = Join-Path $root "build\windows\x64\runner\Release"

Write-Host "RefChecker Windows packaging"
Write-Host "Root       : $root"
Write-Host "Version    : $Version"
Write-Host "Python     : $python"
Write-Host "Output root: $OutputRoot"

if (-not $SkipBackend) {
  Invoke-Step "Install backend dependencies" {
    & $python -m pip install -r requirements.txt
    Assert-LastExitCode "pip install failed"
  }

  Invoke-Step "Build Python backend" {
    & $python -m PyInstaller --clean --onefile --name refchecker_backend check_bib_crossref.py
    Assert-LastExitCode "PyInstaller build failed"
    & $python -m PyInstaller --clean --onefile --name refchecker_http_server refchecker_http_server.py
    Assert-LastExitCode "PyInstaller HTTP server build failed"
    New-Item -ItemType Directory -Force -Path (Join-Path $root "backend") | Out-Null
    Copy-Item -Force -LiteralPath (Join-Path $root "dist\refchecker_backend.exe") -Destination $backendExe
    Copy-Item -Force -LiteralPath (Join-Path $root "dist\refchecker_http_server.exe") -Destination $httpServerExe
  }
} else {
  Write-Host "Skipping backend build"
}

if (-not (Test-Path -LiteralPath $backendExe)) {
  throw "Missing backend executable: $backendExe"
}
if (-not (Test-Path -LiteralPath $httpServerExe)) {
  throw "Missing HTTP server executable: $httpServerExe"
}

if (-not $SkipFlutter) {
  Invoke-Step "Build Flutter Windows release" {
    flutter build windows --release --dart-define "APP_VERSION=$Version"
    Assert-LastExitCode "Flutter Windows build failed"
  }
} else {
  Write-Host "Skipping Flutter build"
}

if (-not (Test-Path -LiteralPath (Join-Path $releaseDir "refchecker_desktop.exe"))) {
  throw "Missing Flutter release executable: $releaseDir\refchecker_desktop.exe"
}

Invoke-Step "Assemble portable directory" {
  New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
  Copy-Item -LiteralPath (Join-Path $releaseDir "refchecker_desktop.exe") -Destination $packageDir -Force
  Copy-Item -LiteralPath (Join-Path $releaseDir "flutter_windows.dll") -Destination $packageDir -Force
  if (Test-Path -LiteralPath (Join-Path $releaseDir "native_assets.json")) {
    Copy-Item -LiteralPath (Join-Path $releaseDir "native_assets.json") -Destination $packageDir -Force
  }
  Copy-Item -LiteralPath (Join-Path $releaseDir "data") -Destination $packageDir -Recurse -Force
  New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "backend") | Out-Null
  Copy-Item -LiteralPath $backendExe -Destination (Join-Path $packageDir "backend\refchecker_backend.exe") -Force
  Copy-Item -LiteralPath $httpServerExe -Destination (Join-Path $packageDir "backend\refchecker_http_server.exe") -Force
  if (Test-Path -LiteralPath (Join-Path $root "browser_extension\refchecker_claude")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "browser_extension") | Out-Null
    Copy-Item -LiteralPath (Join-Path $root "browser_extension\refchecker_claude") -Destination (Join-Path $packageDir "browser_extension") -Recurse -Force
  }
  foreach ($docName in @("README.md", "CHANGELOG.md", "BROWSER_EXTENSION_CLAUDE_WEB.md", "MCP_CLAUDE_DESKTOP.md", "RELEASE_NOTES_v1.2.0-beta.1.md")) {
    $docPath = Join-Path $root $docName
    if (Test-Path -LiteralPath $docPath) {
      Copy-Item -LiteralPath $docPath -Destination (Join-Path $packageDir $docName) -Force
    }
  }

  $manifest = @(
    "RefChecker portable package",
    "Version: $Version",
    "BuiltAt: $(Get-Date -Format o)",
    "Frontend: refchecker_desktop.exe",
    "Backend: backend/refchecker_backend.exe",
    "Browser extension HTTP bridge: backend/refchecker_http_server.exe",
    "Claude web browser extension: browser_extension/refchecker_claude",
    "",
    "Privacy: local settings and API keys are not copied into this package."
  ) -join [Environment]::NewLine
  Set-Content -LiteralPath (Join-Path $packageDir "PACKAGE_MANIFEST.txt") -Encoding UTF8 -Value $manifest

  $privacy = @(
    "RefChecker package privacy note",
    "",
    "- This portable package does not include local settings.json.",
    "- This portable package does not include API keys, .env files, custom_rest_profiles.json, run logs, or generated reports.",
    "- User settings are loaded at runtime from the current user's AppData folder, not from this package.",
    "- During packaging smoke tests, RefChecker API key environment variables are cleared for the child backend process."
  ) -join [Environment]::NewLine
  Set-Content -LiteralPath (Join-Path $packageDir "PACKAGE_PRIVACY.txt") -Encoding UTF8 -Value $privacy
}

Invoke-Step "Secret guard" {
  Assert-NoPackagedSecrets -PackagePath $packageDir
}

if (-not $NoSmoke) {
  Invoke-Step "Smoke test packaged backend" {
    $smokeDir = Join-Path ([System.IO.Path]::GetTempPath()) "refchecker_package_smoke_$stamp"
    New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
    $bib = Join-Path $smokeDir "smoke_missing_title.bib"
    Set-Content -LiteralPath $bib -Encoding UTF8 -Value "@article{missing, author={Doe, Jane}, year={2024}}"
    $outDir = Join-Path $smokeDir "out"
    Invoke-WithRefCheckerSecretEnvironmentCleared {
      & (Join-Path $packageDir "backend\refchecker_backend.exe") $bib --jsonl-progress --output-dir $outDir --delay 0 --app-version $Version --no-springer --no-ieee --no-core
      Assert-LastExitCode "Packaged backend smoke test failed"
    }
    foreach ($name in @("report.md", "result.csv", "citation_consistency.json")) {
      $path = Join-Path $outDir $name
      if (-not (Test-Path -LiteralPath $path)) {
        throw "Smoke test did not create $name"
      }
    }
  }

  Invoke-Step "Smoke test packaged HTTP bridge" {
    $port = 18765
    $httpExe = Join-Path $packageDir "backend\refchecker_http_server.exe"
    $httpProcess = Start-Process -FilePath $httpExe -ArgumentList @("--host", "127.0.0.1", "--port", "$port") -PassThru -WindowStyle Hidden
    try {
      $ok = $false
      for ($i = 0; $i -lt 20; $i++) {
        try {
          $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1
          if ($health.ok -eq $true) {
            $ok = $true
            break
          }
        } catch {
          Start-Sleep -Milliseconds 300
        }
      }
      if (-not $ok) {
        throw "Packaged HTTP bridge did not respond on /health"
      }
    } finally {
      if ($httpProcess -and -not $httpProcess.HasExited) {
        Stop-Process -Id $httpProcess.Id -Force
      }
    }
  }
}

if (-not $NoZip) {
  Invoke-Step "Create zip" {
    if (Test-Path -LiteralPath $zipPath) {
      Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force
  }
}

Write-Host ""
Write-Host "Package directory: $packageDir" -ForegroundColor Green
if (-not $NoZip) {
  Write-Host "Zip package      : $zipPath" -ForegroundColor Green
}
