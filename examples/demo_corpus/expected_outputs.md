# Demo corpus — expected outputs

The table below is **measured output**, not hand-written: it comes from one
actual run of `auralynq.agent.runner.answer_question()` (the same code path
`auralynq ask` and the CLI use) against exactly the three documents in
`examples/demo_corpus/docs/`, in Auralynq's fully-offline $0 configuration —
`AURALYNQ_VECTOR__BACKEND=memory`, `AURALYNQ_EMBEDDING__PROVIDER=hash`,
`AURALYNQ_LLM__PROVIDER=extractive` — the same configuration `make demo-data
&& make demo-index && make demo-query` reproduces from a clean clone with
zero paid keys. It was run in an isolated data directory, not against any
existing local corpus.

Re-run it yourself: `make demo-data && make demo-index && make demo-query`.

| ID | status | confidence | evidence_coverage | Cited source(s) |
|---|---|---:|---:|---|
| q1 | answered | 0.51 | 1.00 | `auralynq-overview.md`, `sample-benchmark-report.pdf` |
| q2 | answered | 0.47 | 0.75 | `auralynq-overview.md`, `visual-grounding-notes.txt` |
| q3 | answered | 0.42 | 0.60 | `sample-benchmark-report.pdf`, `auralynq-overview.md` |
| q4 | answered | 0.43 | 0.50 | `auralynq-overview.md` (strategy table chunk), `sample-benchmark-report.pdf` |
| q5 | answered | 0.50 | 0.875 | `sample-benchmark-report.pdf` **(page 1, real bounding box: `has_bbox: true`)**, `auralynq-overview.md` |
| q6 | answered | 0.47 | 0.40 | `auralynq-overview.md`, `sample-benchmark-report.pdf`, `visual-grounding-notes.txt` |
| q7 | answered | 0.46 | 0.455 | `auralynq-overview.md`, `visual-grounding-notes.txt` |
| q8 | answered | 0.49 | 0.667 | `sample-benchmark-report.pdf`, `auralynq-overview.md` |
| q9 | answered | 0.46 | 0.778 | `auralynq-overview.md`, `visual-grounding-notes.txt` |
| q10 | answered | 0.50 | 0.667 | `sample-benchmark-report.pdf` (both tables), `auralynq-overview.md` |
| q11 | answered | 0.48 | 0.667 | `visual-grounding-notes.txt`, `auralynq-overview.md` |

## What "correct" looks like per category

- **q1, q2, q9, q10 (factoid)** — the answer should quote or closely
  paraphrase the specific fact (e.g. q9's five weights: 30/20/25/15/10%),
  with a citation pointing at the document that actually contains it.
- **q3, q11 (summary)** — the answer should synthesize across more than one
  chunk of the cited document rather than quoting a single sentence.
- **q4 (citation verification)** — the cited chunk must contain the literal
  strategy comparison table; a correct system should not cite the PDF's
  benchmark table for this question even though both documents discuss
  "strategies."
- **q5 (visual grounding click-through)** — this is the one to click through
  in the UI. The real ingest run confirms
  `visual_grounding.has_bbox: true` with a concrete `normalized_bbox` for the
  PDF citation, so the Source Workspace should render an exact highlight box
  around the retrieval-comparison table, not a soft page-level highlight.
- **q7 (ModelFit command)** — a correct answer names
  `auralynq-modelfit recommend --task rag --limit 5` (or the equivalent
  `/api/modelfit/recommendations` call) and explains that its output is a
  ranked list of models with a 0–100 ModelFit score — it should **not**
  claim to already know which model is "best" for the reader's specific
  hardware, since that depends on the live hardware probe, not the corpus.
- **q8 (strategy comparison)** — a correct answer cross-references both the
  Markdown strategy table (`hybrid`/`auralynq_rag` marked Available) and the
  PDF's retrieval-comparison numbers (hybrid: nDCG@10 0.886; note the PDF
  table doesn't have a "PathRAG" *strategy* row by that exact name — it has
  a `PathRAG` *column* in the retrieval comparison — a good system should
  notice and not conflate the two).

## q6 — the insufficient-evidence case, honestly

q6 asks about something that does not exist anywhere in the corpus
(Auralynq has no "Q4 2025 revenue" — it's an open-source project, not a
company with quarterly earnings). **Measured behavior:** the offline
extractive fallback returned `status: answered` with `evidence_coverage:
0.40` and the lowest-signal confidence in this set (0.47, tied with q2) —
it did **not** hard-abstain (`insufficient_evidence`).

This matches the documented design in `auralynq-rag-contribution.md`'s
evidence-sufficiency stage: coverage below ~0.3 triggers a hard abstain,
0.3–0.6 is the "marginal" band (generate with a low-confidence warning), and
0.4 falls inside "marginal," not "insufficient." So this is the expected
*marginal-evidence* behavior for this exact question and configuration, not
a bug — but it's also not a demonstration of hard abstention. **Not verified
in this pass:** whether a real LLM provider (Ollama/OpenAI/Anthropic/Cohere)
triggers a hard `insufficient_evidence` abstain on this same question; that
would need a follow-up run with `AURALYNQ_LLM__PROVIDER` set to a real
provider and is a good manual check before citing this as "abstention
works" in any public-facing claim.

## Reproducing this table

```bash
make demo-data
make demo-index
make demo-query
```

`scripts/demo_query.py` reads `examples/demo_corpus/questions.json` and
prints `status`, `confidence`, `evidence_coverage`, and citations for every
question, in the same order as this table.
