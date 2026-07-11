# Evaluation

`make eval` is the only source of the retrieval/answer-quality numbers that
appear anywhere in this repo's docs — nothing is hand-typed (see
`CONTRIBUTING.md`: "Never hand-write benchmark numbers").

## Running it

```bash
make eval                              # full run, writes reports/eval_report.json
auralynq eval --smoke                  # tiny 3-item run (what CI runs)
auralynq eval --report                 # same as `make eval`
```

Works fully offline at $0: with no embedding/LLM extras installed, it uses
the hash embedder and extractive answerer (ADR-0003) — the numbers will be
lower quality than a real provider, but the harness itself, the report
schema, and the drift check all still run and pass.

## What it measures

For a frozen golden question set (`auralynq/eval/datasets.py`, `--smoke`
uses the first 3 items):

- **Retrieval comparison** across `naive`, `hybrid`, and `pathrag`
  retrievers: `recall_at_k`, `precision_at_k`, `ndcg_at_10`, `mrr`,
  `latency_p50_ms`.
- **Agentic (full pipeline)**: the same retrieval metrics plus Ragas (or a
  proxy) faithfulness/answer-relevancy/context-precision scores, run through
  the actual `auralynq_rag` agent — not a bare retriever.
- **ASR**: word error rate against `data/golden/asr_refs.json`, when audio
  golden items exist.
- **Drift check**: compares `agentic_recall`, `agentic_faithfulness`, and
  `hybrid_ndcg` against `reports/golden_baseline.json`. The first run on a
  machine creates the baseline; subsequent runs flag `"status": "regressed"`
  if any of those three metrics drops by more than `DRIFT_TOLERANCE` (0.05)
  versus the stored baseline. This is a local regression trip-wire, not a
  cross-machine comparison — a baseline created on one machine/config isn't
  meaningful compared against a run on a different one.

## Report shape

Every report (`eval_report.json` and every `bench-*` report — see
`docs/benchmarks.md`) includes a `provenance` block
(`auralynq/eval/provenance.py`):

```json
{
  "provenance": {
    "git_commit": "…",
    "generated_at": "2026-07-01T20:38:42+00:00",
    "hardware": { "cpu": {...}, "ram_gb": ..., "gpus": [...], "best_backend": "..." },
    "dataset_version": "golden_qa.json n=5 (smoke=False)"
  }
}
```

`hardware` reuses the ModelFit hardware probe (`auralynq/modelfit/hardware.py`)
rather than duplicating detection logic — the same numbers you'd see from
`auralynq-modelfit hardware`.

## Where reports live

`reports/` is git-ignored except `.gitkeep`/`README.md` — every report is
regenerated locally, never committed. If you want to cite a number in a PR
or doc, regenerate it and quote the `provenance` block alongside it so
reviewers can reproduce it.

## CI

`.github/workflows/ci.yml` runs `python -m auralynq.cli eval --smoke` on
every push — this is a correctness gate (the harness runs end-to-end with no
keys or extras installed), not a quality gate. A green CI run says nothing
about answer quality; it says the pipeline didn't break.
