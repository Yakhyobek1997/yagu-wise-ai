[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
Set-Location -LiteralPath $repoRoot

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ was not found in PATH. Install Python and run this script again."
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 18.18+ was not found in PATH. Install Node.js LTS and run this script again."
}

$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Assert-LastExitCode "Python version check"
$versionParts = $pythonVersion.Trim().Split('.')
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 11)) {
    throw "Python 3.11+ is required; found $pythonVersion."
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating Python virtual environment..."
    & python -m venv .venv
    Assert-LastExitCode "Virtual environment creation"
}

Write-Host "Installing local backend dependencies..."
& $venvPython -m pip install --disable-pip-version-check -e ".[ingest]"
Assert-LastExitCode "Backend dependency installation"

Write-Host "Installing frontend dependencies..."
Push-Location (Join-Path $repoRoot "web")
try {
    & npm.cmd ci --no-audit --no-fund
    Assert-LastExitCode "Frontend dependency installation"
}
finally {
    Pop-Location
}

Write-Host "Local setup complete. Start YaguWiseAi with: .\start-local.ps1"
