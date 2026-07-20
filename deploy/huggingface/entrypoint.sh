#!/usr/bin/env bash
# Starts the API (loopback-only, background) and the Next.js web server
# (foreground, PID 1's direct child so it receives Space restart/stop signals
# correctly). Next.js proxies /api/* to the API process — see
# web/next.config.js and deploy/huggingface/Dockerfile.
set -euo pipefail

DATA_DIR="${AURALYNQ_DATA_DIR:-/data/auralynq}"
mkdir -p "$DATA_DIR"

# Local LLM server (Ollama) — self-contained, uses the GPU when the Space runs
# on GPU hardware and falls back to CPU otherwise. The model is baked into the
# image (OLLAMA_MODELS). If ollama isn't installed/serving, the app's provider
# resolution falls back to the local GGUF (slm) or extractive — never fatal.
if command -v ollama >/dev/null 2>&1; then
  OLLAMA_HOST=127.0.0.1:11434 ollama serve &
  OLLAMA_PID=$!
  trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT INT TERM
  echo "[entrypoint] waiting for ollama..."
  for _ in $(seq 1 40); do
    curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1 && { echo "[entrypoint] ollama ready"; break; }
    sleep 1
  done
fi

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

# Multiple workers: the /query endpoints are async but the LLM call to Ollama is
# a blocking HTTP call, which would freeze a single event loop (and the health
# check / proxy) for the duration. Extra workers keep the API responsive when one
# is busy generating. Ollama is a shared external process, so the model is loaded
# once regardless of worker count.
python -m uvicorn auralynq.serving.app:app --host 127.0.0.1 --port 8000 \
  --workers "${AURALYNQ_API_WORKERS:-2}" --timeout-keep-alive 75 &
API_PID=$!
trap 'kill "$API_PID" "${OLLAMA_PID:-}" 2>/dev/null || true' EXIT INT TERM

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
