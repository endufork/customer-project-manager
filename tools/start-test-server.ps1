$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PORT)) {
    $env:CUSTOMER_PROJECT_PORT = "8765"
}

$bundledPython = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $bundledPython) {
    & $bundledPython app.py
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & $python.Source app.py
    exit $LASTEXITCODE
}

throw "Python was not found. Install Python or use the Codex bundled runtime."
