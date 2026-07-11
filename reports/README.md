# `reports/` — generated evaluation artifacts, not tracked

These files are produced by the evaluation/benchmark harness and are git-ignored
(only this README is tracked). The benchmark tables in the top-level `README.md`
are populated from them — never hand-written (ADR-0010).

```bash
make eval     # -> reports/eval_report.json + reports/golden_baseline.json
make bench    # -> reports/bench_report.json
```

| File | Produced by | Contents |
|------|-------------|----------|
| `eval_report.json` | `make eval` | retrieval metrics (naive/hybrid/PathRAG/agentic), Ragas (or proxy), ASR WER, drift check |
| `bench_report.json` | `make bench` | vector quantization recall/latency/memory trade-offs |
| `golden_baseline.json` | first `make eval` | frozen baseline for the drift check |

The numbers in `README.md` were measured in the fully-offline `$0` configuration
(hashing embeddings + extractive LLM). Install `auralynq[all]` and rerun for
real-model quality.
