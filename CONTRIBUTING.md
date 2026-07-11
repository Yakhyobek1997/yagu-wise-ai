# Contributing to Auralynq

Thanks for your interest. Auralynq is local-first and runs at $0 by default.

## Dev setup

```bash
make setup          # creates .venv via uv, installs dev + light deps
cp .env.example .env # optional; only HUGGINGFACE_TOKEN matters for gated models
make test           # offline unit + integration (fallbacks)
make lint typecheck # ruff + mypy
```

## Ground rules

- **Lightweight core.** New runtime deps go in an optional extra in `pyproject.toml` unless they are tiny and pure-Python. Import heavy/optional deps lazily inside functions.
- **Always ship a fallback.** Any provider must degrade to a deterministic offline path so tests and the demo run without models or keys (see ADR-0003).
- **Typed + tested.** Public APIs are typed; `mypy` must stay clean. Core retrieval/agent/eval code keeps ≥80% coverage.
- **Deterministic.** Seed randomness via `auralynq.config`. No wall-clock-dependent behavior in tests.
- **Naming.** Product = Auralynq; package/CLI/services = `auralynq`. Run `make name-audit` before opening a PR.
- **Honest docs.** Never hand-write benchmark numbers; they come from `make eval`/`make bench` into `reports/`.

## Commit style

Small, verifiable units. Reference the phase or module. Run `make lint typecheck test` before pushing. Pre-commit hooks enforce ruff + basic hygiene.

## Layout

See `README.md` → Architecture and `DECISIONS.md` for the why behind each module.
