param(
    [ValidateSet("test", "ui", "headed", "install")]
    [string]$Command = "test"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

if ($Command -ne "install") {
    $runId = "{0}-{1}" -f ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()), $PID
    $testRoot = Join-Path $RepoRoot ".playwright-cache\e2e-$runId"
    $env:CUSTOMER_PROJECT_ENV = "test"
    $env:CUSTOMER_PROJECT_PORT = [string](20000 + ($PID % 20000))
    $env:CUSTOMER_PROJECT_DATA_DIR = Join-Path $testRoot "data"
    $env:CUSTOMER_PROJECT_DB_PATH = Join-Path $env:CUSTOMER_PROJECT_DATA_DIR "customer_projects.db"
    $env:CUSTOMER_PROJECT_LOG_DIR = Join-Path $testRoot "logs"
    $env:CUSTOMER_PROJECT_TEST_ROOT = $testRoot
    $env:CUSTOMER_PROJECT_E2E_RUN_ID = $runId
    New-Item -ItemType Directory -Path $env:CUSTOMER_PROJECT_DATA_DIR -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $testRoot "projects") -Force | Out-Null
    New-Item -ItemType Directory -Path $env:CUSTOMER_PROJECT_LOG_DIR -Force | Out-Null
}

$Node = Resolve-Node
if ([string]::IsNullOrWhiteSpace($Node)) {
    throw "Node.js was not found. Install Node.js LTS, add it to PATH, or set CUSTOMER_PROJECT_NODE."
}

switch ($Command) {
    "install" {
        & $Node ".\node_modules\playwright\cli.js" install chromium
    }
    "ui" {
        & $Node ".\node_modules\@playwright\test\cli.js" test --ui
    }
    "headed" {
        & $Node ".\node_modules\@playwright\test\cli.js" test --headed
    }
    default {
        & $Node ".\node_modules\@playwright\test\cli.js" test
    }
}

exit $LASTEXITCODE
