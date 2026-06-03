param(
    [ValidateSet("test", "ui", "headed", "install")]
    [string]$Command = "test"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Resolve-Node {
    $candidates = @(
        "C:\Program Files\nodejs\node.exe",
        "C:\Program Files (x86)\nodejs\node.exe",
        "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        return $node.Source
    }

    throw "Node.js was not found. Install Node.js LTS first."
}

$Node = Resolve-Node

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
