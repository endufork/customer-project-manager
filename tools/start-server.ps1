$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

$python = Resolve-Python
if ([string]::IsNullOrWhiteSpace($python)) {
    throw "Python was not found. Install Python, add it to PATH, or set CUSTOMER_PROJECT_PYTHON."
}

& $python app.py
