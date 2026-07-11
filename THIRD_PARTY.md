# Third-Party Attributions

Auralynq is built on open components. This file attributes algorithms, papers,
datasets, models, and libraries, with license notes. All integrations are
optional extras except the lightweight core listed in `pyproject.toml`.

## Algorithms & papers

| Item | Reference | Use in Auralynq | Notes |
|------|-----------|-----------------|-------|
| **PathRAG** | Chen et al., *PathRAG: Pruning Graph-based Retrieval Augmented Generation with Relational Paths* (2025) | Graph retrieval under `auralynq/retrieval/pathrag/` | Clean-room implementation from the paper. Flow-based pruning, path reliability, path-to-text. No third-party code vendored. |
| Reciprocal Rank Fusion | Cormack et al., 2009 | `retrieval/hybrid/fusion.py` | Standard RRF. |
| Maximal Marginal Relevance | Carbonell & Goldstein, 1998 | `retrieval/hybrid/mmr.py` | De-duplication / diversity. |
| Lost in the Middle | Liu et al., 2023 | `retrieval/hybrid/reorder.py` | Context reordering to mitigate mid-context recall loss. |
| Late chunking | Günther et al. (Jina AI), 2024 | `ingest/chunking.py` | Late-chunking strategy where embeddings allow it. |

## Models (optional, downloaded on demand)

| Model | License | Role | Env to enable |
|-------|---------|------|---------------|
| `BAAI/bge-m3` | MIT | Dense+sparse multilingual embeddings | `pip install 'auralynq[embeddings]'` |
| `BAAI/bge-reranker-v2-m3` | Apache-2.0 | Cross-encoder reranking | `auralynq[embeddings]` |
| faster-whisper (CTranslate2 Whisper) | MIT / Whisper MIT | ASR | `auralynq[voice]` |
| WhisperX | BSD-4-Clause-ish (see repo) | Word alignment | `auralynq[voice]` |
| pyannote.audio | MIT (gated weights need `HUGGINGFACE_TOKEN`) | Diarization | `auralynq[voice]` + token |
| Silero VAD | MIT | Voice activity detection | `auralynq[voice]` |
| Kokoro-82M | Apache-2.0 | TTS | `auralynq[voice]` |

## Libraries

| Library | License | Role |
|---------|---------|------|
| Qdrant / qdrant-client | Apache-2.0 | Vector DB |
| LangGraph / LangChain-core | MIT | Agent orchestration (optional) |
| FastAPI / Starlette / Uvicorn | MIT / BSD | Serving |
| Pydantic / pydantic-settings | MIT | Typed models/config |
| NetworkX | BSD | Knowledge graph |
| structlog | MIT/Apache-2.0 | Structured logging |
| OpenTelemetry | Apache-2.0 | Tracing |
| Arize Phoenix | Elastic-2.0 | Local trace UI (optional) |
| Ragas | Apache-2.0 | RAG eval (optional) |
| jiwer | Apache-2.0 | WER/CER (optional) |
| Hugging Face `datasets` | Apache-2.0 | Dataset loading |
| Next.js / React | MIT | Web UI |
| Tailwind CSS | MIT | UI styling |
| MCP Python SDK | MIT | MCP server |

## Datasets (loaded via `scripts/download_data.py`)

| Dataset | License | Use |
|---------|---------|-----|
| HotpotQA | CC BY-SA 4.0 | Multi-hop QA eval |
| MuSiQue | CC BY 4.0 | Multi-hop QA eval |
| 2WikiMultiHopQA | Apache-2.0 | Multi-hop QA eval |
| MS MARCO (sample) | MIT-style (MS Research) | Passage retrieval eval |
| LibriSpeech (sample) | CC BY 4.0 | ASR / voice eval |
| Common Voice (sample) | CC0 | ASR eval (where access available) |
| FLEURS (sample) | CC BY 4.0 | Multilingual ASR eval |

> Dataset availability/licensing can change upstream. The downloader verifies
> access at runtime and skips gracefully with a clear message when a corpus is
> unavailable or gated, never requiring paid keys.
