[CmdletBinding()]
param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$runtimeDir = Join-Path $PSScriptRoot ".local-run"
$stateFile = Join-Path $runtimeDir "processes.json"

if (-not (Test-Path -LiteralPath $stateFile)) {
    if (-not $Quiet) {
        Write-Host "YaguWiseAi local processes are not recorded as running."
    }
    exit 0
}

$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($name in "web", "api") {
    $entry = $state.$name
    if ($null -eq $entry) {
        continue
    }

    $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        continue
    }

    $actualStart = $process.StartTime.ToUniversalTime().ToString("o")
    if ($actualStart -ne [string]$entry.started_at) {
        if (-not $Quiet) {
            Write-Warning "Skipping PID $($entry.pid): it belongs to a newer process."
        }
        continue
    }

    & taskkill.exe /PID ([int]$entry.pid) /T /F 2>$null | Out-Null
}

Remove-Item -LiteralPath $stateFile -Force
if (-not $Quiet) {
    Write-Host "YaguWiseAi local processes stopped."
}
