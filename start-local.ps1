[CmdletBinding()]
param(
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$runtimeDir = Join-Path $repoRoot ".local-run"
$stateFile = Join-Path $runtimeDir "processes.json"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$nextEntry = Join-Path $repoRoot "web\node_modules\next\dist\bin\next"
Set-Location -LiteralPath $repoRoot

function Test-LocalPort([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-LocalUrl([string]$Url, [int]$Attempts) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

$needsSetup = -not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath $nextEntry)
if ($needsSetup) {
    if ($SkipSetup) {
        throw "Dependencies are missing. Run .\setup-local.ps1 first."
    }
    & (Join-Path $repoRoot "setup-local.ps1")
}

if (Test-Path -LiteralPath $stateFile) {
    & (Join-Path $repoRoot "stop-local.ps1") -Quiet
}

foreach ($port in 8000, 3000) {
    if (Test-LocalPort $port) {
        throw "Port $port is already in use. Stop the process using it, then run this script again."
    }
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$apiOut = Join-Path $runtimeDir "api.out.log"
$apiErr = Join-Path $runtimeDir "api.err.log"
$webOut = Join-Path $runtimeDir "web.out.log"
$webErr = Join-Path $runtimeDir "web.err.log"

Write-Host "Starting local API on http://127.0.0.1:8000 ..."
$api = Start-Process `
    -FilePath $venvPython `
    -ArgumentList @("-m", "uvicorn", "yaguwiseai.serving.app:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $apiOut `
    -RedirectStandardError $apiErr `
    -PassThru

if (-not (Wait-LocalUrl "http://127.0.0.1:8000/health" 60)) {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    throw "API did not start. See $apiErr"
}

$env:NEXT_PUBLIC_API_BASE = "/api"
$env:YAGUWISEAI_API_INTERNAL = "http://127.0.0.1:8000"
$nodePath = (Get-Command node -ErrorAction Stop).Source

Write-Host "Starting local web UI on http://127.0.0.1:3000 ..."
$web = Start-Process `
    -FilePath $nodePath `
    -ArgumentList @(".\node_modules\next\dist\bin\next", "dev", "--hostname", "127.0.0.1", "--port", "3000") `
    -WorkingDirectory (Join-Path $repoRoot "web") `
    -WindowStyle Hidden `
    -RedirectStandardOutput $webOut `
    -RedirectStandardError $webErr `
    -PassThru

$state = @{
    api = @{ pid = $api.Id; started_at = $api.StartTime.ToUniversalTime().ToString("o") }
    web = @{ pid = $web.Id; started_at = $web.StartTime.ToUniversalTime().ToString("o") }
}
$state | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $stateFile -Encoding UTF8

if (-not (Wait-LocalUrl "http://127.0.0.1:3000" 120)) {
    & (Join-Path $repoRoot "stop-local.ps1") -Quiet
    throw "Web UI did not start. See $webErr"
}

Write-Host ""
Write-Host "YaguWiseAi is running locally: http://127.0.0.1:3000" -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:8000/docs"
Write-Host "Logs: $runtimeDir"
Write-Host "Stop: .\stop-local.ps1"
