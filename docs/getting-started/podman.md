# Running Auralynq with Podman (production-shaped stack)

Auralynq is **Podman-first** — no Docker, no sudo required. This mode runs
the full 7-service topology behind a TLS reverse proxy: `caddy`, `web`, `api`,
`worker`, `mcp`, `qdrant`, `phoenix`.

For a lighter single-process setup with no containers, see
[no-podman.md](no-podman.md) instead.

## Prerequisites

- Podman + a Podman Compose (`podman compose` or `podman-compose`)
- No Docker needed anywhere in this flow

```bash
make runtime-check   # verifies a Podman Compose command is available
```

## 1. Build and start

```bash
git clone https://github.com/MHHamdan/Auralynq.git && cd Auralynq
cp .env.example .env    # optional; only HUGGINGFACE_TOKEN matters for gated models

make images       # build versioned api/web/caddy images locally
make stack-up      # start the stack (alias: make up)
```

`make stack-up` starts caddy (public TLS) + web + api + mcp + worker + qdrant +
phoenix, in a hardened order. Only the Caddy HTTPS port is meant to be public;
everything else binds to loopback by default.

## 2. Seed and index data

```bash
podman exec auralynq-api auralynq data --sample
podman exec auralynq-api auralynq index --input /app/data/corpus
```

Or upload documents directly through the web UI's Ingest tab — no shell access
needed.

## 3. Open it

- Web UI: **https://localhost:8443** (accept the self-signed cert warning, or
  see [server.md](server.md) for a real domain / trusted cert)
- API docs: **https://localhost:8443/api/docs**
- Phoenix traces: loopback-only by default; SSH-tunnel to view, or expose
  intentionally if you understand the trade-off

## Everyday commands

```bash
make stack-down     # stop
make stack-logs      # tail logs
make fresh           # wipe corpus + Qdrant volumes and start clean
make status          # container status (when using `make start`/`make stop`)
```

## Rebuilding after a code change

`podman-compose build` can silently reuse cached layers for both the
multi-stage web image and the single-stage API image. Always rebuild with
`podman build --no-cache` directly, then fully cycle the stack (compose pins
image IDs, so a plain restart won't pick up a new image):

```bash
make images
podman-compose -f compose.yml down && make stack-up
```

## Where your data lives (Podman mode)

Corpus, vector index, and page cache live in named Podman volumes (not the
host filesystem), so they survive `stack-down`/`stack-up` cycles but are
separate from whatever `./data/` holds if you also ran no-Podman mode on the
same machine. `make fresh` wipes exactly these volumes (`auralynq-data`,
`auralynq-qdrant`) and nothing else.

## Next steps

- Deploying to a remote server with a real domain/IP → [server.md](server.md)
- No containers at all → [no-podman.md](no-podman.md)
- Something not working → [troubleshooting.md](troubleshooting.md)
