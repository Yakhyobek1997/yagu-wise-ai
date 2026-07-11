# Deploying Auralynq to a Hugging Face Space

> **Status: implemented and locally smoke-tested; not yet published to a
> real Hugging Face Space.** The `deploy/huggingface/` artifacts (Dockerfile,
> entrypoint, env template, Space README template) exist and were verified
> with `podman build` + `podman run` on this machine: health check, `/api/status`
> demo-mode fields, the ModelFit hardware probe, upload gating (403 when
> `AURALYNQ_ALLOW_UPLOADS=false`), the landing page, and a real grounded
> `/api/query` answer against the pre-seeded demo corpus all worked through
> the single exposed port. **Not verified:** an actual Hugging Face Space
> build (HF's build environment, network egress rules, and persistent-storage
> mount behavior can all differ from a local Podman run) — see the caveats in
> [`deploy/huggingface/README.md`](../../deploy/huggingface/README.md) before
> publishing one. Nothing here has been published to Hugging Face
> automatically; publishing is always a manual step you take yourself.

## Why a Space needs its own packaging

Auralynq's default topology (see [podman.md](podman.md)) is 7 containers
behind a Caddy TLS proxy — that doesn't map onto a single HF Space container.
A Space needs one image that either serves the API and a static/SSR frontend
together, or runs both processes under a small supervisor inside one
container.

## The two modes

**Mode A — Lightweight demo Space (this is what `deploy/huggingface/Dockerfile` builds today)**
- No secrets required to run.
- Ships with the [demo corpus](../../examples/demo_corpus/) — seeded and
  indexed on first boot by `entrypoint.sh` (verified: ~1 second, offline).
- Forces the offline/extractive fallback path (hash embeddings, in-memory
  vector store, extractive answering) — no model downloads, no GPU.
- Uploads disabled by default (`AURALYNQ_ALLOW_UPLOADS=false`, enforced in
  `auralynq/serving/app.py`'s `/ingest` handler — verified: returns 403) so a
  public, unauthenticated Space can't accumulate arbitrary user documents.
- Demonstrates: chat, citations, visual grounding, ModelFit hardware page
  (CPU-only numbers, real for whatever container it runs in).

**Mode B — Full Docker Space (same image; flip the env vars below)**
- Reads provider keys from HF Space **Secrets** (never Variables, never
  baked into the image).
- Optionally attaches persistent `/data` if the Space has persistent storage
  enabled; otherwise storage is ephemeral and reset on every Space restart —
  this will be stated plainly in the Space README so nobody mistakes it for
  durable storage.
- Uploads may be enabled (`AURALYNQ_ALLOW_UPLOADS=true`) only when the
  operator understands the privacy implications of a public Space
  persisting user-uploaded documents.

## Environment variables

```bash
AURALYNQ_HF_SPACE=true
AURALYNQ_DEMO_MODE=true
AURALYNQ_PUBLIC_DEMO=true
AURALYNQ_ALLOW_UPLOADS=false            # true only if you understand the persistence/privacy trade-off
AURALYNQ_DATA_DIR=/data/auralynq
AURALYNQ_SERVE__API_KEY=                # set via Space Secrets if the Space needs auth
NEXT_PUBLIC_API_BASE=/api
AURALYNQ_LLM__PROVIDER=extractive
AURALYNQ_VECTOR__BACKEND=memory
AURALYNQ_EMBEDDING__PROVIDER=hash
AURALYNQ_VISUAL__ENABLED=true
AURALYNQ_MODELFIT__ENABLED=true
```

All of these are real, typed `Settings` fields (`auralynq/config/settings.py`)
read by the API at startup — `hf_space`, `demo_mode`, `public_demo`, and
`allow_uploads` are surfaced back out on `GET /api/status` (verified in a
running container), and `modelfit.enabled` gates whether the ModelFit router
is even mounted. `env.example` in `deploy/huggingface/` documents the full
set, split into Space Variables vs. Secrets.

## Variables vs. Secrets (Hugging Face concept, applies once the Space exists)

- **Variables**: visible to anyone who can view the Space's settings/logs if
  misconfigured — fine for `AURALYNQ_DEMO_MODE`, `NEXT_PUBLIC_API_BASE`, etc.
  Never put a provider key in a Variable.
- **Secrets**: encrypted, not visible in the Space UI or logs — use for
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`,
  `AURALYNQ_SERVE__API_KEY`, `HUGGINGFACE_TOKEN`.

## Persistent vs. ephemeral storage

- Free/CPU Spaces without persistent storage attached: everything under
  `AURALYNQ_DATA_DIR` is wiped on every Space restart/redeploy. Uploaded
  documents, the vector index, and the page cache do not survive.
- Spaces with **Persistent Storage** enabled: `/data` survives restarts. Mode
  B is designed to use this when available and to say so explicitly in the
  Space README so users don't assume privacy guarantees that don't hold for
  a public Space regardless of storage durability.

## Hardware

- Default target: **CPU basic** — the whole point of the lightweight mode is
  that it needs no GPU.
- Upgrading to GPU: only meaningful if you also enable a real embedding/LLM
  provider; document the specific hardware tier once ModelFit numbers exist
  for it (no fabricated numbers — see `docs/benchmarks.md` once it exists).

## Duplicating the Space

Once published, "Duplicate this Space" carries over Variables but not
Secrets — anyone duplicating a Mode B Space must re-enter their own provider
keys; they never inherit the original operator's keys.

## Next steps

- No containers at all → [no-podman.md](no-podman.md)
- Full Podman stack → [podman.md](podman.md)
- Remote server deployment → [server.md](server.md)
