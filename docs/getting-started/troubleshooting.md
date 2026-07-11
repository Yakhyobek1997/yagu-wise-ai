# Troubleshooting

## No-Podman / local dev

- **`make setup` fails to resolve deps** — make sure you're on Python 3.11 or
  3.12 (`python3 --version`); older interpreters aren't supported
  (`requires-python = ">=3.11"`).
- **`auralynq: command not found` after `make setup`** — activate the venv:
  `source .venv/bin/activate`.
- **Answers look extractive / low quality** — you're on the offline fallback
  (hash embeddings + in-memory store + extractive LLM). This is expected with
  no keys/extras installed and verifies pipeline *integrity*, not quality —
  see the Limitations section in `README.md`. Install `auralynq[embeddings]`
  and/or set an LLM provider key for real quality.
- **Web UI can't reach the API** — confirm `NEXT_PUBLIC_API_BASE` matches
  where `uvicorn` is actually listening (`http://localhost:8000/api` for the
  no-Podman dev flow), and that both processes are running.
- **Port already in use** — pass `--port` to `uvicorn`/`npm run dev` or stop
  whatever else is bound to 8000/3000.

## Podman stack

- **`make runtime-check` can't find a Compose command** — install
  `podman compose` (Podman v4+) or `podman-compose` separately; Auralynq
  resolves whichever is present via `scripts/check_container_runtime.sh`.
- **Cert warning in the browser** — expected with the baked-in self-signed
  cert; click *Advanced → Proceed*, or follow [server.md](server.md) to bind a
  real domain with Let's Encrypt.
- **502 right after `make stack-up`** — the web container is still booting;
  retry in a few seconds.
- **No answer in chat after a code change** — rebuild the image
  (`podman build --no-cache`, not `podman-compose build`, which can reuse
  stale layers) and fully cycle the stack (`podman-compose down` then
  `make stack-up`); hard-refresh the browser.
- **Rootless networking / container DNS issues** — `make stack-up`
  auto-patches the CNI conflist (CNI 0.4.0 + dnsname) on hosts where rootless
  Podman lacks container DNS; no sudo needed. On a netavark host this is a
  no-op.
- **Can't reach the stack from another machine** — open inbound TCP on
  whatever `AURALYNQ_HTTPS_PORT` is set to (default `8443`) in the firewall;
  every other port binds to loopback intentionally.

## Both modes

- **Secrets never show up** — they live only in `.env` (git-ignored); if a
  provider isn't detected, check the exact env var name against
  `.env.example` (nested settings use `__`, e.g. `AURALYNQ_LLM__PROVIDER`).
- **Corpus looks stale after deleting files by hand** — don't delete `data/`
  subfolders directly; use the API's guarded clear flow
  (`POST /corpus/clear/preview` then `/corpus/clear/confirm`) so the vector
  store, graph, and page cache are cleared together. See
  [no-podman.md](no-podman.md#clearing-your-data-safely).
- **Visual grounding shows "unavailable" for a document** — it was indexed
  before visual grounding metadata existed, or page rendering failed at
  ingest. Re-ingest the document, or use
  `POST /documents/{id}/render-pages` to re-render pages without a full
  reindex.

## Still stuck?

Open an issue with: your OS, Python/Node versions, which mode (no-Podman /
Podman / server), the exact command that failed, and the full error output.
