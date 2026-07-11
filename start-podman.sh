#!/usr/bin/env bash
# ============================================================================
# Auralynq — Podman stack launcher for server 172.24.50.21
#
# Usage: ./start-podman.sh [--build] [--no-cache]
#   --build      Force rebuild of all 3 images before starting
#   --no-cache   Combine with --build to ignore Docker layer cache
#
# Access: https://172.24.50.21:8443
#   (self-signed cert baked at build time — "Accept Risk" in browser on first visit)
# ============================================================================

set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$REPO/.env.podman"

DO_BUILD=0
NO_CACHE=""

for arg in "$@"; do
  case $arg in
    --build)    DO_BUILD=1 ;;
    --no-cache) NO_CACHE="--no-cache" ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────
die()  { echo "✗  $*" >&2; exit 1; }
info() { echo "→  $*"; }
ok()   { echo "✓  $*"; }

wait_tcp() {
  local host=$1 port=$2 name=$3 n=0
  until bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; do
    ((n++)); [[ $n -gt 30 ]] && die "$name did not open $port after 30s"
    sleep 1
  done
  ok "$name is reachable on $port"
}

# ── 1. Restart Ollama bound to all interfaces ─────────────────────────────────
# Containers cannot reach 127.0.0.1 — Ollama must listen on 0.0.0.0.
info "Restarting Ollama on 0.0.0.0:11434 …"
pkill -f "ollama serve" 2>/dev/null || true
sleep 1
OLLAMA_HOST=0.0.0.0 nohup ollama serve >> /tmp/ollama-podman.log 2>&1 &
OLLAMA_PID=$!
info "Ollama PID=$OLLAMA_PID  (log: /tmp/ollama-podman.log)"
wait_tcp 127.0.0.1 11434 "Ollama"

# ── 2. Stop dev services to free host debug ports ────────────────────────────
info "Stopping any dev uvicorn / next.js processes …"
pkill -f "uvicorn auralynq" 2>/dev/null && ok "dev API stopped" || true
pkill -f "next.*300[01]" 2>/dev/null && ok "dev UI stopped" || true
sleep 1

# ── 3. Build images (api, web, caddy) ────────────────────────────────────────
if [[ $DO_BUILD -eq 1 ]]; then
  CERT_HOST="${AURALYNQ_CERT_HOST:-172.24.50.21}"
  IMAGE_PREFIX="localhost/auralynq-"
  TAG="0.2.0"

  info "Building caddy image (cert host: $CERT_HOST) …"
  # MUST use `podman build` directly — `podman-compose build --no-cache` does NOT
  # propagate --no-cache into multi-stage layers for the api/web images.
  podman build $NO_CACHE \
    --build-arg AURALYNQ_CERT_HOST="$CERT_HOST" \
    -f "$REPO/containers/caddy.Dockerfile" \
    -t "${IMAGE_PREFIX}caddy:${TAG}" \
    "$REPO"
  ok "caddy image built"

  info "Building api image …"
  podman build $NO_CACHE \
    -f "$REPO/containers/api.Dockerfile" \
    -t "${IMAGE_PREFIX}api:${TAG}" \
    "$REPO"
  ok "api image built"

  info "Building web image (NEXT_PUBLIC_API_BASE=/api baked in) …"
  podman build $NO_CACHE \
    --build-arg NEXT_PUBLIC_API_BASE=/api \
    -f "$REPO/containers/web.Dockerfile" \
    -t "${IMAGE_PREFIX}web:${TAG}" \
    "$REPO/web"
  ok "web image built"
else
  info "Skipping build (pass --build to rebuild, --build --no-cache to force clean)"
fi

# ── 4. CNI / dnsname prerequisite check ──────────────────────────────────────
# podman-compose needs dnsname plugin for container-to-container DNS.
if ! ls /usr/lib/cni/dnsname 2>/dev/null && ! ls /usr/libexec/cni/dnsname 2>/dev/null; then
  info "WARNING: dnsname CNI plugin not found. Container DNS (auralynq-api, auralynq-qdrant …)"
  info "  may fail. Install: sudo apt install containernetworking-plugins"
  info "  Continuing anyway — will error if containers can't resolve peers by name."
fi

# ── 5. Start the stack ───────────────────────────────────────────────────────
info "Starting Podman stack (detached) …"
cd "$REPO"
podman-compose --env-file "$ENV_FILE" up -d

# ── 6. Wait for Caddy HTTPS ──────────────────────────────────────────────────
info "Waiting for Caddy HTTPS on :8443 …"
n=0
until curl -kfsS https://127.0.0.1:8443 -o /dev/null 2>/dev/null; do
  ((n++)); [[ $n -gt 60 ]] && die "Caddy did not come up after 60s — run: podman-compose logs caddy"
  sleep 2
done
ok "Caddy is up"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Auralynq (Podman) is ready"
echo ""
echo "  Chat UI:     https://172.24.50.21:8443"
echo "  ModelFit:    https://172.24.50.21:8443/modelfit"
echo "  API health:  https://172.24.50.21:8443/api/health"
echo "  API docs:    https://172.24.50.21:8443/api/docs"
echo ""
echo "  ⚠ Self-signed cert: click 'Advanced → Accept Risk' in your browser"
echo "    (Firefox) or 'Proceed anyway' (Chrome) on first visit."
echo ""
echo "  If documents need re-indexing (fresh Qdrant volume):"
echo "    → Go to https://172.24.50.21:8443  and use the Upload / Ingest UI"
echo ""
echo "  Logs:        podman-compose --env-file .env.podman logs -f"
echo "  Stop:        podman-compose --env-file .env.podman down"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
