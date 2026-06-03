$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

$Git = Resolve-Git
& $Git config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure Git hooks path."
}

Write-Host "Git hooks installed for this repository."
Write-Host "Every git commit will run .\tools\check.cmd through .githooks\pre-commit."
