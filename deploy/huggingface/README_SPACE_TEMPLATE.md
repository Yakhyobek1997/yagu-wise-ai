---
title: Auralynq
emoji: 🎙️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: "Local-first, voice-native, agentic RAG with visual citation grounding"
---

# Auralynq (demo Space)

This Space runs [Auralynq](https://github.com/MHHamdan/Auralynq), a
local-first, voice-native, agentic RAG platform, in its **lightweight
offline demo configuration**:

- Hash embeddings + in-memory vector store + extractive answering — no GPU,
  no model downloads, no paid API keys.
- Pre-loaded with the project's small, original, CC0-licensed
  [demo corpus](https://github.com/MHHamdan/Auralynq/tree/main/examples/demo_corpus)
  (three documents — no private or third-party data).
- Document uploads are **disabled by default** on this Space
  (`AURALYNQ_ALLOW_UPLOADS=false`) — you can browse and ask questions, but
  can't add your own files, so nothing you type gets stored beyond the
  current session.

## What data is stored, and for how long

- **This Space has no persistent storage attached.** Everything under
  `AURALYNQ_DATA_DIR` — the demo corpus's vector index, any chat history —
  is held in memory/container-local disk only and is **wiped on every
  restart or redeploy** of the Space. Nothing survives a rebuild.
- No analytics, no logging of your questions to a third party, no data sent
  anywhere except (if you've set an LLM key) to that provider's API.

## Try it

- Ask a question from
  [`examples/demo_corpus/expected_questions.md`](https://github.com/MHHamdan/Auralynq/blob/main/examples/demo_corpus/expected_questions.md).
- Click a citation to open the Source Workspace and see the exact
  bounding-box highlight in the sample PDF.
- Visit `/modelfit` to see the hardware-aware model-selection tool (numbers
  reflect this Space's container, not your own machine).

## Limitations of this demo

- Offline extractive answering verifies pipeline correctness, not answer
  quality — see the Limitations section in the main repo's `README.md`.
- CPU-only; ModelFit's speed/recommendation numbers reflect this container,
  not any GPU you may have.
- No uploads, no persistence, single small demo corpus.

## Duplicate this Space to make it your own

Click **"Duplicate this Space"** (top right). Duplicating copies the
Variables above but **not** Secrets — you'll start with the same safe
defaults. From there you can:

- **Enable uploads**: set `AURALYNQ_ALLOW_UPLOADS=true` as a Variable —
  understand first that a public, unauthenticated Space would let anyone
  upload documents that persist for as long as the container runs.
- **Add real model quality**: set `AURALYNQ_LLM__PROVIDER` and the matching
  key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`) as **Secrets**
  (never Variables).
- **Add persistent storage**: attach Hugging Face Persistent Storage and
  point `AURALYNQ_DATA_DIR` at the mounted path — read the storage-ownership
  caveat in
  [`deploy/huggingface/README.md`](https://github.com/MHHamdan/Auralynq/blob/main/deploy/huggingface/README.md)
  first; the container runs as a non-root user and the mount may need its
  ownership fixed on first boot.
- **Upgrade hardware**: this demo needs no GPU; only upgrade if you've also
  configured a real embedding/LLM provider that would benefit from it.

## Source

Full source, docs, and the no-Podman / Podman / server run modes:
<https://github.com/MHHamdan/Auralynq>. License: Apache-2.0 (code);
CC0-1.0 (this Space's demo corpus).
