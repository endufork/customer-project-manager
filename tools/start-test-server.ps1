$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

if ([string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PORT)) {
    $env:CUSTOMER_PROJECT_PORT = "8765"
}

$python = Resolve-Python
if (-not [string]::IsNullOrWhiteSpace($python)) {
    & $python app.py
    exit $LASTEXITCODE
}

throw "Python was not found. Install Python, add it to PATH, or set CUSTOMER_PROJECT_PYTHON."
