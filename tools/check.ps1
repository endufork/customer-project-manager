param(
    [ValidateSet("Manual", "PreCommit")]
    [string]$Mode = "Manual"
)

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

function Resolve-Python {
    $fallback = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $fallback) {
        return $fallback
    }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return ""
}

function Resolve-Node {
    $fallback = "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path $fallback) {
        return $fallback
    }

    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return ""
}

$Git = Resolve-Git

function Git-Text {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)

    $output = & $Git @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join "`n")
    }
    return @($output)
}

function Test-RiskPath {
    param([string]$Path)

    $normalized = $Path -replace "\\", "/"
    return (
        $normalized -match "^data/" -or
        $normalized -match "(^|/)customer_projects\.db$" -or
        $normalized -match "^server\.(log|err|pid)$" -or
        $normalized -match "(^|/)__pycache__/" -or
        $normalized -match "\.pyc$" -or
        $normalized -match "^D:/01_CustomerProject/"
    )
}

function Assert-NoRiskFiles {
    $tracked = Git-Text ls-files
    $trackedRisk = @($tracked | Where-Object { Test-RiskPath $_ })
    if ($trackedRisk.Count -gt 0) {
        throw "Risk files are tracked by Git. Remove them before committing:`n$($trackedRisk -join "`n")"
    }

    $staged = Git-Text diff --cached --name-only
    $stagedRisk = @($staged | Where-Object { Test-RiskPath $_ })
    if ($stagedRisk.Count -gt 0) {
        throw "Risk files are staged. Unstage them before committing:`n$($stagedRisk -join "`n")"
    }
}

function Show-BranchGuidance {
    $branch = (Git-Text branch --show-current | Select-Object -First 1).Trim()
    if ($Mode -eq "PreCommit" -and $branch -eq "main") {
        Write-Host "Branch: main"
        Write-Host "Reminder: keep main stable. Use codex/* branches for larger features."
    } else {
        Write-Host "Branch: $branch"
    }
}

function Test-PythonCompile {
    $python = Resolve-Python
    if ([string]::IsNullOrWhiteSpace($python)) {
        Write-Host "Python compile check skipped: Python was not found."
        return
    }

    $targets = @()
    if (Test-Path (Join-Path $RepoRoot "app.py")) {
        $targets += "app.py"
    }
    if (Test-Path (Join-Path $RepoRoot "customer_m")) {
        $targets += "customer_m"
    }

    if ($targets.Count -eq 0) {
        return
    }

    Write-Host "Running Python compile check..."
    & $python -m compileall @targets
    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }
}

function Test-JavaScript {
    $node = Resolve-Node
    if ([string]::IsNullOrWhiteSpace($node)) {
        Write-Host "JavaScript check skipped: Node.js was not found."
        return
    }

    $appJs = Join-Path $RepoRoot "static\app.js"
    if (-not (Test-Path $appJs)) {
        return
    }

    Write-Host "Running JavaScript syntax check..."
    & $node --check $appJs
    if ($LASTEXITCODE -ne 0) {
        throw "JavaScript syntax check failed."
    }
}

Write-Host ""
Write-Host "Customer Project Manager checks"
Write-Host "Mode: $Mode"
Show-BranchGuidance
Assert-NoRiskFiles
Test-PythonCompile
Test-JavaScript
Write-Host "Checks passed."
Write-Host ""
