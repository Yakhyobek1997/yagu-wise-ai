# Running Auralynq without Podman (local CLI/dev, $0)

This is the fastest way to try Auralynq: one Python virtualenv, no containers,
no GPU, no paid keys. Everything degrades to a deterministic offline fallback
(hash embeddings, in-memory vector store, extractive answering) so the golden
path always works, even with zero API keys installed.

## 1. Install

```bash
git clone https://github.com/MHHamdan/Auralynq.git && cd Auralynq
make setup      # uv venv (or python -m venv) + dev/ingest/eval deps
source .venv/bin/activate
```

`make setup` installs the light extras only (`dev,ingest,eval`) — no torch,
no GPU stack. See [`pyproject.toml`](../../pyproject.toml) for the full extras
list if you later want `embeddings`, `voice`, `agent`, or `llm` (commercial
provider SDKs).

## 2. Get sample data, index it, run the demo

```bash
make data       # download a small sample text/voice corpus (no paid keys)
make index      # build the vector index + knowledge graph from data/corpus
make demo       # ingest -> index -> ask, text + voice, end to end
```

Prefer a smaller, curated corpus with known-good demo questions instead?

```bash
make demo-data   # copy examples/demo_corpus/docs/ (original, CC0) into data/corpus/
make demo-index  # index it
make demo-query  # ask all 11 example questions, print grounded answers
```

See [`examples/demo_corpus/README.md`](../../examples/demo_corpus/README.md)
for what's in it and why — includes a PDF with real bounding-box visual
grounding, a citation-verification question, and one deliberately
out-of-corpus question.

## 3. Ask questions from the CLI

```bash
auralynq ask "How does PathRAG prune relational paths?"
auralynq ask "Summarize the corpus" --trace     # print the full agent trace
auralynq talk                                    # push-to-talk voice loop
```

## 4. Run the API and web UI as two plain processes

No compose file, no Caddy — just two dev servers talking over HTTP:

```bash
# Terminal 1 — API
python -m uvicorn auralynq.serving.app:app --host 0.0.0.0 --port 8000

# Terminal 2 — Web
cd web
NEXT_PUBLIC_API_BASE=http://localhost:8000/api npm run dev -- --hostname 0.0.0.0 --port 3000
```

Open **http://localhost:3000**. API docs are at **http://localhost:8000/docs**.

## 5. Upload documents

**From the UI:** the Ingest tab in the Agent Activity Rail — drag a PDF/DOCX/TXT/audio
file in.

**From the API:**
```bash
curl -X POST http://localhost:8000/ingest -F "file=@mydoc.pdf"
```

**From the CLI (bulk):**
```bash
auralynq ingest data/corpus --recursive
auralynq index --input data/corpus
```

## 6. Try different RAG strategies

```bash
curl http://localhost:8000/rag/strategies | python -m json.tool   # list all 13
curl -X POST http://localhost:8000/query \
  -H 'content-type: application/json' \
  -d '{"question": "What is Auralynq?", "rag_strategy": "hybrid"}'
```

Or use the **Algorithm Selector** in the composer bar in the web UI.

## 7. Visually verify a citation

Ask a question in the web UI, then click any numbered citation under the
answer — the **Source Workspace** opens full-screen with the original PDF
page, bounding-box overlays over the exact cited span, and claim-support
status (✅ Supported / ⚡ Partial).

## 8. ModelFit — pick a model for your hardware

```bash
auralynq-modelfit hardware                 # what you have (VRAM/RAM/backend)
auralynq-modelfit recommend --task rag --limit 5
auralynq-modelfit score --model ollama:llama3.1:8b --task rag
```
Or open **http://localhost:3000/modelfit**.

## 9. Run benchmarks

```bash
make eval     # Ragas + retrieval metrics + WER -> reports/
make bench    # Qdrant recall/latency/memory trade-offs -> reports/
```
Numbers only ever come from these commands, written to `reports/` with the
git commit, config, and timestamp — never hand-edited.

## Where your data lives (no-Podman mode)

Everything is under `./data/` in the repo you cloned:

| Path | Contents |
|---|---|
| `data/corpus/` | Ingested source documents |
| `data/index/`, `data/vectorstore/` | Vector index (in-memory store persists here if configured; otherwise it's process-lifetime only) |
| `data/page_cache/` | Rendered PDF page images for visual grounding |
| `data/storage/uploads/` | Transient upload staging (files are deleted after indexing; only embeddings are retained) |

`data/` is entirely git-ignored — nothing you ingest locally is ever committed.

## Clearing your data safely

Prefer the API's guarded clear flow (it requires typing a confirmation phrase
and returns a deletion report) over manually deleting folders:

```bash
curl -X POST http://localhost:8000/corpus/clear/preview
curl -X POST http://localhost:8000/corpus/clear/confirm \
  -H 'content-type: application/json' -d '{"phrase": "<phrase from preview>"}'
```

This clears the vector store, knowledge graph, page cache, and document
inventory together, so nothing goes stale.

## Next steps

- Multi-container / production-shaped stack → [podman.md](podman.md)
- Deploying to a remote machine → [server.md](server.md)
- Hugging Face Space → [huggingface-space.md](huggingface-space.md)
- Something not working → [troubleshooting.md](troubleshooting.md)
