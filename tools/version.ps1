param(
    [ValidateSet("status", "branch", "save", "release", "help")]
    [string]$Action = "status",

    [string]$Name = "",

    [ValidateSet("feat", "fix", "refactor", "docs", "style", "data", "chore")]
    [string]$Type = "chore",

    [string]$Message = "",

    [string]$Version = "",

    [switch]$Push
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

    $commands = @("python")
    foreach ($item in $commands) {
        $cmd = Get-Command $item -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
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
    return $output
}

function Git-Run {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)

    & $Git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($GitArgs -join ' ')"
    }
}

function Get-GitOrDefault {
    param([string[]]$GitArgs, [string]$Default = "")

    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Git @GitArgs 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $Default
        }
        return ($output -join "`n").Trim()
    } catch {
        return $Default
    } finally {
        $ErrorActionPreference = $oldPreference
    }
}

function Get-StatusLines {
    $output = & $Git status --short 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join "`n")
    }
    return @($output)
}

function Get-RiskTrackedFiles {
    $tracked = Git-Text ls-files "data" "__pycache__" "server.log" "server.err"
    return @($tracked | Where-Object { $_ -match "^(data/|__pycache__/|server\.log$|server\.err$)" })
}

function Assert-NoRiskTrackedFiles {
    $risk = Get-RiskTrackedFiles
    if ($risk.Count -gt 0) {
        throw "Risk files are tracked by Git. Remove them from Git before saving:`n$($risk -join "`n")"
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "Customer Project Manager version helper"
    Write-Host ""
    Write-Host "Common commands:"
    Write-Host "  .\tools\version.cmd status"
    Write-Host "  .\tools\version.cmd save -Type feat -Message ""add backup button"" -Push"
    Write-Host "  .\tools\version.cmd branch -Name backup-system"
    Write-Host "  .\tools\version.cmd release -Version v0.2.0 -Push"
    Write-Host ""
    Write-Host "Rules:"
    Write-Host "  Git tracks code and docs only."
    Write-Host "  Do not track data/customer_projects.db, customer files, logs, or caches."
    Write-Host "  Use main for stable versions; use codex/* branches for larger changes."
    Write-Host ""
}

function Show-Status {
    $branch = (Git-Text branch --show-current).Trim()
    $upstream = Get-GitOrDefault @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") "(no upstream)"
    $latestCommit = Get-GitOrDefault @("log", "-1", "--oneline") "(no commits)"
    $latestTag = Get-GitOrDefault @("describe", "--tags", "--abbrev=0") "(no tags)"
    $status = Get-StatusLines
    $risk = Get-RiskTrackedFiles

    Write-Host ""
    Write-Host "Branch:        $branch"
    Write-Host "Upstream:      $upstream"
    Write-Host "Latest commit: $latestCommit"
    Write-Host "Latest tag:    $latestTag"
    Write-Host ""

    if ($status.Count -eq 0) {
        Write-Host "Working tree:  clean"
    } else {
        Write-Host "Working tree:"
        $status | ForEach-Object { Write-Host "  $_" }
    }

    Write-Host ""
    if ($risk.Count -eq 0) {
        Write-Host "Data safety:   OK - database/log/cache files are not tracked"
    } else {
        Write-Host "Data safety:   WARNING - risk files are tracked"
        $risk | ForEach-Object { Write-Host "  $_" }
    }
    Write-Host ""
}

function New-WorkBranch {
    if ([string]::IsNullOrWhiteSpace($Name)) {
        throw "Missing branch name. Example: .\tools\version.ps1 branch -Name backup-system"
    }

    $slug = $Name.Trim().ToLowerInvariant()
    $slug = $slug -replace "\s+", "-"
    $slug = $slug -replace "[^a-z0-9._/-]", "-"
    if (-not $slug.StartsWith("codex/")) {
        $slug = "codex/$slug"
    }

    Git-Run checkout -b $slug
    Write-Host "Created and switched to branch: $slug"
}

function Test-PythonCompile {
    $python = Resolve-Python
    if ([string]::IsNullOrWhiteSpace($python)) {
        Write-Host "Python compile check skipped: Python was not found."
        return
    }

    $files = @("app.py")
    if (Test-Path (Join-Path $RepoRoot "customer_m")) {
        $files += Get-ChildItem -Path (Join-Path $RepoRoot "customer_m") -Filter "*.py" | ForEach-Object { $_.FullName }
    }

    if ($files.Count -eq 0) {
        return
    }

    Write-Host "Running Python compile check..."
    & $python -m py_compile @files
    if ($LASTEXITCODE -ne 0) {
        throw "Python compile check failed."
    }
}

function Save-Changes {
    if ([string]::IsNullOrWhiteSpace($Message)) {
        throw "Missing commit message. Example: .\tools\version.ps1 save -Type feat -Message ""add backup button"""
    }

    Assert-NoRiskTrackedFiles
    $status = Get-StatusLines
    if ($status.Count -eq 0) {
        Write-Host "Nothing to save. Working tree is clean."
        return
    }

    Test-PythonCompile

    Git-Run add app.py customer_m static tools "*.md" "*.sql" run_server.cmd .gitignore

    $staged = Git-Text diff --cached --name-only
    if (@($staged).Count -eq 0) {
        Write-Host "No code or document changes were staged."
        Write-Host "Unstaged files are probably data, logs, cache, or customer files."
        return
    }

    Write-Host "Staged files:"
    @($staged) | ForEach-Object { Write-Host "  $_" }

    $commitMessage = "${Type}: $Message"
    Git-Run commit -m $commitMessage

    if ($Push) {
        Git-Run push
    }
}

function New-Release {
    if ([string]::IsNullOrWhiteSpace($Version)) {
        throw "Missing version. Example: .\tools\version.ps1 release -Version v0.2.0"
    }

    $releaseVersion = $Version.Trim()
    if (-not $releaseVersion.StartsWith("v")) {
        $releaseVersion = "v$releaseVersion"
    }

    $status = Get-StatusLines
    if ($status.Count -gt 0) {
        throw "Release requires a clean working tree. Save or discard changes first."
    }

    $existing = Get-GitOrDefault @("tag", "--list", $releaseVersion)
    if (-not [string]::IsNullOrWhiteSpace($existing)) {
        throw "Tag already exists: $releaseVersion"
    }

    Git-Run tag -a $releaseVersion -m "Release $releaseVersion"
    Write-Host "Created release tag: $releaseVersion"

    if ($Push) {
        Git-Run push origin $releaseVersion
    }
}

switch ($Action) {
    "status" { Show-Status }
    "branch" { New-WorkBranch }
    "save" { Save-Changes }
    "release" { New-Release }
    "help" { Show-Help }
}
