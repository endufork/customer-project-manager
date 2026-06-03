param(
    [ValidateSet("test", "ui", "headed", "install")]
    [string]$Command = "test"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

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
