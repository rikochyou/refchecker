param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
  throw "Flutter is not available on PATH. Install Flutter, enable desktop support, then rerun this script."
}

if ($Force) {
  flutter create --platforms=windows,macos --overwrite .
} else {
  flutter create --platforms=windows,macos .
}

flutter pub get
