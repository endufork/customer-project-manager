$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "runtime.ps1")

$Python = Resolve-Python
if ([string]::IsNullOrWhiteSpace($Python)) {
    throw "Python was not found. Install Python or set CUSTOMER_PROJECT_PYTHON."
}

$CacheDir = Join-Path $RepoRoot ".playwright-cache\dependency-lock"
New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null

function Resolve-DependencyReport {
    param(
        [string]$InputFile,
        [string]$ReportFile
    )

    Write-Host "Resolving $InputFile..."
    & $Python -m pip install `
        --dry-run `
        --ignore-installed `
        --report $ReportFile `
        --cache-dir (Join-Path $RepoRoot ".playwright-cache\pip-cache") `
        --retries 5 `
        --timeout 60 `
        -r $InputFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to resolve $InputFile."
    }
}

function Read-DependencyPins {
    param([string]$ReportFile)

    $report = Get-Content -LiteralPath $ReportFile -Raw -Encoding UTF8 | ConvertFrom-Json
    return @(
        $report.install |
            ForEach-Object {
                $name = $_.metadata.name.ToLowerInvariant().Replace("_", "-")
                [PSCustomObject]@{
                    Name = $name
                    Pin = "$name==$($_.metadata.version)"
                }
            } |
            Sort-Object Name
    )
}

function Write-Utf8Lines {
    param(
        [string]$Path,
        [string[]]$Lines
    )

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($Path, $Lines, $encoding)
}

$RuntimeReport = Join-Path $CacheDir "runtime-report.json"
$DevReport = Join-Path $CacheDir "dev-report.json"
Resolve-DependencyReport "requirements.in" $RuntimeReport
Resolve-DependencyReport "requirements-dev.in" $DevReport

$runtimePins = @(Read-DependencyPins $RuntimeReport)
$devPins = @(Read-DependencyPins $DevReport)
$runtimeNames = @{}
foreach ($item in $runtimePins) {
    $runtimeNames[$item.Name] = $true
}
$devOnlyPins = @($devPins | Where-Object { -not $runtimeNames.ContainsKey($_.Name) })

Write-Utf8Lines (Join-Path $RepoRoot "requirements.txt") @(
    "# Locked Windows/Python 3.12 runtime dependencies."
    "# Source constraints: requirements.in"
    $runtimePins.Pin
)
Write-Utf8Lines (Join-Path $RepoRoot "requirements-dev.txt") @(
    "# Locked development and test dependencies."
    "-r requirements.txt"
    ""
    $devOnlyPins.Pin
)

Write-Host "Updated requirements.txt and requirements-dev.txt."
