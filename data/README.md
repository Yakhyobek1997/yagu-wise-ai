# `data/` — generated, not tracked

This directory holds datasets, the built index, and the knowledge graph. All of
it is **generated** and git-ignored (only this README is tracked). Recreate it:

```bash
make data     # download sample text + voice corpora (synthetic $0 fallback always)
make index    # build the hybrid vector index + knowledge graph
```

Layout after `make data && make index`:

```
data/
  corpus/        curated synthetic + audio sources (ingested by default)
  corpus_hf/     optional Hugging Face multi-hop QA docs (HotpotQA/MuSiQue/2Wiki)
  golden/        golden_qa.json (frozen eval set), asr_refs.json
  manifests/     dataset_manifest.json (provenance + checksums)
  index/         persisted MemoryStore vectors + graph.json (+ ingest manifest)
  storage/       uploads, TTS output, transient audio
```

Nothing here requires paid keys. `HUGGINGFACE_TOKEN` is only needed for gated
assets (e.g. pyannote diarization weights).
