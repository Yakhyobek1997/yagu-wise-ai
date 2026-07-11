#!/usr/bin/env bash
# Auralynq startup script
# Usage: ./start.sh
# Access: http://172.24.50.21:3001
#
# Port assignments (conflict-free on this server):
#   8000 — Auralynq API  (FastAPI / uvicorn)
#   3001 — Auralynq UI   (Next.js dev server)
# Already running on this server (do not touch):
#   3000 — Tadabbur frontend
#   8002 — Tadabbur backend API
#   5432 — PostgreSQL  |  6379 — Redis  |  8529 — ArangoDB

set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO/logs"
mkdir -p "$LOG_DIR"

# ── Helpers ────────────────────────────────────────────────────────────────────
die()  { echo "✗  $*" >&2; exit 1; }
info() { echo "→  $*"; }
ok()   { echo "✓  $*"; }

port_free() { ! ss -tlnp 2>/dev/null | grep -q ":$1 "; }
wait_up() {
  local url=$1 name=$2 n=0
  until curl -sf "$url" -o /dev/null 2>/dev/null; do
    ((n++)); [[ $n -gt 30 ]] && die "$name did not come up after 30s"
    sleep 1
  done
  ok "$name is up"
}

# ── 1. Activate venv ──────────────────────────────────────────────────────────
if [[ -f "$REPO/.venv/bin/activate" ]]; then
  source "$REPO/.venv/bin/activate"
  ok "venv activated"
else
  info "No .venv found — using system Python (run: python -m venv .venv && pip install -e '.[ingest,slm]')"
fi

# ── 2. Ollama ─────────────────────────────────────────────────────────────────
if ! curl -sf http://localhost:11434/api/version -o /dev/null 2>/dev/null; then
  info "Starting Ollama…"
  OLLAMA_HOST=127.0.0.1 ollama serve >> "$LOG_DIR/ollama.log" 2>&1 &
  wait_up http://localhost:11434/api/version "Ollama"
else
  ok "Ollama already running"
fi

# ── 3. Qdrant ─────────────────────────────────────────────────────────────────
if ! curl -sf http://localhost:6333 -o /dev/null 2>/dev/null; then
  info "Starting Qdrant…"
  QDRANT_STORAGE="$REPO/data/qdrant_storage"
  mkdir -p "$QDRANT_STORAGE"
  if command -v qdrant &>/dev/null; then
    qdrant --storage-path "$QDRANT_STORAGE" >> "$LOG_DIR/qdrant.log" 2>&1 &
  elif [[ -f /tmp/qdrant/qdrant ]]; then
    /tmp/qdrant/qdrant --storage-path "$QDRANT_STORAGE" >> "$LOG_DIR/qdrant.log" 2>&1 &
  else
    die "Qdrant binary not found. Run: ./scripts/download_qdrant.sh  or set AURALYNQ_VECTOR__BACKEND=chroma"
  fi
  wait_up http://localhost:6333 "Qdrant"
else
  ok "Qdrant already running"
fi

# ── 4. Auralynq API (port 8000) ───────────────────────────────────────────────
if port_free 8000; then
  info "Starting Auralynq API on :8000…"
  cd "$REPO"
  python -m uvicorn auralynq.serving:app \
    --host 0.0.0.0 --port 8000 \
    --log-level warning \
    >> "$LOG_DIR/api.log" 2>&1 &
  wait_up http://127.0.0.1:8000/health "Auralynq API"
else
  ok "Auralynq API already on :8000"
fi

# ── 5. Auralynq UI (port 3001) ────────────────────────────────────────────────
if port_free 3001; then
  info "Starting Auralynq UI on :3001…"
  cd "$REPO/web"
  npm run dev -- --port 3001 \
    >> "$LOG_DIR/web.log" 2>&1 &
  WEB_PID=$!
  info "Waiting for Next.js to compile (may take ~15s on first run)…"
  wait_up http://127.0.0.1:3001 "Auralynq UI"
else
  ok "Auralynq UI already on :3001"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Auralynq is ready"
echo ""
echo "  Chat:          http://172.24.50.21:3001"
echo "  ModelFit:      http://172.24.50.21:3001/modelfit"
echo "  API docs:      http://172.24.50.21:8000/docs"
echo "  API health:    http://172.24.50.21:8000/health"
echo ""
echo "  Logs:          $LOG_DIR/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
