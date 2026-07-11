# Deploying Auralynq to a server

This covers running the full Podman stack on a Linux server you control,
reachable from other machines. It builds on [podman.md](podman.md) — read
that first if you haven't run the stack locally yet.

The stack exposes **one public port** (Caddy TLS, default `8443`). The web
UI, API, Qdrant, and Phoenix all bind to loopback internally and are
unreachable from the server's network interface directly — only Caddy is
public.

## Prerequisites on the server

- Podman + a Podman Compose (`podman compose` or `podman-compose`)
- One inbound firewall rule: TCP `8443` (or whatever you set
  `AURALYNQ_HTTPS_PORT` to)
- No GHCR login needed if you use the public pre-built images

## Option A — run from the published images (no source needed)

You only need `compose.yml`, `containers/Caddyfile`, `scripts/`, and a
`Makefile` — or just clone the repo, it's small.

```bash
git clone https://github.com/MHHamdan/Auralynq.git && cd Auralynq
```

Create `.env` (git-ignored; never commit it) — replace `<SERVER>` with the
server's IP or domain:

```bash
cat > .env <<'EOF'
AURALYNQ_HTTPS_PORT=8443
AURALYNQ_CERT_HOST=<SERVER>                       # IP or domain (cert SAN)
AURALYNQ_SITE_ADDRESS=:8443                       # or https://your.domain for Let's Encrypt
AURALYNQ_SERVE__CORS_ORIGINS=["https://<SERVER>:8443"]
NEXT_PUBLIC_API_BASE=/api                         # browser -> same-origin proxy
AURALYNQ_BIND_INTERNAL=127.0.0.1                  # internal services off the public NIC

AURALYNQ_IMAGE_PREFIX=ghcr.io/mhhamdan/auralynq-
AURALYNQ_IMAGE_TAG=0.2.0

# Providers are all optional; missing keys degrade to local/offline fallbacks
AURALYNQ_LLM__PROVIDER=auto
# COHERE_API_KEY= / OPENAI_API_KEY= / ANTHROPIC_API_KEY= / HUGGINGFACE_TOKEN=

# Recommended once the server is reachable from anyone but you:
AURALYNQ_SERVE__API_KEY=<openssl rand -hex 24>
EOF

make stack-up
```

Browse to `https://<SERVER>:8443`.

## Option B — build images on the server from source

```bash
make images       # build api/web/caddy locally, versioned + OCI labels
make stack-up
```

## The TLS certificate

The public Caddy image ships a **self-signed cert** whose SAN is
`AURALYNQ_CERT_HOST`. On a fresh host this means a browser warning
(functionally fine — *Advanced → Proceed*). To avoid it:

- **Self-signed for your own IP** — rebuild caddy locally with your IP as the
  SAN:
  ```bash
  AURALYNQ_CERT_HOST=<SERVER> podman build -t auralynq-caddy:0.2.0 -f containers/caddy.Dockerfile .
  ```
- **Trusted certificate (real domain)** — set
  `AURALYNQ_SITE_ADDRESS=https://your.domain`; Caddy auto-provisions Let's
  Encrypt (needs DNS pointed at this host and ports 80/443 reachable).

## Adding data once it's running

- **UI**: Ingest tab → upload a PDF/DOCX/TXT/audio file.
- **CLI**:
  ```bash
  podman cp mydoc.pdf auralynq-api:/app/data/corpus/
  podman exec auralynq-api auralynq index --input /app/data/corpus
  ```

## Health checks

```bash
podman ps
curl -sk https://<SERVER>:8443/api/health
curl -sk -X POST https://<SERVER>:8443/api/query \
  -H 'content-type: application/json' -d '{"question":"hi"}'
```

## Security notes

- The browser never holds the API key — the web container's same-origin
  `/api/*` proxy injects the bearer token server-side.
- Set `AURALYNQ_SERVE__API_KEY` once the server is reachable by anyone other
  than you; it's empty (open) by default for local/demo convenience.
- Only the HTTPS port needs to be open in the firewall — everything else
  binds to loopback.

## Next steps

- Local Podman without a public server → [podman.md](podman.md)
- No containers at all → [no-podman.md](no-podman.md)
- Something not working → [troubleshooting.md](troubleshooting.md)
