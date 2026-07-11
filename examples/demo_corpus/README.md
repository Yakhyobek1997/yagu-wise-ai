# Auralynq Demo Corpus

A small, deliberately safe corpus for trying Auralynq end-to-end — locally,
in CI, or in a future Hugging Face Space — without needing any real
documents, paid API keys, or GPU.

## Contents

```
docs/
  auralynq-overview.md            # Markdown, includes a comparison table
  visual-grounding-notes.txt      # plain text
  sample-benchmark-report.pdf     # PDF with two real tables (visual grounding target)
questions.json                    # 11 demo questions (machine-readable)
expected_questions.md             # same questions, human-readable, with rationale
expected_outputs.md               # measured (not hand-written) reference outputs
license.md                        # CC0-1.0 — original content, safe to redistribute
```

All three documents were written from scratch for this project — see
[license.md](license.md). Nothing here is a real company's document, a
copyrighted third-party file, or private data.

## Why this corpus

- **Small enough to ship in the repo** (a few KB of text + a 3 KB PDF).
- **Supports visual grounding** — the PDF has real tables that
  `pdfplumber`/`pymupdf` extract with page images and bounding boxes, so
  citations into it resolve to an exact `span`, not just a page.
- **At least 10 demo questions** (11, covering factoid, summary, citation
  verification, visual-grounding click-through, insufficient-evidence,
  ModelFit command, and cross-document strategy comparison).
- **One deliberately unanswerable question** (q6) to exercise the
  evidence-sufficiency / confidence signals honestly — see the caveat in
  [expected_outputs.md](expected_outputs.md#q6--the-insufficient-evidence-case-honestly).

## Quickstart

```bash
make demo-data      # copy docs/ into data/corpus/
make demo-index     # build the vector index + knowledge graph
make demo-query      # ask every question in questions.json, print grounded answers
```

This runs in the fully-offline $0 configuration by default (hash embeddings,
in-memory vector store, extractive LLM) — no keys, no GPU, no downloads.
Install `auralynq[embeddings]` and/or set a real `AURALYNQ_LLM__PROVIDER`
for higher-quality answers over the same corpus.

To try it through the web UI instead: run `make demo-data && make demo-index`,
then start the API/web dev servers as in
[docs/getting-started/no-podman.md](../../docs/getting-started/no-podman.md),
upload nothing (the corpus is already indexed), and ask the questions from
[expected_questions.md](expected_questions.md) directly in chat.
