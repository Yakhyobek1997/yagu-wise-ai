---
# Hugging Face dataset-card metadata. Replace every <placeholder>.
license: <spdx-id, e.g. cc0-1.0>       # MUST allow redistribution if you publish the data
tags:
  - auralynq
  - rag
  - retrieval
language:
  - <en, ...>
pretty_name: <Human-readable dataset name>
---

# <Dataset name>

<One-paragraph description: what this dataset is, what task it supports
(e.g. RAG eval, grounded document QA, abstention testing), and how it
relates to Auralynq.>

## Source & license

- **Source:** <where the documents/QA pairs come from>
- **License:** <spdx-id>. **Only publish data you have the right to
  redistribute.** If it derives from third-party documents, confirm their
  license permits this and attribute them.
- **Contains personal/private data?** <no | yes — if yes, do not publish, or
  document consent/anonymization>

## Structure

- **Rows:** <n>
- **Fields:** <e.g. `question`, `answer`, `supporting` (source ids),
  `type`>
- **Splits:** <train/val/test or single>

Example:
```json
<one representative row>
```

## Preprocessing

<Chunking strategy, normalization, how supporting-source labels were
assigned, dedup, etc.>

## Visual grounding metadata (if applicable)

If this dataset carries page-image / bounding-box grounding metadata for
Auralynq's Source Workspace, document it here:

- **Grounding fields:** <e.g. `page`, `normalized_bbox`, `block_type`>
- **How produced:** <pdfplumber/pymupdf layout extraction at what DPI>
- **Coverage:** <fraction of rows with `span` vs `page` vs `unavailable`
  grounding — reproduce with `make bench-visual-grounding`>

## Intended use

<What it's for: benchmarking retrieval, evaluating abstention, training a
grounding-aware model, a public demo corpus, etc.>

**Out of scope:** <what it should not be used for.>

## Limitations & biases

<Domain coverage, language coverage, size limits, any known label noise or
sampling bias. Be honest — small demo sets are fine, but say they're small.>

## Citation

```bibtex
@misc{<key>,
  title  = {<Dataset name>},
  author = {<you>},
  year   = {<year>},
  howpublished = {\url{https://huggingface.co/datasets/<org>/<name>}}
}
```
