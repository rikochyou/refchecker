param(
  [ValidateSet("windows", "macos")]
  [string]$Platform = "windows"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$venvPython = Join-Path $root ".venv_build\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

& $python -m pip install -r requirements.txt

$backendName = if ($Platform -eq "windows") { "refchecker_backend.exe" } else { "refchecker_backend" }
$httpName = if ($Platform -eq "windows") { "refchecker_http_server.exe" } else { "refchecker_http_server" }
& $python -m PyInstaller --clean --onefile --name refchecker_backend check_bib_crossref.py
& $python -m PyInstaller --clean --onefile --name refchecker_http_server refchecker_http_server.py

$backendDir = Join-Path $root "backend"
New-Item -ItemType Directory -Force -Path $backendDir | Out-Null

$backendSource = if ($Platform -eq "windows") {
  Join-Path $root "dist\refchecker_backend.exe"
} else {
  Join-Path $root "dist/refchecker_backend"
}
$httpSource = if ($Platform -eq "windows") {
  Join-Path $root "dist\refchecker_http_server.exe"
} else {
  Join-Path $root "dist/refchecker_http_server"
}

Copy-Item -Force -LiteralPath $backendSource -Destination (Join-Path $backendDir $backendName)
Copy-Item -Force -LiteralPath $httpSource -Destination (Join-Path $backendDir $httpName)
Write-Host "Backend copied to backend/$backendName"
Write-Host "HTTP server copied to backend/$httpName"
