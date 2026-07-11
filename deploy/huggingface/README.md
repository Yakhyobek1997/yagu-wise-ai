# Hugging Face Space packaging

Artifacts for running Auralynq as a single-container Hugging Face Space
(Docker SDK). Nothing here publishes anything automatically — every step
below is a manual, explicit action you take in your own Hugging Face
account.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Single-container image: Next.js standalone web server (foreground) + FastAPI/uvicorn API (background, loopback-only), built from the repo root. |
| `entrypoint.sh` | Seeds/indexes the demo corpus on first boot (demo mode only), starts both processes, waits for the API to be healthy before serving traffic. |
| `env.example` | Every environment variable this image reads, split into Space Variables vs. Secrets, with safe defaults already baked into the Dockerfile. |
| `space-config.example.yaml` | The Space metadata block (title, SDK, port, license) — copy into your Space README's front-matter. |
| `README_SPACE_TEMPLATE.md` | A complete Space README (front-matter + body) you can copy as-is to a new Space repo. |

## Build and test locally first

Always smoke-test the image locally before pushing to Hugging Face — a
Space rebuild is slower to iterate on than a local container.

```bash
# from the repository root
podman build -f deploy/huggingface/Dockerfile -t auralynq-space .
podman run --rm -p 7860:7860 auralynq-space
```

Then check:
```bash
curl -sf http://localhost:7860/api/health
curl -sf http://localhost:7860/api/status
```
Open `http://localhost:7860` in a browser and try a question from
[`examples/demo_corpus/expected_questions.md`](../../examples/demo_corpus/expected_questions.md).

## Publishing to Hugging Face (manual steps)

1. Create a new Space at huggingface.co, SDK = **Docker**.
2. Copy `README_SPACE_TEMPLATE.md` to the Space repo's `README.md` (it
   already has the front-matter from `space-config.example.yaml`).
3. Copy this repository's `Dockerfile`... actually, point the Space at this
   repo directly (Space repos can mirror a GitHub repo, or you can push a
   copy) — either way, the Space needs `deploy/huggingface/Dockerfile` to
   resolve at the repo root as its `Dockerfile`, or you set the Space's
   "Dockerfile path" setting to `deploy/huggingface/Dockerfile` if your
   Space SDK settings support a custom path.
4. Set Variables from `env.example`'s Variables section (safe defaults
   already exist in the image — you only need to override what you want to
   change).
5. Set Secrets from `env.example`'s Secrets section, if you want real model
   quality instead of the offline extractive fallback.
6. Save — the Space builds and starts automatically. Watch the build logs
   for the same health check used locally.

## Known caveats (read before enabling persistent storage or uploads)

- **Persistent storage ownership.** The container runs as a non-root user
  (`auralynq`, uid 10001). If you attach Hugging Face Persistent Storage at
  `/data`, HF may mount it with different ownership than the container
  expects, which can cause permission errors on first boot. This has **not
  been verified against a real HF persistent-storage mount** in this change
  — treat it as untested until you've confirmed it on an actual Space, and
  be ready to `chmod`/`chown` the mount in a startup step if needed.
- **Uploads + no persistence = uploads vanish on restart.** If you set
  `AURALYNQ_ALLOW_UPLOADS=true` without persistent storage, uploaded
  documents live only as long as the container runs — say so in your Space
  README if you enable this, so users aren't surprised.
- **Public, unauthenticated Space + uploads enabled** means anyone can add
  documents to a corpus other visitors can then query. Only enable uploads
  on a public Space if you understand and accept that.
- **CPU only by default.** The image never installs `embeddings`/`voice`/
  `slm` (torch) extras — if you want real embeddings or a local GGUF model,
  you'll need to modify the Dockerfile's `pip install` extras and likely
  request GPU hardware, at which point ModelFit's recommendations become
  meaningful for this container.

## Design notes

See [`docs/getting-started/huggingface-space.md`](../../docs/getting-started/huggingface-space.md)
for the two-mode design (lightweight demo vs. full Docker Space), the
Variables-vs-Secrets explanation, and the persistent-vs-ephemeral storage
trade-offs in more depth.
