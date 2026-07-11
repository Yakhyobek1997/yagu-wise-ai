# Auralynq -- Windows launcher (PowerShell)
# Requires: Podman Desktop OR Docker Desktop + Ollama installed
#
# Usage:
#   .\start-podman.ps1 -Build          # first time -- builds images then starts
#   .\start-podman.ps1 -Build -NoCache # clean rebuild
#   .\start-podman.ps1                 # subsequent runs
#
# Access: https://localhost:8443
#   (self-signed cert -- click Advanced then Proceed to localhost)

param(
    [switch]$Build,
    [switch]$NoCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$EnvFile = Join-Path $Repo ".env.podman.windows"

# ---- Pick container engine --------------------------------------------------
$Engine = ""
if (Get-Command podman -ErrorAction SilentlyContinue) {
    $Engine = "podman"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $Engine = "docker"
} else {
    Write-Error "Neither podman nor docker found. Install Podman Desktop or Docker Desktop."
    exit 1
}

Write-Host "-> Using container engine: $Engine" -ForegroundColor Cyan

# ---- Helper: wait for TCP port ----------------------------------------------
function Wait-Port {
    param($HostName, $Port, $Name, $Retries = 30)
    $n = 0
    while ($n -lt $Retries) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect($HostName, $Port)
            $tcp.Close()
            Write-Host "OK  $Name is up on :$Port" -ForegroundColor Green
            return
        } catch {
            $n++
            Start-Sleep -Seconds 1
        }
    }
    throw "$Name did not open port $Port after ${Retries}s"
}

# ---- 1. Ollama: rebind to 0.0.0.0 ------------------------------------------
Write-Host "-> Restarting Ollama on 0.0.0.0:11434 ..." -ForegroundColor Cyan

$ollamaProc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($ollamaProc) {
    $ollamaProc | Stop-Process -Force
    Start-Sleep -Seconds 1
}

$env:OLLAMA_HOST = "0.0.0.0"
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
Wait-Port -HostName "127.0.0.1" -Port 11434 -Name "Ollama"

# ---- 2. Write Windows env file ----------------------------------------------
$envContent = @"
AURALYNQ_CERT_HOST=localhost
AURALYNQ_SITE_ADDRESS=:8443
AURALYNQ_HTTPS_PORT=8443
AURALYNQ_TLS=/certs/site.crt /certs/site.key
AURALYNQ_WEB_UPSTREAM=http://auralynq-web:3000

AURALYNQ_BIND_INTERNAL=127.0.0.1
AURALYNQ_API_PORT=8100
AURALYNQ_QDRANT_HTTP_PORT=6433
AURALYNQ_QDRANT_GRPC_PORT=6434
AURALYNQ_WEB_PORT=3800
AURALYNQ_PHOENIX_PORT=6006
AURALYNQ_PHOENIX_OTLP_PORT=4317
AURALYNQ_MCP_PORT=8765

AURALYNQ_LLM__PROVIDER=auto
AURALYNQ_LLM__MODEL=qwen3:32b
AURALYNQ_LLM__BASE_URL=http://host.containers.internal:11434

AURALYNQ_EMBEDDING__PROVIDER=auto
AURALYNQ_EMBEDDING__OLLAMA_MODEL=nomic-embed-text

AURALYNQ_VECTOR_URL=http://auralynq-qdrant:6333
AURALYNQ_VECTOR_BACKEND=qdrant

AURALYNQ_SERVE__API_KEY=
AURALYNQ_SERVE__CORS_ORIGINS=["https://localhost:8443"]

AURALYNQ_API_INTERNAL=http://auralynq-api:8000
AURALYNQ_OTLP_ENDPOINT=http://auralynq-phoenix:4317

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
COHERE_API_KEY=
HUGGINGFACE_TOKEN=

AURALYNQ_IMAGE_PREFIX=localhost/auralynq-
AURALYNQ_IMAGE_TAG=0.2.0
"@
Set-Content -Path $EnvFile -Value $envContent -Encoding UTF8
Write-Host "OK  Created $EnvFile" -ForegroundColor Green

# ---- 3. Build images --------------------------------------------------------
if ($Build) {
    $prefix = "localhost/auralynq-"
    $tag    = "0.2.0"
    $nc     = if ($NoCache) { "--no-cache" } else { $null }

    Write-Host "-> Building caddy image ..." -ForegroundColor Cyan
    $args = @("build")
    if ($nc) { $args += $nc }
    $args += @("--build-arg", "AURALYNQ_CERT_HOST=localhost",
               "-f", (Join-Path $Repo "containers\caddy.Dockerfile"),
               "-t", "${prefix}caddy:${tag}", $Repo)
    & $Engine @args
    Write-Host "OK  caddy built" -ForegroundColor Green

    Write-Host "-> Building api image ..." -ForegroundColor Cyan
    $args = @("build")
    if ($nc) { $args += $nc }
    $args += @("-f", (Join-Path $Repo "containers\api.Dockerfile"),
               "-t", "${prefix}api:${tag}", $Repo)
    & $Engine @args
    Write-Host "OK  api built" -ForegroundColor Green

    Write-Host "-> Building web image ..." -ForegroundColor Cyan
    $args = @("build")
    if ($nc) { $args += $nc }
    $args += @("--build-arg", "NEXT_PUBLIC_API_BASE=/api",
               "-f", (Join-Path $Repo "containers\web.Dockerfile"),
               "-t", "${prefix}web:${tag}", (Join-Path $Repo "web"))
    & $Engine @args
    Write-Host "OK  web built" -ForegroundColor Green
} else {
    Write-Host "-> Skipping build (pass -Build to rebuild)" -ForegroundColor Yellow
}

# ---- 4. Start stack ---------------------------------------------------------
Write-Host "-> Starting stack ..." -ForegroundColor Cyan
if ($Engine -eq "podman") {
    & podman-compose --env-file $EnvFile up -d
} else {
    & docker compose --env-file $EnvFile up -d
}

# ---- 5. Wait for Caddy HTTPS ------------------------------------------------
Write-Host "-> Waiting for Caddy on :8443 ..." -ForegroundColor Cyan
$n = 0
$up = $false
while ($n -lt 60) {
    try {
        Add-Type -AssemblyName System.Net.Http -ErrorAction SilentlyContinue
        $handler = New-Object System.Net.Http.HttpClientHandler
        $handler.ServerCertificateCustomValidationCallback = [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
        $client  = New-Object System.Net.Http.HttpClient($handler)
        $client.Timeout = [System.TimeSpan]::FromSeconds(3)
        $response = $client.GetAsync("https://localhost:8443").Result
        $client.Dispose()
        $up = $true
        break
    } catch {
        $n++
        Start-Sleep -Seconds 2
    }
}

if ($up) {
    Write-Host "OK  Caddy is up" -ForegroundColor Green
} else {
    Write-Warning "Caddy did not respond after 120s. Check logs:"
    if ($Engine -eq "podman") {
        Write-Host "  podman-compose --env-file $EnvFile logs caddy"
    } else {
        Write-Host "  docker compose --env-file $EnvFile logs caddy"
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Auralynq is ready" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Chat UI:    https://localhost:8443"
Write-Host "  ModelFit:   https://localhost:8443/modelfit"
Write-Host "  API health: https://localhost:8443/api/health"
Write-Host ""
Write-Host "  Self-signed cert: click Advanced then Proceed to localhost" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Logs:  podman-compose --env-file .env.podman.windows logs -f"
Write-Host "  Stop:  podman-compose --env-file .env.podman.windows down"
Write-Host "============================================================" -ForegroundColor Cyan
