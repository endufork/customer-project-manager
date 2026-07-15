$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

if ([string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PORT)) {
    $env:CUSTOMER_PROJECT_PORT = "8765"
}

if ($env:CUSTOMER_PROJECT_ENV -ne "test" -or [string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_TEST_ROOT)) {
    throw "Playwright test server requires an isolated CUSTOMER_PROJECT_ENV=test environment."
}

$python = Resolve-Python
if (-not [string]::IsNullOrWhiteSpace($python)) {
    & $python ".\tools\prepare_e2e_environment.py"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    & (Join-Path $PSScriptRoot "start-fastapi-server.ps1")
    exit $LASTEXITCODE
}

throw "Python was not found. Install Python, add it to PATH, or set CUSTOMER_PROJECT_PYTHON."
