param(
  [ValidateSet("windows", "macos")]
  [string]$Platform = "windows"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

python -m pip install -r requirements.txt

$name = if ($Platform -eq "windows") { "refchecker_backend.exe" } else { "refchecker_backend" }
python -m PyInstaller --clean --onefile --name refchecker_backend check_bib_crossref.py

$backendDir = Join-Path $root "backend"
New-Item -ItemType Directory -Force -Path $backendDir | Out-Null

$source = if ($Platform -eq "windows") {
  Join-Path $root "dist\refchecker_backend.exe"
} else {
  Join-Path $root "dist/refchecker_backend"
}

Copy-Item -Force -LiteralPath $source -Destination (Join-Path $backendDir $name)
Write-Host "Backend copied to backend/$name"
