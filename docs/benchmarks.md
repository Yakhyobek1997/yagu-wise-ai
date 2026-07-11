# Benchmarks

Every number under this page's targets is produced by running the command —
never hand-written, never copied from a prior run without regenerating it.
See `docs/evaluation.md` for `make eval` (retrieval/answer-quality); this
page covers the rest.

## Commands

| Command | What it measures | Requires | Report |
|---|---|---|---|
| `make bench` | Vector-index recall/latency/memory across quantization modes (none/scalar/binary) | Nothing — runs on whatever's indexed, in-process | `reports/bench_report.json` |
| `make bench-modelfit` | ModelFit Index rankings for *this machine's* hardware | Nothing — pure hardware probe + scoring formula, no network | `reports/modelfit_bench_report.json` |
| `make bench-visual-grounding` | Grounding resolution rates (`span`/`segment`/`page`/`unavailable`) over the golden set | Nothing — offline-safe | `reports/visual_grounding_report.json` |
| `make bench-rag` | RAG-quality benchmark: groundedness, citation coverage, abstention accuracy | A local Ollama server with the target model pulled — degrades to a report noting "not reachable" if absent, never fabricates numbers | `reports/rag_bench_report.json` |
| `make export-paper-tables` | Renders every report above into one Markdown file | Whichever reports already exist; missing ones are listed, not backfilled | `reports/paper_tables.md` |

```bash
make bench
make bench-modelfit                    # or: TASK=coding make bench-modelfit
make bench-visual-grounding
make bench-rag                         # or: MODEL=ollama:llama3.1:8b make bench-rag
make export-paper-tables
```

## Estimated vs. measured — always separated

Every ModelFit number carries an explicit `is_estimate`/`estimate_used` flag
(`auralynq/modelfit/scoring.py`, `resource_estimator.py`,
`benchmark_runner.py`) — a formula-based VRAM/speed estimate is never
presented the same way as a number that came from an actual timed run. The
same discipline extends to the RAG-quality benchmark
(`RAGBenchMetrics.is_measured`) and community-submitted results
(`auralynq/modelfit/community.py`, which additionally rejects implausible
submissions — `tok_per_sec > 10000` — and strips PII-shaped hardware fields
before accepting a result; see `docs/modelfit/community-contributions.md`).

## Report provenance

Every report — `eval_report.json` and all five above — embeds the same
`provenance` block: git commit, UTC timestamp, a full hardware summary, and
a short description of exactly which dataset produced it. See
`docs/evaluation.md`'s "Report shape" section for the exact fields. This is
what `make export-paper-tables` surfaces under each table so a reader can
tell *when*, on *what hardware*, and against *which commit* a number was
produced — not just what the number was.

## The published README numbers

The retrieval-comparison and quantization tables in the main `README.md`'s
Benchmarks section came from real `make eval` / `make bench` runs — if you
regenerate them on your own machine, expect different absolute numbers
(different hardware, different corpus state) but the same report shape and
the same provenance fields. If a number in a doc doesn't have a
`provenance` block backing it somewhere, don't trust it — flag it as a docs
bug.

## Offline / CI-safe subset

`make bench`, `make bench-modelfit`, and `make bench-visual-grounding` all
run with zero external services and zero paid keys — they're safe to run in
CI or a Hugging Face Space build. `make bench-rag` is the one exception
(needs a real local Ollama + model) and is not part of any CI gate; run it
manually when you want real RAG-quality numbers for a specific model.
