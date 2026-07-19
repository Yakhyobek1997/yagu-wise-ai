# Single-container image for a Hugging Face Space (Docker SDK).
#
# Spaces expose exactly one public port, but Auralynq's default topology is
# 7 containers behind a Caddy proxy (see containers/ and compose.yml). This
# image instead runs the API (FastAPI/uvicorn, loopback-only) and the web UI
# (Next.js standalone) as two processes in one container; Next.js itself
# proxies /api/* to the API process (see web/next.config.js's rewrites()),
# so no separate reverse proxy is needed.
#
# Build context must be the repository root:
#   podman build -f deploy/huggingface/Dockerfile -t auralynq-space .

FROM docker.io/library/node:20-slim AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web/ ./
# next.config.js's rewrites() resolves at `next build` time (baked into
# .next/routes-manifest.json), so AURALYNQ_INTERNAL_API_URL must be set here,
# not just in the runtime stage below — otherwise the /api proxy is silently
# empty and every API request 404s through the web server.
ENV NEXT_PUBLIC_API_BASE=/api \
    NEXT_TELEMETRY_DISABLED=1 \
    AURALYNQ_INTERNAL_API_URL=http://127.0.0.1:8000
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
    && apt-get install -y --no-install-recommends curl poppler-utils nodejs npm ffmpeg libsndfile1 espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# ---- API (light extras only — no torch/GPU stack; see pyproject.toml) ----
# `ingest` = PDF/DOCX parsing + page rendering for visual grounding. `llm` =
# the lightweight openai/anthropic/cohere HTTP SDKs (no torch, no langchain) —
# openai is required for the `huggingface` provider (HF Inference Providers via
# the OpenAI-compatible router). `eval` is deliberately excluded (ragas drags in
# langchain/langgraph and ~doubles image size; only `make eval`/`bench` need it).
COPY pyproject.toml README.md ./
COPY auralynq ./auralynq
RUN pip install -e ".[ingest,llm]"

# ---- Voice ASR (free, torch-free): faster-whisper (CTranslate2) + soundfile. ----
# The full `voice` extra pulls silero-vad (→torch, ~800MB) + librosa; we skip
# those and disable VAD/diarization (VAD is only in the live-mic path, not the
# uploaded-file path the web voice query uses). The Whisper model is baked into
# an image layer so voice works instantly + offline at runtime (no per-cold-start
# download on the free CPU tier).
ENV HF_HOME=/app/hfcache
# faster-whisper (ASR, small) + Kokoro (TTS, spoken replies). Install the
# CPU-only torch wheel first so kokoro doesn't drag in the ~2GB CUDA build.
# Prebake both models into image layers → voice is instant + offline at runtime.
RUN pip install "faster-whisper>=1.0" "soundfile>=0.12" \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install "kokoro>=0.9" \
    && mkdir -p /app/hfcache \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')" \
    && python -c "from kokoro import KPipeline; p=KPipeline(lang_code='a'); [c for _,_,c in p('warm up', voice='af_heart')]; [c for _,_,c in p('warm up', voice='am_michael')]"

# ---- Local generative LLM (free, in-container): llama-cpp-python + GGUF. ----
# Install a PREBUILT AVX2/FMA/F16C wheel (compiled in a matching python:3.11-slim
# and committed under wheels/). HF's build node can't finish a source compile in
# its time window, so we bring our own optimized binary — no toolchain in the
# image, no build timeout. Qwen2.5-3B-Instruct Q4_K_M (~2.1 GB) follows the
# "cite every claim with [n]" instruction far more reliably than 1.5B. Model
# baked in for offline runtime.
COPY wheels/llama_cpp_python-0.3.34-py3-none-linux_x86_64.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/llama_cpp_python-0.3.34-py3-none-linux_x86_64.whl \
    && rm -rf /tmp/wheels \
    && python -c "from huggingface_hub import hf_hub_download; hf_hub_download('Qwen/Qwen2.5-3B-Instruct-GGUF', 'qwen2.5-3b-instruct-q4_k_m.gguf')"

# ---- Ollama (GPU path): self-contained CUDA runtime, auto-detects the T4. ----
# The provider is `auto`: ollama (GPU) is preferred, with the CPU GGUF above as
# a fallback if the GPU/ollama is ever unavailable. Model baked into an image
# layer at OLLAMA_MODELS so runtime is offline. `ollama serve` is started by
# entrypoint.sh.
ENV OLLAMA_MODELS=/app/ollama_models
RUN curl -fsSL https://ollama.com/download/ollama-linux-amd64.tgz | tar -xz -C /usr/local \
    && mkdir -p /app/ollama_models \
    && bash -c 'OLLAMA_HOST=127.0.0.1:11434 ollama serve & SRV=$!; sleep 8; ollama pull qwen2.5:3b; kill "$SRV"'

COPY scripts ./scripts
COPY examples ./examples

# ---- Web (pre-built Next.js standalone output) ----
COPY --from=web-builder /web/.next/standalone ./web
COPY --from=web-builder /web/.next/static ./web/.next/static
COPY --from=web-builder /web/public ./web/public

COPY deploy/huggingface/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh \
    && useradd -m -u 10001 auralynq \
    && mkdir -p /data/auralynq \
    && chown -R auralynq:auralynq /app /data

LABEL org.opencontainers.image.title="auralynq-space" \
      org.opencontainers.image.description="Auralynq single-container image for Hugging Face Spaces" \
      org.opencontainers.image.source="https://github.com/MHHamdan/Auralynq" \
      org.opencontainers.image.licenses="Apache-2.0"

USER auralynq

# Safe-by-default posture for a public Space — see env.example for the full
# list and docs/getting-started/huggingface-space.md for the design notes.
# Every one of these can be overridden via Space Variables/Secrets.
# HF_HUB_OFFLINE: ASR/TTS models are baked into the image above — never let a
# runtime model load block on (rate-limited, unauthenticated) hub HEAD calls.
# A stalled load during a relaunch is exactly what "workload not healthy after
# 30 min" looks like on the free tier.
ENV HF_HUB_OFFLINE=1 \
    AURALYNQ_HF_SPACE=true \
    AURALYNQ_DEMO_MODE=true \
    AURALYNQ_PUBLIC_DEMO=true \
    AURALYNQ_ALLOW_UPLOADS=false \
    AURALYNQ_DATA_DIR=/data/auralynq \
    AURALYNQ_VECTOR__BACKEND=memory \
    AURALYNQ_EMBEDDING__PROVIDER=hash \
    AURALYNQ_LLM__PROVIDER=slm \
    AURALYNQ_LLM__SLM_REPO=Qwen/Qwen2.5-3B-Instruct-GGUF \
    AURALYNQ_LLM__SLM_FILENAME=qwen2.5-3b-instruct-q4_k_m.gguf \
    AURALYNQ_LLM__MAX_TOKENS=512 \
    AURALYNQ_VOICE__ASR_PROVIDER=faster_whisper \
    AURALYNQ_VOICE__ASR_MODEL=base.en \
    AURALYNQ_VOICE__VAD=false \
    AURALYNQ_VOICE__DIARIZE=false \
    AURALYNQ_VOICE__TTS_PROVIDER=kokoro \
    AURALYNQ_VOICE__TTS_VOICE=af_heart \
    AURALYNQ_VISUAL__ENABLED=true \
    AURALYNQ_SERVE__API_KEY= \
    AURALYNQ_INTERNAL_API_URL=http://127.0.0.1:8000 \
    NEXT_PUBLIC_API_BASE=/api \
    PORT=7860

EXPOSE 7860
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-7860}/api/health" || exit 1

CMD ["/app/entrypoint.sh"]
