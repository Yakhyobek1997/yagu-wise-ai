# Auralynq Platform Overview (Sample Corpus Document)

*This document was written for Auralynq's public demo corpus. It is an
original summary of the platform, not third-party material.*

## What is Auralynq?

Auralynq is a local-first, voice-native, agentic retrieval-augmented
generation (RAG) platform. It accepts text or voice questions against a
private document collection and returns grounded, cited answers. Every
citation can be visually verified against the exact page and text span it
came from, and every pipeline step is exposed in a live trace so a user can
see why the system answered the way it did.

## Retrieval architecture

A query enters an adaptive pipeline: intent classification, complexity
classification, retrieval-plan selection, retrieval, evidence-sufficiency
evaluation, generation, citation validation, and confidence scoring. Two
retrieval paths feed the same fusion stage:

- **Hybrid retrieval** — dense embeddings plus sparse (keyword) search,
  combined with Reciprocal Rank Fusion and de-duplicated with Maximal
  Marginal Relevance.
- **PathRAG graph retrieval** — path expansion over a knowledge graph, with
  Personalised PageRank (PPR) blended against flow-based path pruning to
  reduce short-path bias.

The default strategy, `auralynq_rag`, routes between these two paths (or
combines them) based on query complexity, and can rewrite the query up to
three times if a dual-signal evidence critic finds both lexical *and*
semantic coverage too low.

### RAG strategy comparison (sample)

| Strategy | Status | Speed |
|---|---|---|
| auralynq_rag | Available | Fast |
| hybrid | Available | Fast |
| naive_vector | Available | Fast |
| keyword_bm25 | Available | Fast |
| self_rag | Experimental | Medium |
| crag | Experimental | Slow |
| adaptive_rag | Experimental | Slow |
| graph_rag | Planned | — |
| raptor | Planned | — |

## Visual source grounding

At ingest time, Auralynq extracts layout blocks with bounding boxes from
each page and renders a page image. At query time, every citation resolves
to one of three grounding stages — `span` (exact bounding box), `page`
(page known, no exact span), or `unavailable` (document needs reindexing).
Clicking a citation opens the Source Workspace: the original page on one
side, the exact highlighted region, and the extracted evidence text on the
other.

## Auralynq ModelFit Index

The ModelFit Index scores candidate local models against the user's actual
hardware (VRAM, RAM, backend) rather than ranking them by benchmark accuracy
alone. The composite ModelFit score combines five weighted sub-scores:
hardware fit (30%), speed fit (20%), RAG fit (25%), task fit (15%), and
deployment fit (10%). No model is ever downloaded automatically, and every
benchmark run requires explicit user confirmation after a dry-run preview.
