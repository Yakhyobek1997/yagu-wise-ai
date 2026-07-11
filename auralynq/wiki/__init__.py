"""Compounding Wiki (Phase 1).

A persistent, LLM-synthesized knowledge layer built from the PathRAG knowledge
graph at ingest. Durable markdown entity pages sit above the chunk index and KG,
so synthesis is compiled once and kept current instead of re-derived every query.
Purely additive and gated behind ``AURALYNQ_WIKI__ENABLED`` (default off).
"""
