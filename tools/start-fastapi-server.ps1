$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

if ([string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_ENV)) {
    $env:CUSTOMER_PROJECT_ENV = "development"
}

function Test-PythonModule {
    param(
        [string]$Python,
        [string]$ModuleName
    )

    if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path $Python)) {
        return $false
    }

    & $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Resolve-FastApiPython {
    $candidates = @()

    if (-not [string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PYTHON)) {
        $candidates += $env:CUSTOMER_PROJECT_PYTHON
    }

    $resolved = Resolve-Python
    if (-not [string]::IsNullOrWhiteSpace($resolved)) {
        $candidates += $resolved
    }

    $pathPython = Get-Command python -ErrorAction SilentlyContinue
    if ($pathPython) {
        $candidates += $pathPython.Source
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-PythonModule $candidate "uvicorn") {
            return $candidate
        }
    }

    throw "FastAPI runtime was not found. Install dependencies with 'python -m pip install -r requirements.txt', or set CUSTOMER_PROJECT_PYTHON to the Python executable that has uvicorn installed."
}

$python = Resolve-FastApiPython
if ([string]::IsNullOrWhiteSpace($python)) {
    throw "Python was not found. Install Python, add it to PATH, or set CUSTOMER_PROJECT_PYTHON."
}

$port = if ([string]::IsNullOrWhiteSpace($env:CUSTOMER_PROJECT_PORT)) { "8765" } else { $env:CUSTOMER_PROJECT_PORT }
& $python -m uvicorn customer_m.fastapi_app:app --host 127.0.0.1 --port $port
