$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Resolve-Git {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $fallback = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path $fallback) {
        return $fallback
    }

    throw "Git was not found. Install Git or add it to PATH."
}

$Git = Resolve-Git
& $Git config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure Git hooks path."
}

Write-Host "Git hooks installed for this repository."
Write-Host "Every git commit will run .\tools\check.cmd through .githooks\pre-commit."
