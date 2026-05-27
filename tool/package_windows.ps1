param(
  [string]$Version = "",
  [switch]$ExactVersion,
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

function Get-DefaultBaseVersion {
  param([string]$RootPath)

  $versionFile = Join-Path $RootPath "refchecker\version.py"
  if (Test-Path -LiteralPath $versionFile) {
    $match = Select-String -LiteralPath $versionFile -Pattern 'DEFAULT_APP_VERSION\s*=\s*"([^"]+)"' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($match -and $match.Matches.Count -gt 0) {
      return $match.Matches[0].Groups[1].Value
    }
    $match = Select-String -LiteralPath $versionFile -Pattern 'APP_VERSION\s*=\s*"([^"]+)"' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($match -and $match.Matches.Count -gt 0) {
      return $match.Matches[0].Groups[1].Value
    }
  }

  $pubspec = Join-Path $RootPath "pubspec.yaml"
  if (Test-Path -LiteralPath $pubspec) {
    $match = Select-String -LiteralPath $pubspec -Pattern '^version:\s*(\S+)' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($match -and $match.Matches.Count -gt 0) {
      return $match.Matches[0].Groups[1].Value
    }
  }

  return "0.0.0"
}

function Get-ChromeExtensionVersion {
  param(
    [string]$BaseVersion,
    [int]$BuildNumber
  )

  if ($BuildNumber -lt 0 -or $BuildNumber -gt 65535) {
    throw "Chrome extension build number must be between 0 and 65535, got $BuildNumber"
  }
  $match = [regex]::Match($BaseVersion, '^(\d+)\.(\d+)\.(\d+)')
  if (-not $match.Success) {
    return "0.0.0.$BuildNumber"
  }
  return "$($match.Groups[1].Value).$($match.Groups[2].Value).$($match.Groups[3].Value).$BuildNumber"
}

function Get-BuildStatePath {
  param([string]$RootPath)
  return Join-Path $RootPath ".refchecker_build_state.json"
}

function Read-BuildCounters {
  param([string]$RootPath)

  $statePath = Get-BuildStatePath -RootPath $RootPath
  $counters = @{}
  if (-not (Test-Path -LiteralPath $statePath)) {
    return $counters
  }

  try {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    if ($state.counters) {
      foreach ($property in $state.counters.PSObject.Properties) {
        $counters[$property.Name] = [int]$property.Value
      }
    }
  } catch {
    Write-Warning "Cannot read $statePath; version counter will be inferred from existing packages."
  }
  return $counters
}

function Get-MaxExistingBuildNumber {
  param(
    [string]$OutputRoot,
    [string]$BaseVersion
  )

  $safeBase = $BaseVersion -replace '[^A-Za-z0-9._-]', '_'
  $pattern = '^RefChecker_portable_v' + [regex]::Escape($safeBase) + '\.(\d+)(?:\.zip)?$'
  $max = -1
  if (-not (Test-Path -LiteralPath $OutputRoot)) {
    return $max
  }

  foreach ($item in Get-ChildItem -LiteralPath $OutputRoot -Force) {
    $match = [regex]::Match($item.Name, $pattern)
    if ($match.Success) {
      $value = [int]$match.Groups[1].Value
      if ($value -gt $max) {
        $max = $value
      }
    }
  }
  return $max
}

function Get-NextPackageVersion {
  param(
    [string]$RootPath,
    [string]$OutputRoot,
    [string]$BaseVersion
  )

  $counters = Read-BuildCounters -RootPath $RootPath
  $stateMax = if ($counters.ContainsKey($BaseVersion)) { [int]$counters[$BaseVersion] } else { -1 }
  $packageMax = Get-MaxExistingBuildNumber -OutputRoot $OutputRoot -BaseVersion $BaseVersion
  $buildNumber = [Math]::Max($stateMax, $packageMax) + 1

  while ($true) {
    $candidateVersion = "$BaseVersion.$buildNumber"
    $safeCandidate = $candidateVersion -replace '[^A-Za-z0-9._-]', '_'
    $candidateDir = Join-Path $OutputRoot "RefChecker_portable_v${safeCandidate}"
    $candidateZip = "$candidateDir.zip"
    if (-not (Test-Path -LiteralPath $candidateDir) -and -not (Test-Path -LiteralPath $candidateZip)) {
      return [pscustomobject]@{
        Version = $candidateVersion
        BuildNumber = $buildNumber
      }
    }
    $buildNumber += 1
  }
}

function Save-BuildCounter {
  param(
    [string]$RootPath,
    [string]$BaseVersion,
    [int]$BuildNumber,
    [string]$PackageVersion
  )

  $statePath = Get-BuildStatePath -RootPath $RootPath
  $counters = Read-BuildCounters -RootPath $RootPath
  $counters[$BaseVersion] = $BuildNumber

  $orderedCounters = [ordered]@{}
  foreach ($key in ($counters.Keys | Sort-Object)) {
    $orderedCounters[$key] = $counters[$key]
  }

  $state = [ordered]@{
    counters = $orderedCounters
    last_version = $PackageVersion
    last_built_at = (Get-Date -Format o)
  }
  $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Set-PackagedBrowserExtensionVersion {
  param(
    [string]$ExtensionDir,
    [string]$PackageVersion,
    [string]$ChromeVersion
  )

  $manifestPath = Join-Path $ExtensionDir "manifest.json"
  if (-not (Test-Path -LiteralPath $manifestPath)) {
    return
  }

  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  $manifest.version = $ChromeVersion
  if ($manifest.PSObject.Properties.Name -contains "version_name") {
    $manifest.version_name = $PackageVersion
  } else {
    $manifest | Add-Member -NotePropertyName "version_name" -NotePropertyValue $PackageVersion
  }
  $manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
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

$buildTime = Get-Date
$stamp = $buildTime.ToString("yyyyMMdd_HHmmss_fff")
$baseVersion = if ([string]::IsNullOrWhiteSpace($Version)) {
  Get-DefaultBaseVersion -RootPath $root
} else {
  $Version.Trim()
}
if ([string]::IsNullOrWhiteSpace($baseVersion)) {
  throw "Version cannot be empty"
}
if ($ExactVersion) {
  $Version = $baseVersion
  $exactBuildMatch = [regex]::Match($Version, '\.(\d+)$')
  $packageBuildNumber = if ($exactBuildMatch.Success) { [int]$exactBuildMatch.Groups[1].Value } else { 0 }
} else {
  if ($baseVersion.Contains("+")) {
    throw "Base version should not include '+'. Use -ExactVersion to package an exact version string."
  }
  $nextVersion = Get-NextPackageVersion -RootPath $root -OutputRoot $OutputRoot -BaseVersion $baseVersion
  $Version = $nextVersion.Version
  $packageBuildNumber = [int]$nextVersion.BuildNumber
}
$chromeExtensionVersion = Get-ChromeExtensionVersion -BaseVersion $baseVersion -BuildNumber $packageBuildNumber
$safeVersion = $Version -replace '[^A-Za-z0-9._-]', '_'
$packageDir = Join-Path $OutputRoot "RefChecker_portable_v${safeVersion}"
$zipPath = "$packageDir.zip"

$venvPython = Join-Path $root ".venv_build\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$backendExe = Join-Path $root "backend\refchecker_backend.exe"
$httpServerExe = Join-Path $root "backend\refchecker_http_server.exe"
$releaseDir = Join-Path $root "build\windows\x64\runner\Release"

Write-Host "RefChecker Windows packaging"
Write-Host "Root       : $root"
Write-Host "Base       : $baseVersion"
Write-Host "Version    : $Version"
Write-Host "Build no.  : $packageBuildNumber"
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
    # Some local Flutter SDK builds have a Windows batch typo that invokes
    # "$git rev-parse HEAD" while preparing flutter_tools. If "$git" cannot be
    # resolved, flutter.bat can spin forever in its acquire_lock retry loop
    # before Dart/MSBuild ever start. Provide a narrow, temporary shim so the
    # SDK batch file resolves "$git" to the real git.exe without modifying the
    # user's Flutter installation.
    $flutterShimDir = Join-Path ([System.IO.Path]::GetTempPath()) "refchecker_flutter_cmd_shim_$stamp"
    New-Item -ItemType Directory -Force -Path $flutterShimDir | Out-Null
    $gitShimPath = Join-Path $flutterShimDir '$git.cmd'
    Set-Content -LiteralPath $gitShimPath -Encoding ASCII -Value "@echo off`r`ngit.exe %*`r`n"
    $oldPath = $env:PATH
    try {
      $env:PATH = "$flutterShimDir;$oldPath"
      flutter build windows --release --dart-define "APP_VERSION=$Version"
      Assert-LastExitCode "Flutter Windows build failed"
    } finally {
      $env:PATH = $oldPath
      Remove-Item -LiteralPath $flutterShimDir -Recurse -Force -ErrorAction SilentlyContinue
    }
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
  Set-Content -LiteralPath (Join-Path $packageDir "VERSION.txt") -Encoding UTF8 -Value $Version
  Set-Content -LiteralPath (Join-Path $packageDir "backend\VERSION.txt") -Encoding UTF8 -Value $Version
  if (Test-Path -LiteralPath (Join-Path $root "browser_extension\refchecker_claude")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "browser_extension") | Out-Null
    Copy-Item -LiteralPath (Join-Path $root "browser_extension\refchecker_claude") -Destination (Join-Path $packageDir "browser_extension") -Recurse -Force
    Set-PackagedBrowserExtensionVersion `
      -ExtensionDir (Join-Path $packageDir "browser_extension\refchecker_claude") `
      -PackageVersion $Version `
      -ChromeVersion $chromeExtensionVersion
  }
  foreach ($docName in @("README.md", "CHANGELOG.md", "BROWSER_EXTENSION_CLAUDE_WEB.md", "CUSTOM_REST_BRAVE_SEARCH.md", "MCP_CLAUDE_DESKTOP.md", "RELEASE_NOTES_v1.2.0.md", "RELEASE_NOTES_v1.2.0-beta.1.md")) {
    $docPath = Join-Path $root $docName
    if (Test-Path -LiteralPath $docPath) {
      Copy-Item -LiteralPath $docPath -Destination (Join-Path $packageDir $docName) -Force
    }
  }
  $braveExample = Join-Path $root "examples\brave_search_custom_rest_profile.example.json"
  if (Test-Path -LiteralPath $braveExample) {
    New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "examples") | Out-Null
    Copy-Item -LiteralPath $braveExample -Destination (Join-Path $packageDir "examples\brave_search_custom_rest_profile.example.json") -Force
  }

  $manifest = @(
    "RefChecker portable package",
    "Version: $Version",
    "BaseVersion: $baseVersion",
    "BuildNumber: $packageBuildNumber",
    "ChromeExtensionVersion: $chromeExtensionVersion",
    "BuiltAt: $(Get-Date -Format o)",
    "Frontend: refchecker_desktop.exe",
    "Backend: backend/refchecker_backend.exe",
    "Browser extension HTTP bridge: backend/refchecker_http_server.exe",
    "Claude web browser extension: browser_extension/refchecker_claude",
    "Brave custom REST example: examples/brave_search_custom_rest_profile.example.json",
    "",
    "Privacy: local settings and API keys are not copied into this package."
  ) -join [Environment]::NewLine
  Set-Content -LiteralPath (Join-Path $packageDir "PACKAGE_MANIFEST.txt") -Encoding UTF8 -Value $manifest

  $versionMetadata = [ordered]@{
    package_version = $Version
    base_version = $baseVersion
    build_number = $packageBuildNumber
    built_at = (Get-Date -Format o)
    chrome_extension_version = $chromeExtensionVersion
  }
  $versionMetadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $packageDir "PACKAGE_VERSION.json") -Encoding UTF8

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

if (-not $ExactVersion) {
  Save-BuildCounter -RootPath $root -BaseVersion $baseVersion -BuildNumber $packageBuildNumber -PackageVersion $Version
}

Write-Host ""
Write-Host "Package directory: $packageDir" -ForegroundColor Green
if (-not $NoZip) {
  Write-Host "Zip package      : $zipPath" -ForegroundColor Green
}
