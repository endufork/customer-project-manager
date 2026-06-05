$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

$python = Resolve-Python
if ([string]::IsNullOrWhiteSpace($python)) {
    throw "Python was not found. Install Python, add it to PATH, or set CUSTOMER_PROJECT_PYTHON."
}

$port = if ([string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PORT)) { "8765" } else { $env:CUSTOMER_PROJECT_PORT }
& $python -m uvicorn customer_m.fastapi_app:app --host 127.0.0.1 --port $port
