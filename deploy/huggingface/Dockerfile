# Single-container image for a Hugging Face Space (Docker SDK).
#
# Spaces expose exactly one public port, but YaguWiseAi's default topology is
# 7 containers behind a Caddy proxy (see containers/ and compose.yml). This
# image instead runs the API (FastAPI/uvicorn, loopback-only) and the web UI
# (Next.js standalone) as two processes in one container; Next.js itself
# proxies /api/* to the API process (see web/next.config.js's rewrites()),
# so no separate reverse proxy is needed.
#
# Build context must be the repository root:
#   podman build -f deploy/huggingface/Dockerfile -t yaguwiseai-space .

FROM docker.io/library/node:20-slim AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web/ ./
# next.config.js's rewrites() resolves at `next build` time (baked into
# .next/routes-manifest.json), so YAGUWISEAI_INTERNAL_API_URL must be set here,
# not just in the runtime stage below — otherwise the /api proxy is silently
# empty and every API request 404s through the web server.
ENV NEXT_PUBLIC_API_BASE=/api \
    NEXT_TELEMETRY_DISABLED=1 \
    YAGUWISEAI_INTERNAL_API_URL=http://127.0.0.1:8000
RUN npm run build

FROM docker.io/library/python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# poppler-utils: PDF page rendering for visual grounding. nodejs/npm: runtime
# only for the pre-built Next.js standalone server (no build tools needed
# here — the build already happened in the web-builder stage).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl poppler-utils nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# ---- API (light extras only — no torch/GPU stack; see pyproject.toml) ----
# Only `ingest` (PDF/DOCX parsing + page rendering for visual grounding) is
# needed to serve the demo — `eval` pulls in ragas, which transitively drags
# in langchain/langgraph/openai and roughly doubles image size, but is only
# used by `make eval`/`make bench`, neither of which this Space runs.
COPY pyproject.toml README.md ./
COPY yaguwiseai ./yaguwiseai
RUN pip install -e ".[ingest]"
COPY scripts ./scripts
COPY examples ./examples

# ---- Web (pre-built Next.js standalone output) ----
COPY --from=web-builder /web/.next/standalone ./web
COPY --from=web-builder /web/.next/static ./web/.next/static
COPY --from=web-builder /web/public ./web/public

COPY deploy/huggingface/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh \
    && useradd -m -u 10001 yaguwiseai \
    && mkdir -p /data/yaguwiseai \
    && chown -R yaguwiseai:yaguwiseai /app /data

LABEL org.opencontainers.image.title="yaguwiseai-space" \
      org.opencontainers.image.description="YaguWiseAi single-container image for Hugging Face Spaces" \
      org.opencontainers.image.source="https://github.com/MHHamdan/YaguWiseAi" \
      org.opencontainers.image.licenses="Apache-2.0"

USER yaguwiseai

# Safe-by-default posture for a public Space — see env.example for the full
# list and docs/getting-started/huggingface-space.md for the design notes.
# Every one of these can be overridden via Space Variables/Secrets.
ENV YAGUWISEAI_HF_SPACE=true \
    YAGUWISEAI_DEMO_MODE=true \
    YAGUWISEAI_PUBLIC_DEMO=true \
    YAGUWISEAI_ALLOW_UPLOADS=false \
    YAGUWISEAI_DATA_DIR=/data/yaguwiseai \
    YAGUWISEAI_VECTOR__BACKEND=memory \
    YAGUWISEAI_EMBEDDING__PROVIDER=hash \
    YAGUWISEAI_LLM__PROVIDER=extractive \
    YAGUWISEAI_VISUAL__ENABLED=true \
    YAGUWISEAI_SERVE__API_KEY= \
    YAGUWISEAI_INTERNAL_API_URL=http://127.0.0.1:8000 \
    NEXT_PUBLIC_API_BASE=/api \
    PORT=7860

EXPOSE 7860
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-7860}/api/health" || exit 1

CMD ["/app/entrypoint.sh"]
