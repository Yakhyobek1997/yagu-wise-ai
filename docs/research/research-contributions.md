# Auralynq Research Contributions

This page describes what Auralynq actually implements, what's experimental,
and what's roadmap — grounded in the code, not aspiration. We position
Auralynq as a **reproducible, open-source research platform for studying**
adaptive RAG routing, visual source grounding, and hardware-aware local
model selection, not as a benchmark-topping product. Where we cite prior
work, it's to place a design decision in context, not to claim priority over
it. We don't use "state of the art" anywhere on this page — none of these
components have been benchmarked against published baselines on a shared
dataset, and until that exists the phrase would be a claim we can't back up.

Every code reference below was checked against the current source tree while
writing this page (paths and function names, not just prose).

---

## 1. Auralynq-RAG — adaptive, observable, calibrated RAG

### Motivation

Most RAG systems retrieve, generate, and present an answer with no visible
signal about *why* that answer was produced or how much to trust it. Our
starting premise: a RAG pipeline that can't explain its own trace, and can't
tell you when its evidence was weak, isn't trustworthy enough to build on.

### Implemented now

- **Adaptive strategy routing** — a pluggable registry
  (`auralynq/rag/strategy_registry.py`) dispatches to 13 named strategies;
  4 are production-ready (`auralynq_rag`, `hybrid`, `naive_vector`,
  `keyword_bm25`).
- **PPR-augmented PathRAG** — `auralynq/retrieval/pathrag/retriever.py`'s
  `_assign_ppr()` runs `networkx.pagerank()` with a personalization vector
  seeded on query entities (α = 0.15 teleport); `_apply_ppr()` blends that
  authority score against flow-based path pruning
  (`0.4 · flow_score + 0.6 · ppr_authority`) to correct the short-path bias
  that plain resource-decay PathRAG exhibits. This blend is our own design
  choice, explicitly inspired by the authority-propagation idea in HippoRAG2
  (Gutierrez et al., NeurIPS 2024) — we did not reimplement HippoRAG2 itself.
- **Dual-signal evidence sufficiency critic** — `auralynq/agent/nodes.py`'s
  `_semantic_coverage()` requires *both* lexical coverage (<60% key-term
  overlap) **and** semantic coverage (cosine(query, context) < 0.5) to fall
  below threshold before triggering a query rewrite (capped at 3 retries).
  Motivated by the observation that vocabulary mismatch alone (e.g.
  "photosynthesis" vs. "light-dependent reactions") shouldn't force a
  rewrite when the semantics already line up.
- **Calibrated four-signal confidence** — `node_self_check` computes
  `0.30·score_quality + 0.30·citation_coverage + 0.25·semantic_coverage +
  0.15·token_coverage`, each signal individually visible in the API response
  and the UI's confidence bar, rather than one opaque number.
- **Citation validation** — every citation is checked against the chunk it
  claims to cite before being surfaced (see Visual Source Grounding, below,
  for how far this goes).
- **Trace-first observability** — every query builds a structured trace (one
  span per pipeline step) returned in the API response and rendered in the
  UI's Trace panel; optional export to Phoenix (local OTLP) or Langfuse
  (hosted).

### Experimental

- `self_rag`, `crag`, `adaptive_rag` strategies exist in the registry and
  are selectable in the UI (flagged "Experimental" with a speed warning) but
  haven't been evaluated to the same bar as the 4 available strategies.

### Planned

- `graph_rag`, `raptor`, `lightrag-{local,global,hybrid}`, `hipporag` are
  registered as placeholders requiring infrastructure (graph index, entity
  counts, reranker) not all deployments have — see the strategy registry's
  "Planned" group.

### How to run it

```bash
auralynq ask "your question" --trace           # CLI, full trace
curl -X POST http://localhost:8000/query -d '{"question": "...", "rag_strategy": "hybrid"}'
curl http://localhost:8000/rag/strategies       # list all 13 + availability
```

### What metrics evaluate it

`make eval` runs the offline evaluation harness (Ragas proxy metrics +
retrieval metrics + WER) against a frozen golden set and writes to
`reports/`. The retrieval-comparison and answer-quality numbers in the main
`README.md`'s Benchmarks section came from exactly this command — we don't
hand-write benchmark tables (see `DECISIONS.md` ADR log and
`scripts/name_audit.py`/CI's `--smoke` eval gate for how that's enforced).

### Limitations

- The offline fallback path (hash embeddings, in-memory store, extractive
  LLM) verifies pipeline *correctness*, not answer *quality* — we verified
  this directly while building the [demo corpus](../../examples/demo_corpus/):
  a genuinely out-of-corpus question landed in the "marginal evidence" band
  (coverage 0.4) rather than triggering a hard abstain in that
  configuration, which is expected per the documented thresholds but is
  worth knowing before assuming abstention "just works" end-to-end. Whether
  a real LLM provider abstains more reliably on the same question has not
  been verified in this pass.
- No published head-to-head comparison against other open-source RAG
  frameworks exists yet; the "4 research claims" in the fuller internal
  design notes (evidence sufficiency reduces hallucination, calibration is
  well-behaved, etc.) are stated as claims to test, not results.
- The knowledge graph is NetworkX + JSON — laptop-scale, not built for a
  large multi-tenant corpus.

---

## 2. Visual Source Grounding

### Motivation

A citation that just names a document isn't independently verifiable by a
reader in under a few seconds. The goal here is: click a citation, see the
exact region of the exact page it came from, with a support-status label —
without re-running anything.

### Implemented now

- **Citation → page → span mapping** — at ingest, `pdfplumber`/`pymupdf`
  extract layout blocks with bounding boxes per chunk; `pdf2image` renders a
  page image. At query time, `auralynq/grounding/resolver.py`'s
  `GroundingResolver.resolve()` maps each citation to one of four states:
  `span` (exact bounding box), `segment` (audio timestamp interval, for
  WAV/MP3/M4A chunks), `page` (page known, no exact box), or `unavailable`
  (needs reindex). Confirmed by running `scripts/bench_visual_grounding.py`
  against the golden set, which mixes text and one audio document — its real
  output was `{"unavailable": 7, "segment": 2}` for that specific corpus, not
  hand-typed.
- **Bounding-box overlays** — verified directly: ingesting the demo corpus's
  sample PDF produces citations with `has_bbox: true` and a concrete
  `normalized_bbox` (e.g. `[0.127, 0.080, 0.872, 0.222]`), which the frontend
  renders as a `%`-based CSS overlay that stays aligned at any zoom level
  (`components/SourceWorkspaceModal.tsx`).
- **Source Workspace** — a full-screen three-panel view (citations, PDF
  viewer with zoom presets, evidence panel) opened on citation click.
- **Claim support status** — citations are labeled "Supported" or "Partial"
  depending on whether they back the full claim or only part of it.

### Experimental

- ColPali-style visual retrieval (image-to-image semantic search over page
  images, `AURALYNQ_VISUAL__VISUAL_RETRIEVAL_ENABLED=true`) exists as a
  gated, off-by-default code path.

### Planned

- A page-thumbnail rail in the Source Workspace.
- A dedicated layout-block store (today, layout blocks live per-chunk inside
  the vector store payload; the `/pages/{n}/layout` endpoint does a bounded
  scroll query, which is fine at demo scale but not designed for very large
  documents).

### How to run it

Ask a question through the web UI, click a numbered citation. Or hit the
endpoints directly:

```bash
curl http://localhost:8000/documents/{doc_id}/grounding-status
curl http://localhost:8000/documents/{doc_id}/pages/1/layout
curl http://localhost:8000/corpus/grounding-summary
```

The [demo corpus](../../examples/demo_corpus/) includes one PDF specifically
so this is exercisable with zero setup — see `expected_outputs.md`'s q5.

### What metrics evaluate it

There is no standalone "visual grounding accuracy" benchmark yet; today the
practical check is binary (does a citation resolve `span`/`page` vs.
`unavailable`) and is exercised in `tests/test_visual_grounding.py` and
`tests/test_source_workspace.py`, plus the manual demo-corpus walkthrough
above.

### Limitations

- Bounding boxes come from the PDF's text layer via `pdfplumber`; scanned
  (image-only) PDFs without OCR won't produce spans — only `page`-level
  grounding, or `unavailable` if rendering also fails.
- No formal evaluation of grounding *precision* (does the highlighted region
  actually contain the cited claim, vs. just the right page) exists yet —
  this is a natural next research question, not yet answered.

---

## 3. Auralynq ModelFit Index

### Motivation

Choosing a local model for RAG today means: find a model on Hugging Face or
Ollama, guess VRAM needs, load it, run out of memory, retry at a lower
quantization, and test quality with no reproducible metric — repeated per
candidate model. ModelFit tries to make that a single, reproducible,
in-platform step.

### Implemented now

- **Hardware-aware scoring** — `auralynq/modelfit/hardware.py` probes CPU,
  RAM, GPU/VRAM, backend (CUDA/Metal/ROCm/CPU), and Ollama availability;
  verified live (not just in tests) by hitting `GET /api/modelfit/hardware`
  in both a bare-metal run and inside the Hugging Face Space container built
  for this release — both returned real OS/CPU/RAM values for their
  respective environment.
- **Composite ModelFit score** (`auralynq/modelfit/scoring.py`) —
  `hw·0.30 + speed·0.20 + rag·0.25 + task·0.15 + deploy·0.10`, with a
  documented capability-utilization adjustment on ≥32GB VRAM hardware so a
  tiny model doesn't win by default just because it's fast.
- **Estimated vs. measured separation** — every number carries an explicit
  `is_estimate`/`is_measured` flag (`scoring.py`, `benchmark_runner.py`,
  `rag_bench.py`); nothing is silently presented as measured when it's a
  formula-based estimate.
- **RAG-quality benchmarking** — `auralynq/modelfit/rag_bench.py` measures
  groundedness (lexical overlap between answer and retrieved context),
  citation coverage (fraction of citations that reference actually-retrieved
  passages), and abstention accuracy, over a small fixed prompt set.
- **Quantization recommendation** — `recommend_quantization()` (used in
  `scoring.py`'s `score_model()`) picks a quantization level given the
  hardware profile; this is a deterministic, formula-based recommendation,
  not a learned model.
- **Community benchmark validation** — `auralynq/modelfit/community.py`
  rejects implausible submissions (`tok_per_sec > 10000`) and strips
  PII-shaped hardware fields (`serial`, `uuid`, `mac_address`, `hostname`,
  `username`) before accepting a community-submitted result; see
  `docs/modelfit/community-contributions.md`.
- **Safety constraints, enforced in code, not just policy**: no model is
  ever downloaded automatically; a benchmark run requires an explicit
  `confirmed=true` after a dry-run preview is shown.

### Experimental

- The RAG-quality benchmark's groundedness metric is a simple lexical-overlap
  heuristic (`_simple_groundedness` in `rag_bench.py`), not an LLM-judged or
  embedding-based faithfulness score — treat it as a coarse signal, not a
  precise one.

### Planned

- A community-index web UI to submit/browse verified benchmark results
  (today, submission/validation exists in code; there's no browsing UI yet).

### How to run it

```bash
auralynq-modelfit hardware
auralynq-modelfit recommend --task rag --limit 5
auralynq-modelfit score --model ollama:llama3.1:8b --task rag
auralynq-modelfit benchmark --model llama3.1:8b --task rag --examples 5 --dry-run
```
Or `/modelfit` in the web UI (6 tabs: Hardware, Models, Recommended, Score
Cards, Benchmark Lab, Comparison).

### What metrics evaluate it

`make bench` (Qdrant recall/latency/memory across quantization modes) and
the RAG-quality benchmark above, both writing to `reports/`. The example
ranking table in the main README (llama3.1:14b scoring 95 on a 44GB CUDA
box, etc.) is a real output of the scorer on that hardware profile, not a
hypothetical.

### Limitations

- The Ollama and Hugging Face catalogs are curated lists (14 static + live
  Ollama API, 8 curated HF models) — not an exhaustive or auto-updating
  index of every available local model.
- Speed estimates for un-benchmarked models come from a 5-tier VRAM
  bandwidth table, which is a coarse approximation until an actual benchmark
  run replaces it with a measured number.

---

## 4. Auralynq-CALoRA-RAG — roadmap, not implemented

### Motivation

Local RAG deployment is really a joint selection problem across five
things: base model, quantization, an optional LoRA/QLoRA adapter, a RAG
strategy compatible with the resulting context length, and an embedding
model that fits in the remaining memory budget. No component in Auralynq
today optimizes across all five jointly.

### Status: **not implemented.** This is a research-track name and problem
formalization, not shipped functionality.

The only trace of this in the codebase today is a boolean
`supports_adapters` metadata flag on catalog entries
(`auralynq/modelfit/model_metadata.py`) — there is no LoRA/QLoRA training,
adapter loading, or adapter-aware RAG strategy selection anywhere in
`auralynq/`. We verified this directly (`grep -rl` across the package for
LoRA/adapter code turns up only that one metadata field).

### What's planned

- A memory-budget decomposition (`VRAM_base + VRAM_adapter + VRAM_kvcache +
  VRAM_embedding + overhead`) extending ModelFit's existing VRAM estimator.
- Adapter-aware RAG strategy routing — matching a RAG strategy's context
  requirements against what a given (model, quantization, adapter) triple
  can actually support.
- Citation/abstention/grounding-aware adaptation — using the confidence and
  citation-coverage signals from Auralynq-RAG (§1) as a fine-tuning signal,
  not just a serving-time signal.

### How to run it

Not runnable yet. There is no CLI command, API endpoint, or UI surface for
this.

### What metrics would evaluate it

Not defined yet, beyond reusing Auralynq-RAG's existing citation-coverage,
groundedness, and abstention-accuracy metrics as the target the adaptation
would need to move.

### Limitations

Everything here is a problem statement, not a result. Treat any specific
numbers that might appear in future internal design notes about this track
as illustrative until real training/eval code exists and is checked in.

---

## Related-work posture

Where a component above cites prior work (PathRAG, HippoRAG2, Corrective
RAG, Self-RAG, RAGAS, RRF, MMR, Lost-in-the-Middle, late chunking — full list
in `THIRD_PARTY.md`), that citation is there to show we're building on a
named idea, not claiming to have originated it. If you're aware of directly
comparable work we should cite or benchmark against, that's a welcome
contribution — see `CONTRIBUTING.md`.
