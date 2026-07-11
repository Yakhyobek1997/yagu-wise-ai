# Demo corpus — expected questions

Eleven questions covering the required demo categories, run against
`examples/demo_corpus/docs/` (three files: one Markdown, one plain-text, one
PDF). Machine-readable form: [`questions.json`](questions.json).

| ID | Category | Question |
|---|---|---|
| q1 | factoid | What is Auralynq? |
| q2 | factoid | What does the 'span' grounding stage mean? |
| q3 | summary | Summarize how Auralynq's retrieval architecture works. |
| q4 | citation verification | Which RAG strategies are listed as Available in the strategy comparison table? |
| q5 | **visual grounding click-through** | According to the sample benchmark report, what is the nDCG@10 for the hybrid strategy? |
| q6 | **insufficient evidence** | What was Auralynq's total revenue in Q4 2025? |
| q7 | **ModelFit recommendation command** | Which CLI command recommends the best local model for a RAG task, and what does it print? |
| q8 | **strategy comparison** | Compare the hybrid and PathRAG rows in both the strategy table and the benchmark report. |
| q9 | factoid | What five sub-scores make up the composite ModelFit score, and what are their weights? |
| q10 | factoid | In the sample benchmark report, which quantization level gives the best memory compression, and what recall does it trade off to get there? |
| q11 | summary | In two sentences, what does the Source Workspace let a user do? |

**q5 (visual grounding)** is deliberately answered only by
`sample-benchmark-report.pdf` — clicking its citation should open the Source
Workspace with a real bounding-box overlay over the retrieval-comparison
table (confirmed: the ingest pipeline resolves `has_bbox: true` with a real
`normalized_bbox` for this PDF's chunks).

**q6 (insufficient evidence)** asks about something not present anywhere in
the corpus. See [expected_outputs.md](expected_outputs.md) for the honest,
measured behavior of the offline fallback on this question — it is a useful
illustration of the confidence/coverage signals, not a demonstration of hard
abstention (see caveat there).

**q7 (ModelFit command)** exercises the CLI rather than the corpus:

```bash
auralynq-modelfit recommend --task rag --limit 5
```

is the command; the corpus documents ModelFit's composite scoring formula so
a RAG answer can explain *what* the command's output means, even though the
live hardware ranking itself comes from the CLI, not from retrieval.

## Running these yourself

```bash
make demo-data      # copy examples/demo_corpus/docs/ into data/corpus/
make demo-index     # build the vector index + knowledge graph
make demo-query      # run every question in questions.json end-to-end
```
