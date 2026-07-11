#!/usr/bin/env bash
# Starts the API (loopback-only, background) and the Next.js web server
# (foreground, PID 1's direct child so it receives Space restart/stop signals
# correctly). Next.js proxies /api/* to the API process — see
# web/next.config.js and deploy/huggingface/Dockerfile.
set -euo pipefail

DATA_DIR="${AURALYNQ_DATA_DIR:-/data/auralynq}"
mkdir -p "$DATA_DIR"

# Demo mode: seed and index the public demo corpus on first boot only, so a
# Space restart doesn't re-index for no reason. Never touches an existing
# index. Safe to skip entirely if AURALYNQ_DEMO_MODE=false.
if [ "${AURALYNQ_DEMO_MODE:-false}" = "true" ] && [ ! -f "$DATA_DIR/index/last_ingested.json" ]; then
  echo "[entrypoint] demo mode: seeding the public demo corpus (examples/demo_corpus/docs)"
  mkdir -p "$DATA_DIR/corpus"
  cp -r /app/examples/demo_corpus/docs/. "$DATA_DIR/corpus/"
  python -m auralynq.cli index --input "$DATA_DIR/corpus" \
    || echo "[entrypoint] demo indexing failed; continuing without a pre-built index"
fi

python -m uvicorn auralynq.serving.app:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

echo "[entrypoint] waiting for the API to become healthy..."
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "[entrypoint] API is healthy"
    break
  fi
  sleep 1
done

cd /app/web
exec node server.js
