$ErrorActionPreference = "Stop"

. "$PSScriptRoot\runtime.ps1"

$python = Resolve-Python
if ([string]::IsNullOrWhiteSpace($python)) {
    throw "Python was not found. Install Python or set CUSTOMER_PROJECT_PYTHON."
}

& $python "$PSScriptRoot\cleanup_test_data.py" @args
