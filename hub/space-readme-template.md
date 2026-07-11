---
# Hugging Face Space metadata (front-matter of the Space's README.md).
title: <Space title>
emoji: 🎙️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: <one line, <60 chars>
---

# <Space title>

> A **ready-to-copy, already-filled** version of this template lives at
> [`deploy/huggingface/README_SPACE_TEMPLATE.md`](https://github.com/MHHamdan/Auralynq/blob/main/deploy/huggingface/README_SPACE_TEMPLATE.md),
> alongside the Dockerfile, entrypoint, and env reference. Prefer that one for
> the standard Auralynq demo Space; use this generic template only if you're
> building a customized Space and want the section skeleton.

<One paragraph: what this Space demonstrates and who it's for.>

## What this demo does

<Concrete capabilities a visitor can try: chat, citations, visual grounding
click-through, ModelFit page, etc.>

## What data is stored, and for how long

- **Persistence:** <ephemeral (wiped on restart) | persistent `/data`
  attached>. Be explicit — a public Space with no persistent storage loses
  everything on restart.
- **Uploads:** <disabled | enabled>. If enabled on a public Space, warn that
  anyone can add documents others can query, and that they persist only as
  long as the container runs (unless persistent storage is attached).
- **Third parties:** <none | which provider APIs receive data if keys are set>

## Configuration — Variables vs. Secrets

- **Variables** (visible in Space settings): `AURALYNQ_DEMO_MODE`,
  `AURALYNQ_ALLOW_UPLOADS`, `NEXT_PUBLIC_API_BASE`, … — never a key/token.
- **Secrets** (encrypted): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `COHERE_API_KEY`, `AURALYNQ_SERVE__API_KEY`, `HUGGINGFACE_TOKEN`.

Full list with safe defaults:
[`deploy/huggingface/env.example`](https://github.com/MHHamdan/Auralynq/blob/main/deploy/huggingface/env.example).

## How to duplicate

Click **Duplicate this Space**. Variables carry over; **Secrets do not** —
you'll re-enter your own keys, so you never inherit the original operator's.

## Hardware recommendations

- **Default:** CPU basic — the lightweight demo needs no GPU.
- **GPU:** only worth it if you've also configured a real embedding/LLM
  provider; document the tier once you have real ModelFit numbers for it.

## Limitations

<Offline extractive answering verifies the pipeline not answer quality; CPU
only; single demo corpus; no persistence; etc. — be honest.>

## Source & license

Source: <https://github.com/MHHamdan/Auralynq>. License: Apache-2.0 (code).
Demo data: <its own license, e.g. CC0-1.0>.
