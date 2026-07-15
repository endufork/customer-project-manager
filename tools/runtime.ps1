function Resolve-ExistingPath {
    param([string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    return ""
}

function Get-CodexDependencyPath {
    param([string]$RelativePath)

    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_RUNTIME_ROOT)) {
        $candidates += Join-Path $env:CUSTOMER_PROJECT_RUNTIME_ROOT $RelativePath
    }
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $candidates += Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\$RelativePath"
    }

    return Resolve-ExistingPath $candidates
}

function Resolve-Git {
    if (-not [string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_GIT) -and (Test-Path $env:CUSTOMER_PROJECT_GIT)) {
        return $env:CUSTOMER_PROJECT_GIT
    }

    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $fallbacks = @()
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $fallbacks += Join-Path $env:ProgramFiles "Git\cmd\git.exe"
    }
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
        $fallbacks += Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe"
    }

    $fallback = Resolve-ExistingPath $fallbacks
    if (-not [string]::IsNullOrWhiteSpace($fallback)) {
        return $fallback
    }

    throw "Git was not found. Install Git or add it to PATH."
}

function Resolve-Python {
    if (-not [string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PYTHON) -and (Test-Path $env:CUSTOMER_PROJECT_PYTHON)) {
        return $env:CUSTOMER_PROJECT_PYTHON
    }

    $projectVenv = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (Test-Path $projectVenv) {
        return (Resolve-Path $projectVenv).Path
    }

    $bundled = Get-CodexDependencyPath "python\python.exe"
    if (-not [string]::IsNullOrWhiteSpace($bundled)) {
        return $bundled
    }

    foreach ($name in @("python", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }

    return ""
}

function Resolve-Node {
    if (-not [string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_NODE) -and (Test-Path $env:CUSTOMER_PROJECT_NODE)) {
        return $env:CUSTOMER_PROJECT_NODE
    }

    $bundled = Get-CodexDependencyPath "node\bin\node.exe"
    if (-not [string]::IsNullOrWhiteSpace($bundled)) {
        return $bundled
    }

    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return ""
}
