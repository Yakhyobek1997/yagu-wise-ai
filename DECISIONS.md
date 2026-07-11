# Architecture Decision Records — Auralynq

Short ADRs. Each: **Context → Decision → Rationale → Alternatives rejected.**

---

## ADR-0001 — Product & package naming

**Context.** The product must use one consistent name across package, CLI, services, UI, and docs.

**Decision.** Product = **Auralynq**. Python package / modules / folders / CLI / services = `auralynq`. MCP server = `auralynq-mcp`. Container prefix = `auralynq-*`. Tagline = "Talk to Your Data". **PathRAG** is preserved only as the name of the graph-retrieval algorithm/paper.

**Rationale.** Single source of truth prevents drift; a repo-wide name audit (`make name-audit`) enforces it.

**Alternatives rejected.** Mixed/generic naming (e.g. a "Voice-RAG"-style label, or branding the product after the PathRAG algorithm) — causes branding drift and import confusion.

---

## ADR-0002 — Python 3.11 baseline (spec asked 3.12)

**Context.** Spec requests Python 3.12; the build/CI environment ships Python 3.11.14.

**Decision.** Target `requires-python = ">=3.11"`. Code is written to be 3.11/3.12 compatible; CI matrices both.

**Rationale.** Use the interpreter actually present so `make setup`/tests run at $0 with no extra downloads. No 3.12-only syntax is used.

**Alternatives rejected.** Forcing a 3.12 toolchain install — slower setup, no functional benefit for this codebase.

---

## ADR-0003 — Lightweight core + optional heavy extras + deterministic fallbacks

**Context.** The spec mandates "runs locally at $0", "missing paid keys never break the demo", yet also wants bge-m3, Qdrant, whisper, pyannote, Kokoro, langgraph, ragas, etc. — multi-GB GPU stacks.

**Decision.** Core deps are pure-Python/light (pydantic, fastapi, numpy, networkx, httpx). Every heavy/paid integration lives in a `pyproject` extra and is **imported lazily**. Each subsystem ships a deterministic, dependency-free **fallback**:
- Embeddings → hashing-bag embedder (stable, seeded) when bge-m3 absent.
- Vector store → in-process `MemoryStore` when `qdrant-client`/server absent.
- LLM → extractive synthesizer (citation-faithful) when Ollama/keys absent.
- ASR/TTS → null/sine + transcript-passthrough providers when models absent.
- Agent → native Python state machine mirroring the LangGraph graph when `langgraph` absent.
- Eval → numpy metric implementations when `ragas`/`jiwer` absent.

**Rationale.** The whole platform — ingest → index → retrieve → agent → serve → eval → MCP → UI — is exercisable and unit-tested offline. Upgrading to real models is a config flag, not a code change. This is the single most important design choice for reproducibility.

**Alternatives rejected.** Hard-requiring the ML stack — breaks `$0` guarantee, makes CI heavy/flaky, slows onboarding.

---

## ADR-0004 — Provider abstraction via factories + `auto` resolution

**Context.** Many swappable backends (embeddings, LLM, rerank, ASR, TTS, vector).

**Decision.** Each subsystem exposes a `Protocol`/ABC and a `factory.py` that resolves `provider=auto` by probing env keys and importable packages, falling back deterministically. Selection is logged once at startup.

**Rationale.** One config surface; testable resolution logic; honest "what's actually running" reporting at `/health`.

**Alternatives rejected.** Hard-wired imports; conditional logic scattered across call-sites.

---

## ADR-0005 — Podman-first containerization

**Context.** Target machine has no Docker; Podman 3.4 with `podman-compose` (the `podman compose` subcommand is absent).

**Decision.** `scripts/check_container_runtime.sh` detects `podman compose` then `podman-compose`; all Makefile stack targets call it. Compose file is `compose.yml`. Images are rootless-friendly (no privileged ports, named volumes).

**Rationale.** Matches the actual environment; degrades gracefully with a clear message if neither is present.

**Alternatives rejected.** Docker / docker-compose — not installed, explicitly disallowed.

---

## ADR-0006 — PathRAG isolated, attributed, flow-pruned

**Context.** Graph retrieval must implement PathRAG (Chen et al., 2025) with flow-based pruning.

**Decision.** PathRAG lives only under `auralynq/retrieval/pathrag/`. We implement node retrieval → relational path expansion (bounded hops) → resource-flow-based path pruning → path-reliability scoring → deterministic path-to-text prompting with golden-region (most-reliable-at-edges) ordering. The algorithm is a clean-room implementation from the paper; attribution + license notes in `THIRD_PARTY.md`.

**Rationale.** Clear module boundary, testable scoring, no licensing entanglement.

**Alternatives rejected.** Vendoring a third-party repo wholesale (license/maintenance risk).

---

## ADR-0007 — Relational knowledge graph in NetworkX + SQLite-style JSON persistence

**Context.** Need entities, relations, provenance, spans, timestamps, reliability — small/local.

**Decision.** Build the KG with `networkx.MultiDiGraph`; persist as versioned JSON (`graph.json`) plus a node/edge provenance table. Reliability scores are computed from corroboration count + source trust.

**Rationale.** Zero-infra, diff-able, fast for laptop-scale corpora; trivially swappable for a real graph DB later.

**Alternatives rejected.** Neo4j (infra weight), pure in-memory (no persistence).

---

## ADR-0008 — Agent as explicit typed state machine

**Context.** Spec lists 11 nodes with latency budgets and iteration caps.

**Decision.** A single Pydantic `AgentState` flows through nodes. When `langgraph` is installed we compile a real `StateGraph`; otherwise an equivalent ordered executor runs the same node functions. Every node emits a trace span with timing; the trajectory is returned in the API response and rendered in the UI.

**Rationale.** Identical behavior with/without langgraph; full observability; deterministic tests.

**Alternatives rejected.** langgraph as a hard dependency (heavy, breaks $0 default).

---

## ADR-0009 — SSE for chat tokens, WebSocket for voice

**Context.** Need token streaming and a bidirectional voice channel.

**Decision.** Chat uses Server-Sent Events (`sse-starlette`) — simple, proxy-friendly, unidirectional. Voice uses a WebSocket carrying control + audio frames for the push-to-talk loop.

**Rationale.** Right tool per channel; SSE avoids WS overhead for plain token streams.

**Alternatives rejected.** WS for everything (more complex client), polling (latency).

---

## ADR-0010 — Eval harness owns all benchmark numbers

**Context.** README must not contain invented numbers.

**Decision.** Every metric in the README is produced by `make eval` / `make bench` and written under `reports/`. Unmeasured metrics are explicitly marked "pending". A frozen golden set + drift check guards regressions.

**Rationale.** Honesty + reproducibility; the README is generated from real artifacts.

**Alternatives rejected.** Hand-written marketing numbers.

---

## ADR-0011 — Optional bearer-token API auth (open-by-default)

**Context.** The serving layer needs a production auth story, but the headline
promise is a zero-friction local `$0` demo. These pull in opposite directions.

**Decision.** Auth is gated by `AURALYNQ_SERVE__API_KEY`. Empty (default) ⇒ the API
is open — the local demo and tests are unaffected. When set, an `AuthMiddleware`
requires `Authorization: Bearer <key>` on all endpoints except `/health` and
`/metrics` (and CORS pre-flight), returning a structured 401. Tokens are compared
with `hmac.compare_digest` (constant-time).

**Rationale.** One env var flips a local demo into an authenticated deployment with
no code change; health/metrics stay public for orchestrators/probes; constant-time
compare avoids timing leaks.

**Alternatives rejected.** Always-on auth (breaks the $0 demo), per-route decorators
(scattered, easy to miss an endpoint), full OAuth/JWT (over-engineered for a
single-tenant local-first tool; can layer on later behind the same middleware).

---

## ADR-0012 — Deployment hardening for remote/server exposure

**Context.** The stack is run on a remote server reachable by browsers on other
machines, with all ports bound to `0.0.0.0`. The earlier setup ran api/worker as
container-root, exposed Qdrant + Phoenix publicly with no auth, had no restart
policies/healthchecks, and (for rootless DNS reasons) reached Qdrant via the host
gateway. Enabling API auth naively would either break the browser UI or leak the
key into the client bundle.

**Decision.**
- **Network surface:** only the **web UI** and **API** publish on `0.0.0.0`.
  **Qdrant and Phoenix** bind to `${AURALYNQ_BIND_INTERNAL:-127.0.0.1}` — on this
  host the podman bridge gateway (`10.88.0.1`/cni-podman0), reachable by containers
  (via `host.containers.internal`) and host tooling, but **not** from the external
  NIC. Default `127.0.0.1` keeps a clean host secure out of the box.
- **API auth:** `AURALYNQ_SERVE__API_KEY` (empty == open). The browser never holds
  the key: the **web container runs a same-origin `/api/*` proxy** (Next.js route
  handler) that injects `Authorization: Bearer` server-side and streams responses.
  So `NEXT_PUBLIC_API_BASE=/api` — no IP and no secret are baked into the bundle.
- **Least privilege:** api/worker drop the `user: "0:0"` override and run as the
  image's non-root `auralynq` (uid 10001); all services get
  `security_opt: ["no-new-privileges"]`, `restart: unless-stopped`, and
  healthchecks. Named volumes (`auralynq-data`, `auralynq-reports`) initialize with
  the image's non-root owner so writes succeed without host-ownership clashes.

**Rationale.** Satisfies "expose only UI+API", "enable API auth", and "never expose
secrets" simultaneously; the proxy also removes CORS as an attack surface (browser
calls are same-origin). Restart + healthchecks give crash recovery. TLS / public
reverse proxy is intentionally deferred to a separate step.

**Alternatives rejected.** Baking the key into the browser bundle (leaks the secret);
breaking the UI when auth is on (fails the "UI reachable" goal); binding internal
services to `127.0.0.1` only (the rootless API can't reach host loopback — no working
inter-container DNS on this Podman 3.4/CNI host); fixing DNS (dnsname/aardvark not
available here).

---

## ADR-0013 — TLS reverse proxy (Caddy), single public HTTPS port

**Context.** The hardened stack (ADR-0012) exposed plaintext HTTP on the API/UI
ports. Production remote access needs TLS, ideally a single public entrypoint.

**Decision.** Add a **Caddy** reverse-proxy service as the ONLY container published
on `0.0.0.0` (default `:8443`). It terminates TLS and forwards to the web container
(`auralynq-web:3000`), which serves the UI and proxies `/api/*` to the API. web,
api, qdrant, phoenix only bind to `${AURALYNQ_BIND_INTERNAL:-127.0.0.1}` (loopback)
plus the shared container network. TLS uses a **self-signed cert baked into the
Caddy image** (`containers/caddy.Dockerfile`) with the server IP + localhost as
SANs, served via an explicit `tls /certs/site.crt /certs/site.key` directive —
reliable for an IP / no-domain host (Caddy's on-demand internal-CA issuance is
unreliable for bare-IP sites). HTTP/3 is disabled (rootless can't size the QUIC
UDP buffer). `flush_interval -1` keeps SSE streaming + WebSocket voice unbuffered.

**Rationale.** One public TLS port; the browser only ever talks to Caddy; the API
key never leaves the server (web `/api` proxy injects it). For a real domain, set
`AURALYNQ_SITE_ADDRESS=https://your.domain` + `AURALYNQ_TLS=internal` (or ACME).

**Alternatives rejected.** `tls internal` for a bare-IP site (handshake fails — no
leaf cert for IP SNI); HTTP/3 (broken UDP buffer on rootless); terminating TLS in
the app (re-implements a proxy, no cert automation).

---

## ADR-0014 — No-sudo fix for rootless container DNS (CNI 0.4.0 + dnsname)

**Context.** This host runs **rootless Podman 3.4 with CNI**. Two defects broke
inter-container networking: (1) podman generates network conflists with
`cniVersion: 1.0.0`, but the installed **`firewall` CNI plugin only supports
≤0.4.0**, so it fails validation and collapses the plugin chain; (2) the default
`podman` network ships **without the `dnsname` plugin**, so there is no container
DNS at all. Earlier ADR-0012 worked around this with brittle bridge-IP wiring and
shared network namespaces. A proper fix via podman 4 / netavark needs root — but
the whole point of rootless Podman is to avoid sudo.

**Decision.** Fix it **without sudo** by rewriting the user-owned CNI conflists in
`~/.config/cni/net.d/`: pin `cniVersion` to `0.4.0` (which `firewall`, `bridge` and
`dnsname` all support) and append the `dnsname` plugin if absent. `scripts/stack_up.sh`
does this idempotently before `up`. With DNS restored, all services share
podman-compose's default network and address peers by **container_name**
(`auralynq-qdrant` / `auralynq-api` / `auralynq-web`) — eliminating the bridge-IP
guessing and shared-netns hacks. `dnsname` requires the `dnsmasq` binary (present)
and the plugin binary at `/usr/lib/cni/dnsname` (present; the rootless plugin dir
is set in `~/.config/containers/containers.conf`).

**Rationale.** Pure user-space, persists across `down`/`up`, and restores the
clean service-name networking Podman is supposed to provide. Supersedes the
bridge-IP workaround noted in ADR-0012.

**Alternatives rejected.** podman 4 + netavark (needs root); `external` networks in
compose (podman-compose 1.5.0 ignores them — attaches to the default net anyway);
shared network namespace for every service (couples lifecycles, can't publish
per-container ports); service-name aliases (dnsname resolves container_name, not
the compose service name, on this version).

---

## ADR-0015 — MCP as a first-class microservice (stdio + streamable-HTTP)

**Context.** The MCP server exposes Auralynq's 7 tools but was stdio-only — usable
by a local client that spawns the process, not by remote clients. The product goal
is to "serve production-ready around the world" as composable microservices.

**Decision.** Keep the transport-agnostic tool functions
(`auralynq/mcp_server/tools.py`) as the single source of truth, and make the server
**transport-selectable** via `--transport` / `AURALYNQ_MCP_TRANSPORT`:
`stdio` (default, local), `streamable-http` (remote microservice on
`AURALYNQ_MCP_HOST:PORT`, default `:8765`), or `sse` (legacy). A dedicated
`auralynq-mcp` container in `compose.yml` runs the HTTP transport (internal-only;
front with the Caddy TLS proxy for public exposure). An integration test drives
the real stdio protocol end-to-end (client → server → tool) and auto-skips when
the optional SDK is absent.

**Rationale.** One tool implementation, many entry points (CLI, FastAPI, local
MCP, remote MCP). HTTP transport lets agents/IDEs anywhere call the same grounded
RAG + PathRAG + voice tools — the microservices foundation the roadmap needs —
without duplicating logic.

**Alternatives rejected.** A bespoke REST shim around the tools (re-implements MCP,
loses client compatibility); HTTP-only (breaks the zero-config local Claude Desktop
flow); embedding MCP in the FastAPI app (couples two servers with different
lifecycles and auth models).

---

## ADR-0016 — Bearer-token auth for the MCP HTTP transports

**Context.** ADR-0015 made MCP remotely callable over HTTP. An open HTTP MCP
endpoint exposes the full ingest/search/agent toolset to anyone who can reach it —
unacceptable for public deployment.

**Decision.** Add an ASGI `MCPAuthMiddleware` wrapped around FastMCP's
`streamable_http_app()` / `sse_app()` (served via uvicorn in `_serve_http`). It
requires `Authorization: Bearer <key>` when a key is configured, returning a
structured 401 otherwise; comparison is constant-time (`hmac.compare_digest`).
Key resolution: `AURALYNQ_MCP_API_KEY` (dedicated) wins, else
`AURALYNQ_SERVE__API_KEY` (reuse the HTTP API key). Empty ⇒ open. The **stdio
transport is never gated** (it is local — the client spawns the process), so the
zero-config Claude Desktop flow is unaffected.

**Rationale.** Mirrors the HTTP API's auth model (ADR-0011) for consistency; one
env var turns the remote MCP microservice from open to authenticated with no code
change; constant-time compare avoids timing leaks. Combined with the Caddy TLS
proxy (ADR-0013) the token travels encrypted.

**Alternatives rejected.** OAuth/JWT (over-engineered for a single-tenant tool;
can layer behind the same middleware later); gating stdio (breaks local clients);
relying only on network isolation (defense-in-depth — auth + internal binding +
TLS are complementary).

---

## ADR-0017 — Versioned container images + GHCR registry

**Context.** "Serve production-ready around the world" needs deployable, pinnable,
traceable images — not a single mutable `:latest`. The repo lives on GitHub.

**Decision.** Publish three OCI-labelled images (`auralynq-api`, `auralynq-web`,
`auralynq-caddy`) to **GitHub Container Registry** (`ghcr.io/<owner>/…`). The
version is the single source `auralynq.__version__`; every build carries four
tags: **`X.Y.Z`** (immutable release), **`X.Y`** (latest patch of a minor),
**`<git-sha>`** (exact provenance), and **`latest`** (convenience). Tooling:
`scripts/image_env.sh` (shared config), `scripts/build_images.sh`,
`scripts/push_images.sh`, and `make images|push|version`. The authoritative
publish path is CI: `.github/workflows/release.yml` builds + pushes on a `v*` git
tag using the workflow's `GITHUB_TOKEN` (`packages: write`) — no manual login.
`compose.yml` references `${AURALYNQ_IMAGE_PREFIX:-auralynq-}<svc>:${AURALYNQ_IMAGE_TAG:-X.Y.Z}`
so it runs locally-built images by default and a pinned GHCR version when set.

**Rationale.** Immutable + minor + sha + latest covers reproducible deploys,
easy patching, exact provenance, and convenience. GHCR is zero-config from GitHub
Actions. The single-source version + one tag scheme prevents drift; OCI labels
make images self-describing (source, revision, license).

**Alternatives rejected.** Bare `:latest` only (no rollback/pinning); Docker Hub
(extra account/secret vs. GHCR's built-in token); a separate VERSION file (drifts
from the package version); baking secrets into images (they stay in env/.env).

---

## ADR-0018 — Microservice split: one image, role entrypoints, k8s for scaling

**Context.** The roadmap calls for "independently scalable microservices, served
worldwide". The services already run as separate containers (api/mcp/worker/web +
qdrant/phoenix/caddy), but podman-compose 1.5 on this host can't do per-service
profiles or isolated subset deploys (verified: `up <svc>` pulls the whole
depends_on graph; `COMPOSE_PROFILES` is ignored), and a single-host compose file
isn't where independent autoscaling happens anyway.

**Decision.** Split by **process/role over one shared image**, not by duplicated
code or repos: `api`, `mcp`, and `worker` are the same `auralynq-api` image with
different entrypoints (`uvicorn …app` / `python -m …mcp_server.server` /
`python -m …serving.worker`); `web` is its own image. Ship **Kubernetes manifests**
(`deploy/k8s`, kustomize) as the production scaling path: each service is its own
Deployment+Service, api/mcp/web autoscale via HPA against a single Qdrant
StatefulSet, the web UI is the only public surface (Ingress+TLS), and config/secrets
are a ConfigMap+Secret. Compose remains the local/single-host mode. Topology +
scaling rules are documented in `docs/SERVICES.md`.

**Rationale.** One image = one build/test/provenance surface; roles diverge only
by args + env. k8s is where "independently scalable" is real (per-service replicas,
HPA, rolling updates), and the GHCR images (ADR-0017) make `kubectl apply -k`
deployable anywhere. Stateless-against-Qdrant api/mcp scale freely; the one
stateful tier (Qdrant) is isolated. Honest about the boundary: in-memory vector
backend is NOT multi-replica-safe — k8s config defaults to the Qdrant backend.

**Alternatives rejected.** Separate repos per service (duplicated core, version
skew, against the "one repo, keep updating" goal); per-service images for
api/mcp/worker (3× build/scan for identical code); compose profiles (broken on
podman-compose 1.5); baking scaling into compose (single-host; no autoscaling).

---

## ADR-0019 — Optional Langfuse trace export (best-effort, never blocking)

**Context.** The agent already builds an in-process `Trace` (per-node spans) and
mirrors it to OpenTelemetry/Phoenix. Production observability for a service "served
worldwide" benefits from a hosted trace/eval backend (Langfuse), but it must never
become a hard dependency or a failure point on the answer path.

**Decision.** Add `auralynq/telemetry/langfuse_export.py`: a best-effort exporter
that pushes a finished `Trace` to Langfuse as a trace (question input,
answer/route/metadata output) with one nested span per agent node. It is wired at
the end of `answer_question` and `stream_answer_question` via a `_export_langfuse`
helper that swallows all errors. Activation requires BOTH `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` AND the importable `langfuse` SDK (in the `telemetry` extra);
otherwise it is a silent no-op. Host is configurable for self-hosted Langfuse;
`/health` reports the active tracing backend.

**Rationale.** Same provider-abstraction + offline-safe pattern as every other
integration (ADR-0003/0004): one config flag turns it on, missing SDK/keys/network
degrade to the local tracer, and observability can never break or slow an answer.
Complements (does not replace) the in-process trace and Phoenix mirror.

**Alternatives rejected.** Hard-requiring langfuse (breaks $0 default, heavy dep);
exporting inline inside each node (couples the agent to a vendor, multiplies
failure surface); replacing the in-process tracer (loses the UI trace panel + the
always-on local record).

## ADR-0020 — Client-side API failover at the web proxy (local-primary, remote-backup)

**Context.** Auralynq can run as a full stack on a laptop with all real provider
keys, while a remote server (reached at `https://<server>:8443`) stays available
as a backup. We want the laptop UI to keep answering when the laptop's own API
container is down or wedged — without the user switching URLs or losing the
same-origin/secret-injection model (ADR-0012).

**Decision.** The Next.js `/api/[...path]` proxy gained an ordered-upstream
failover policy (`web/lib/failover.ts`, pure + unit-tested): try the
local/primary backend (`AURALYNQ_API_INTERNAL`) first; if it is unreachable
(connection error or time-to-first-byte over `AURALYNQ_API_PRIMARY_TIMEOUT_MS`,
default 12s) or returns a gateway-class status (502/503/504), replay the same
request against `AURALYNQ_API_FALLBACK` (e.g. `https://<server>:8443/api`). When a
fallback is configured the request body is buffered so it can be replayed; with no
fallback the proxy streams the body untouched (unchanged behavior). The
self-signed fallback cert is trusted via an `undici` `Agent`
(`connect.rejectUnauthorized:false`) passed as the global-`fetch` dispatcher,
enabled only when `AURALYNQ_API_FALLBACK_INSECURE_TLS=1`. The chosen upstream is
reported in the `x-auralynq-upstream: primary|fallback|none` response header.

**Rationale.** Failover belongs at the proxy: it already terminates the
same-origin contract and holds the bearer token, so streaming (SSE) and auth keep
working transparently. Only gateway-class statuses trigger failover — a 4xx/500
means the backend is up and answering, so failing over would mask real bugs.
Bounding only time-to-first-byte (not the whole stream) lets long LLM responses
flow while still escaping a hung backend. Empty `AURALYNQ_API_FALLBACK` is a
no-op, so server deployments are unaffected.

**Alternatives rejected.** DNS/round-robin or an external LB (heavier, loses the
secret-injection proxy); client-side (browser) failover (would expose the backup
URL + key to the browser, breaking ADR-0012); failing over on any 5xx (masks
application errors); `NODE_TLS_REJECT_UNAUTHORIZED=0` (disables TLS verification
process-wide instead of only for the one self-signed fallback).

---

## ADR-0021 — PPR-augmented PathRAG path scoring

**Context.** The original PathRAG path scorer uses a resource-decay flow model: a budget
is distributed from seed nodes with per-hop decay; a path's score is the bottleneck
(minimum) edge flow. This correctly penalises long, low-reliability chains but has a
structural bias toward short paths — a one-hop path from a seed always accrues the full
initial resource regardless of how central its terminal node is in the broader graph.

**Decision.** Augment the flow score with Personalised PageRank (PPR) terminal-node
authority. `_assign_ppr()` builds a collapsed `DiGraph` (no multi-edges, weights =
edge_weight × (0.1 + reliability)), runs `nx.pagerank()` with a personalisation vector
concentrated on the seed entities (alpha = 0.15 teleport = 85% damping), then normalises
scores to [0, 1]. The blended path score is **0.4 × flow_component + 0.6 × ppr_terminal**.
Flow provides edge-level robustness; PPR provides convergent multi-hop authority.

**Rationale.** PPR is the retrieval mechanism in HippoRAG (NeurIPS'24) and HippoRAG2,
where it outperforms flow-only scoring on multi-hop benchmarks by 5–20 pp. Keeping the
flow term (40 %) preserves the edge-reliability signal for short, high-precision paths
while the PPR term (60 %) rewards nodes that aggregate evidence from many query-relevant
directions. The `_apply_ppr()` call is a separate pass so the existing flow-based pruning
(`_prune`) removes candidate paths first — PPR is only computed over the retained set.

**Alternatives rejected.** Pure PPR without flow (loses per-edge reliability weighting);
learning-to-rank path scoring (requires labelled training data, breaks $0 constraint);
raising `max_hops` to compensate for flow's short-path bias (exponential expansion cost).

---

## ADR-0022 — Dual-signal evidence sufficiency (FAIR-RAG SEA)

**Context.** `node_critic` used token-level overlap to decide whether to rewrite the query:
`coverage = 1 - |gap_terms| / |q_terms|`. This correctly identifies missing vocabulary but
produces false-positive rewrites when the query and documents use synonymous or paraphrased
vocabulary — the retrieval is semantically sufficient even though the surface coverage is
low. This caused unnecessary rewrite iterations and increased latency on paraphrase-heavy
corpora (technical domains, multilingual documents).

**Decision.** Add a second gate: `_semantic_coverage()` computes the cosine similarity
between the query dense embedding and the mean of all retrieved-context dense embeddings,
mapped from [−1, 1] to [0, 1]. A rewrite is only triggered when **both**
`coverage < 0.6` and `semantic_coverage < 0.5`. A `semantic_coverage ≥ 0.5` reading
means the retrieved passages are on-topic at the embedding level even if their surface
tokens differ, so rewriting would likely recall the same passages with worse diversity.

**Rationale.** Mirrors the Structured Evidence Assessment (SEA) module in FAIR-RAG
(arXiv:2510.22344, Oct 2025), which found that combining lexical and semantic sufficiency
signals reduces spurious rewrites by ~30 % on paraphrase test sets. The embedder is already
loaded in `AgentDeps.hybrid.embedder` — no extra model weight. Falls back to 0.0 (always
allows rewrite) for the offline hashing embedder, which does not produce meaningful cosine
similarities.

**Alternatives rejected.** LLM-as-judge sufficiency check (too slow, too expensive for
the $0 constraint); BM25 IDF overlap (still purely lexical, same failure mode); ROUGE/BLEU
(designed for generation, not retrieval sufficiency).

---

## ADR-0023 — Calibrated four-signal confidence scoring

**Context.** The heuristic confidence formula `0.4 * context_count_fraction + 0.3 *
has_citations + 0.3 * token_coverage_fraction` conflates three different phenomena:
how many passages were retrieved (quantity), whether the LLM cited any of them (utilisation),
and whether the question's vocabulary was covered (lexical breadth). A high score on all
three is necessary but not sufficient — the retrieved passages could be marginally relevant
(low score) yet plentiful enough to drive a high confidence score.

**Decision.** Replace with four orthogonal signals:
- **score_quality** = clip(mean_retrieval_score / 0.7, 0, 1). Reference 0.7 is the
  empirical centre of bge-m3 cross-encoder scores for on-topic passages (0.65–0.80 range).
  Scores below 0.3 indicate marginal relevance.
- **citation_coverage** = len(cited_contexts) / len(all_contexts). Measures LLM utilisation:
  a low ratio means the LLM ignored most retrieved evidence, suggesting a poor fit.
- **semantic_coverage** = cosine(query_emb, mean_ctx_embs) from `node_critic`. Grounding
  quality at the embedding level.
- **token_coverage** = 1 − gap_fraction. Lexical breadth.
Blended: `conf = 0.30 × sq + 0.30 × cc + 0.25 × sc + 0.15 × tc`. Weights were chosen so
that retrieval quality and citation utilisation dominate (together 60 %), reflecting the
Bayesian RAG finding (Frontiers 2026) that retrieval score distributions correlate ρ = 0.94
with precision at the answer level.

**Rationale.** The new formula exposes *why* confidence is low via the `ConfidenceBar`
UI component, which renders all four signals. This is a transparency improvement aligned
with the UncertaintyRAG literature (arXiv 2025). The weights are empirically motivated but
the formula is deterministic and does not require a held-out calibration set.

**Alternatives rejected.** Monte-Carlo dropout or logit-based uncertainty (requires white-box
LLM access, breaks the provider-agnostic design); Platt scaling (requires labelled
confidence data); the existing heuristic (masked the retrieval quality signal).
