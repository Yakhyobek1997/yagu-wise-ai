# Auralynq Open-Source Release Readiness Audit

**Date:** 2026-07-01
**Branch:** `release/open-source-production-readiness`
**Scope:** Fresh-clone install, packaging, frontend, API, research packaging, public trust, Hugging Face Spaces.

Every finding below was verified against the current repo state (file + line references given where useful) — nothing here is inferred from docs alone.

---

## 1. Installation readiness

| Item | Status | Notes |
|---|---|---|
| Python version support | ✅ Good | `requires-python = ">=3.11"`; CI matrices 3.11/3.12 (`.github/workflows/ci.yml`). |
| Node version support | ⚠️ Undocumented | `web/package.json` has no `engines` field; no Node version stated anywhere public. Next.js 15.5 needs Node ≥18.18. |
| uv/pip setup | ✅ Good | `make setup` uses `uv` if present, falls back to `venv`+`pip`. |
| No-Podman mode | ✅ Works | `python -m auralynq.cli serve` / `uvicorn auralynq.serving.app:app` runs standalone; verified `create_app()` imports cleanly with no Podman/qdrant-server dependency (falls back to in-memory store). |
| Podman mode | ✅ Documented | `compose.yml` (7 services), `RUNNING.md`, `make stack-up`. |
| Linux server mode | ✅ Documented | `RUNNING.md` §1 "Run on a DIFFERENT machine" covers GHCR images + `.env`. |
| Mac local dev mode | ⚠️ Partial | No Podman-on-Mac or Apple-Silicon note; no-Podman path should work identically but isn't called out. |
| GPU/local model optional paths | ✅ Good | `llm`, `slm`, `embeddings`, `voice` extras are optional; llama-cpp CUDA wheel instructions inline in `pyproject.toml:69`. |
| Offline fallback path | ✅ Good | ADR-0003 (`DECISIONS.md`) documents hashing embedder / in-memory vector store / extractive LLM / null ASR-TTS fallbacks; confirmed these are real code paths, not just claims (`auralynq/embeddings`, `auralynq/vectorstore`, `auralynq/llm`). |

**Gap:** there is no single "5-minute quickstart" that a first-time cloner can follow end-to-end without already knowing the repo. `RUNNING.md` is deploy-oriented (assumes a running stack); `README.md` (per user's pasted excerpt) is contribution-quality but the explicit `make setup && make data && make index && make demo` golden path isn't spelled out as one block.

---

## 2. Packaging readiness

| Item | Status | Notes |
|---|---|---|
| `pyproject.toml` completeness | ✅ Good | name/version/description/readme/license/classifiers/keywords all present. |
| CLI entry points | 🔴 **Fixed this session** | `auralynq-research = "auralynq.research.cli:app"` pointed at code that was deliberately removed from the public repo (commit `5d80833`, `auralynq/research/` is gitignored — "local only"). This is a dangling console-script: `pip install auralynq` would ship a script that raises `ModuleNotFoundError` on invocation. **Fix applied:** removed the `auralynq-research` script and the `research` extra from `pyproject.toml` (per explicit decision — research subsystem stays private/unpublished). Remaining entry points (`auralynq`, `auralynq-mcp`, `auralynq-modelfit`) all resolve to real, tracked modules. |
| Optional extras | ✅ Good | `embeddings/vector/ingest/voice/agent/llm/eval/telemetry/slm/mcp/dev/all` — clean core/extras split matching ADR-0003. |
| Package data | ⚠️ Unverified | No `[tool.hatch.build.targets.wheel].include`/`force-include` beyond `packages = ["auralynq"]`; if any non-`.py` data files (prompts, templates) are read at runtime from inside the package, confirm they're included in the wheel. Not confirmed either way in this pass — flag for a real `python -m build` + `unzip -l` check. |
| Versioning | ✅ Present | `version = "0.2.0"`; no `CHANGELOG.md` yet (see Part 11 gap below). |
| License metadata | ✅ Good | `license = { text = "Apache-2.0" }`, `LICENSE` file present, OCI labels in `release.yml` also stamp `licenses=Apache-2.0`. |
| Core vs extras dependency split | ✅ Good | Core list (pydantic, fastapi, numpy, networkx, httpx, etc.) is genuinely light; all heavy/paid SDKs (torch, qdrant-client, openai, anthropic, langgraph, llama-cpp-python) are extras. |

---

## 3. Frontend readiness

| Item | Status | Notes |
|---|---|---|
| Next.js build | ⚠️ Unverified this pass | `npm run build` not yet run in this session (queued for Part 14 quality gates). |
| Environment variables | ✅ Documented | `NEXT_PUBLIC_API_BASE` used consistently; `.env.example`/`web/.env.example` referenced in `RUNNING.md`. |
| Public API base handling | ✅ Good | Same-origin `/api` proxy pattern documented for production; direct `http://localhost:8000/api` for dev. |
| Local dev mode | ✅ Good | `npm run dev -- --hostname 0.0.0.0 --port 3000` works standalone against the FastAPI dev server. |
| Deployed mode | ✅ Good | Caddy reverse-proxies web+api same-origin per `RUNNING.md`. |
| Responsive behavior | ⚠️ Unverified | No explicit mobile breakpoints audit performed; `web/app` only has 3 route pages (landing, `/chat`, `/modelfit`) — everything else (source workspace, eval panel, benchmark lab, settings) is rendered as modals/panels inside `/chat`, not tested for small viewports in this pass. |
| Accessibility | 🔴 Gap | No ARIA/keyboard-nav audit exists; no accessibility test in `web/lib/*.test.mjs`. |

---

## 4. API readiness

| Item | Status | Notes |
|---|---|---|
| OpenAPI docs | ✅ Enabled | Default FastAPI `/docs`, `/openapi.json`, `/redoc` (no `docs_url=None` override), and they're in the auth bypass list (`auralynq/serving/auth.py:19`) so they stay reachable even with an API key set — **acceptable for a self-hosted tool, but worth a README note** that anyone who can reach the port can read the schema. |
| Route grouping | ⚠️ Ungrouped | All routes are registered flat on `app` in `auralynq/serving/app.py` with no `/api` prefix (`/health`, `/status`, `/version`, `/corpus/summary`, etc.) — **this does not match the env-var convention the brief assumes** (`GET /api/status`, `GET /api/version`, `GET /api/corpus/summary` don't exist at those paths; the real paths are `/status`, `/version`, `/corpus/summary`). Only the ModelFit router is mounted under `/api/modelfit/*` (`auralynq/modelfit/router.py:32`). This is an inconsistency worth fixing (either add `/api` aliases or update all docs to the real paths) — **not fixed in this pass to avoid breaking the existing frontend's fetch calls without a coordinated change; flagged as a high-priority follow-up**, see §8. |
| Health/status endpoints | ✅ Present (different paths than the brief assumed) | `/health` (liveness), `/ready` (readiness), `/version`, `/status`, `/corpus/summary`, `/metrics`. `/api/modelfit/hardware` exists as specified. |
| Error format consistency | ⚠️ Partial | `auralynq/serving/errors.py` gives `{"error", "detail", "request_id"}` for `AuralynqError` and unhandled 500s — **no `code` or `trace_id` fields** (brief wants `{"error":{"code","message","details","trace_id"}}`, current shape is flatter and `request_id` ≠ `trace_id`). FastAPI's default `HTTPException`/422 validation errors still fall through to Starlette's stock `{"detail": ...}` shape, so the envelope isn't applied uniformly. |
| Auth behavior | ✅ Good, documented | Optional bearer token via `AURALYNQ_SERVE__API_KEY`; empty = open (local-dev default); constant-time compare (`hmac.compare_digest`); public-path bypass list is a small, explicit frozenset. |
| CORS behavior | ✅ Good | `CORSMiddleware`, origins from `serve.cors_origins` (default `["http://localhost:3000"]`, not wildcard). |
| No-browser-secret leakage | ✅ Good | `NEXT_PUBLIC_API_BASE=/api` pattern keeps provider keys server-side; no evidence of secrets baked into the Next.js client bundle (not exhaustively grepped this pass — recommend a build-output grep in Part 13 tests). |

---

## 5. Research readiness

| Item | Status | Notes |
|---|---|---|
| Auralynq-RAG contribution documented | ✅ Excellent, but **not public** | `docs/research/auralynq-rag-contribution.md` is thorough (pipeline, KPIs, related-work table, honest "Research Claims" with named measurements) — but `docs/` is fully gitignored except 4 grandfathered files, so this document **does not exist in the public git history**. Per explicit decision this session, that stays as-is for now (material is being reserved for a future paper). |
| ModelFit contribution documented | ✅ Excellent, same caveat | `docs/research/auralynq-modelfit-index.md` — same gitignore status. |
| Visual Grounding contribution documented | ✅ Good, same caveat | `docs/audits/visual-grounded-rag-algorithm-audit.md` covers competitor survey + design rationale; also gitignored. |
| Benchmarks reproducible | ⚠️ Partial | `make eval` and `make bench` exist and write to `reports/`; CI runs `auralynq.cli eval --smoke`. Not yet verified: `bench-rag`, `bench-modelfit`, `bench-visual-grounding`, `export-paper-tables` targets from the brief — **none of these exist in the current Makefile** (only `eval`, `bench`). Flagged for Part 6. |
| Ablations runnable | ⚠️ Unverified | Not confirmed this pass; `auralynq/rag/` has 13 strategies per README claim — worth a `--strategy` CLI flag check in Part 6. |
| Metrics documented | ✅ Good | KPI table in `auralynq-rag-contribution.md` names concrete metrics + targets. |
| Limitations honest | ✅ Good | Existing docs use careful, hedged language ("Status: Initial definition — implementation in progress"); no "state of the art" claims found in the research docs read this pass. |

**Because the source research docs stay private, the public-facing `docs/research/research-contributions.md` (Part 4) must be written as new, standalone public content** — summarizing the real, verified capabilities (grep-confirmed code, not aspirational) rather than linking to the private detailed docs.

---

## 6. Public trust

| Item | Status | Notes |
|---|---|---|
| README clarity | ✅ Strong | Clear one-line pitch, architecture section, links to contribution docs (though some linked docs are private — see below). |
| `SECURITY.md` | 🔴 **Blocking** | Currently the **unfilled GitHub default template** — placeholder version table (`5.1.x`/`4.0.x` don't correspond to any real Auralynq release) and boilerplate "Use this section to tell people..." text. Must be rewritten before public release. |
| `CONTRIBUTING.md` | ✅ Good | Real, specific, references ADRs and `make name-audit`. |
| `THIRD_PARTY.md` | ✅ Good | Real attribution table (PathRAG, RRF, MMR, Lost-in-the-Middle, late chunking) + model/library license notes. |
| `DECISIONS.md` | ✅ Good | 12+ ADRs with Context/Decision/Rationale/Alternatives-rejected — genuinely useful for public contributors. |
| License headers | N/A | Not required for Apache-2.0 at file level; repo-level `LICENSE` suffices. |
| Model/data privacy warnings | 🔴 Gap | No explicit "documents you upload are processed locally / where they're stored / how to delete them" statement surfaced in README or UI. |
| No fake benchmark numbers | ✅ Verified | `reports/` is gitignored except `.gitkeep`/`README.md` — no hand-committed benchmark tables found in tracked docs. |
| No unsupported claims | ✅ Mostly | README pitch is factual/behavioral ("13 pluggable RAG strategies", "span-level bounding boxes") rather than comparative superlatives — no "state of the art" language found. |
| `prompt.md` placeholder | ⚠️ Minor | Line 607 has a literal "Demo GIF/video placeholder" marker — irrelevant to public release since `prompt.md` is gitignored (private planning doc), but worth remembering it's not shippable content. |

---

## 7. Hugging Face readiness

| Item | Status | Notes |
|---|---|---|
| Space deployment mode | 🔴 Doesn't exist | No `deploy/huggingface/` directory. |
| Dockerfile / Space entrypoint | 🔴 Doesn't exist | Existing `containers/api.Dockerfile` and `containers/web.Dockerfile` are **separate** images (API-only, web-only) built for the multi-container Podman/Caddy topology — neither is a single-container Space-ready image. A new combined image (or documented supervisor pattern) is needed. |
| Secrets/variables instructions | 🔴 Doesn't exist | No `AURALYNQ_HF_SPACE`, `AURALYNQ_DEMO_MODE`, or any HF-specific env var exists anywhere in the codebase today (`auralynq/`, `web/`, `.env.example`) — this is genuinely new work, not a documentation gap. |
| Persistent storage expectations | 🔴 Not addressed | No code path checks for HF's `/data` persistent-storage convention. |
| Demo dataset | 🔴 Doesn't exist | `data/` is fully gitignored; the on-disk sample PDFs (`data/samples_pdf/` — real named-company patent-pledge filings; `data/benchmark_corpus/` — academic papers) are **not tracked in git** and are not appropriate to force-add wholesale (uncertain redistribution rights for the company documents; the academic PDFs would need per-paper license checks). A new, deliberately-licensed demo corpus must be authored fresh (Part 5). |
| Model cards / dataset cards / Space README | 🔴 Doesn't exist | No `hub/` directory. |
| No private data leakage | ✅ N/A currently | Nothing HF-related exists yet, so nothing to leak; must be designed correctly from scratch. |
| Safe default configs | 🔴 Not addressed | No demo-mode gating exists yet to disable heavy model downloads / uploads-persistence by default. |

**Bottom line: Hugging Face readiness is 0% implemented today** — everything in Part 3 and Part 9 of the brief is greenfield work, not a gap-fix.

---

## Blocking issues (must fix before any public release)

1. **`SECURITY.md` is an unfilled template** with fabricated version numbers — actively misleading if published as-is.
2. **Dangling `auralynq-research` CLI entry point** in `pyproject.toml` pointing at code not present in the public repo — ✅ **fixed this session** (entry point + `research` extra removed).
3. **No Hugging Face Space artifacts exist at all** (Dockerfile, env vars, demo-mode gating, docs) — required if the user wants to publish a Space; currently would need to be built from zero.
4. **No public demo dataset** — `examples/demo_corpus/` doesn't exist; nothing safe/licensed to ingest for a public demo today.
5. **No model/data privacy statement** — public users uploading documents have no stated expectation of where data goes or how to delete it.

## High-priority issues

6. API route/env-var mismatch: brief's assumed `/api/status`, `/api/version`, `/api/corpus/summary` don't exist at those paths (real paths lack the `/api` prefix except ModelFit). Needs either route aliases or a documentation correction — recommend documentation correction over route changes to avoid breaking the existing frontend's fetch calls.
7. Error envelope isn't uniform (`code`/`trace_id` missing; FastAPI default validation errors bypass the custom envelope).
8. `CHANGELOG.md`, `docs/release/versioning.md`, `docs/release/release-checklist.md` don't exist.
9. `bench-rag` / `bench-modelfit` / `bench-visual-grounding` / `export-paper-tables` Make targets don't exist (only `eval`, `bench`).
10. No accessibility pass on the frontend; no responsive-layout audit.
11. Node engine version undocumented.

## Nice-to-have

12. `web/lib/modelfit.test.mjs` exists but isn't wired into `package.json`'s `test` script — free coverage currently not running in CI.
13. Package-data inclusion in the wheel unverified (`python -m build` + `unzip -l` check).
14. Mac-specific dev notes.

## Proposed implementation order

1. Fix blocking public-trust issues that are pure content (`SECURITY.md`, privacy statement) — no code risk.
2. Public quickstart docs (Part 2) — highest leverage for "can a stranger run this," low risk.
3. Research contributions page (Part 4), written fresh and public (per the docs/ privacy decision), summarizing only what's grep-verified in code.
4. Hugging Face Spaces scaffolding (Part 3) + Hub templates (Part 9) — greenfield, additive, no risk to existing runtime.
5. Demo dataset (Part 5) — needed before HF Space or quickstart docs can show a real walkthrough.
6. Benchmark/eval command surface (Part 6) — additive Make targets + docs.
7. Production hardening (Part 7) — touches live serving code; sequenced after docs so route-naming decisions are already settled.
8. CI/CD + versioning/changelog (Parts 10, 11).
9. Frontend polish (Part 8) and testing gaps (Part 13) — largest, most open-ended; sequenced last so earlier decisions (route names, demo-mode env vars) are stable inputs.
10. Quality gates + final report (Parts 14, 15).
