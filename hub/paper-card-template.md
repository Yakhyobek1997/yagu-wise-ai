# <Paper / contribution title>

A paper-page / summary card for an Auralynq research contribution
(Auralynq-RAG, Visual Source Grounding, the ModelFit Index, or CALoRA-RAG).
Keep it honest — this is a research platform, not a benchmark-topping claim.

- **Authors:** <names>
- **Status:** <preprint | under review | published | working draft>
- **Links:** <arXiv / PDF / project page / code>
- **Code:** <https://github.com/MHHamdan/Auralynq> (+ specific module paths)

## TL;DR

<Two or three sentences. What problem, what approach, what's actually shown.
Use "We position this as a reproducible open-source platform for studying …"
framing rather than "state of the art" unless you have benchmarked it.>

## Contribution

<What is genuinely new vs. an engineering integration of existing ideas.
Cite the prior work you build on (see `THIRD_PARTY.md`). Distinguish
implemented / experimental / planned, matching
`docs/research/research-contributions.md`.>

## Method

<Short description; link to the detailed writeup and the implementing code
paths, e.g. `auralynq/retrieval/pathrag/retriever.py`.>

## Results

> Only real, reproducible numbers. Generate with `make eval` / `make bench` /
> `make bench-*` and quote the provenance (commit + hardware + dataset). If a
> contribution isn't benchmarked against a baseline yet, say so — an honest
> "not yet benchmarked against X" is better than an unsupported claim.

| Setup | Metric | Value | Provenance |
|---|---|---|---|
| <config> | <metric> | <value> | commit `<sha>`, `<hardware>`, `<dataset>` |

## Reproducing

```bash
<exact commands, e.g. make demo-index && make eval && make export-paper-tables>
```

## Limitations

<Honest scope: what it does not show, what's laptop-scale, what needs a
larger study. Reuse the limitations from research-contributions.md.>

## Related work

<Named prior work you compare to or build on, with citations. If you claim
an improvement, it must be against a specific, cited baseline on a shared
dataset.>

## Citation

```bibtex
@misc{<key>,
  title  = {<title>},
  author = {<authors>},
  year   = {<year>},
  eprint = {<arxiv-id, if any>},
  url    = {https://github.com/MHHamdan/Auralynq}
}
```
