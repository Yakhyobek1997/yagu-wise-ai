"""Docs-consistency checker used by CI (.github/workflows/docs.yml) and a
pytest wrapper (tests/test_docs.py).

Checks, over a curated set of public docs:
  1. Every relative markdown link points to a file that exists.
  2. Every `make <target>` referenced in those docs exists in the Makefile.
  3. env.example documents the environment variables the getting-started /
     Hugging Face docs tell people to set.

Exits non-zero and prints every problem if anything fails. Pure stdlib; runs
offline at $0.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Public docs we hold to the link/target contract. Deliberately curated — not
# every file under docs/ (some are private research notes).
DOCS = [
    "README.md",
    "RUNNING.md",
    "docs/getting-started/no-podman.md",
    "docs/getting-started/podman.md",
    "docs/getting-started/server.md",
    "docs/getting-started/huggingface-space.md",
    "docs/getting-started/troubleshooting.md",
    "docs/evaluation.md",
    "docs/benchmarks.md",
    "examples/demo_corpus/README.md",
]

# Env vars the HF/getting-started docs promise exist; env.example must list them.
REQUIRED_ENV_VARS = [
    "AURALYNQ_HF_SPACE",
    "AURALYNQ_DEMO_MODE",
    "AURALYNQ_ALLOW_UPLOADS",
    "AURALYNQ_LLM__PROVIDER",
    "AURALYNQ_VECTOR__BACKEND",
    "AURALYNQ_EMBEDDING__PROVIDER",
    "AURALYNQ_SERVE__API_KEY",
]

_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_MAKE = re.compile(r"\bmake\s+([a-zA-Z][a-zA-Z0-9_-]*)")
_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")


def _code_spans(text: str) -> str:
    """Concatenate only the code portions of a markdown doc (fenced blocks +
    inline code), so `make sure` in prose isn't mistaken for `make <target>`."""
    parts = _FENCE.findall(text)
    parts += _INLINE_CODE.findall(text)
    return "\n".join(parts)


def _make_targets() -> set[str]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    # Match ".PHONY: name" and "name:" target definitions.
    targets: set[str] = set()
    for m in re.finditer(r"^\.PHONY:\s*(.+)$", text, re.M):
        targets.update(m.group(1).split())
    for m in re.finditer(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:", text, re.M):
        targets.add(m.group(1))
    return targets


def check_links(errors: list[str]) -> None:
    for rel in DOCS:
        doc = ROOT / rel
        if not doc.exists():
            errors.append(f"{rel}: listed in check_docs but the file is missing")
            continue
        base = doc.parent
        for link in _LINK.findall(doc.read_text(encoding="utf-8")):
            target = link.split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (base / target).resolve()
            if not resolved.exists():
                errors.append(f"{rel}: broken relative link -> {target}")


def check_make_targets(errors: list[str]) -> None:
    targets = _make_targets()
    # Env-style make invocations we intentionally skip (they're commands users
    # run, not always literal targets, e.g. "make stack-up" IS a target though).
    for rel in DOCS:
        doc = ROOT / rel
        if not doc.exists():
            continue
        code = _code_spans(doc.read_text(encoding="utf-8"))
        for tgt in _MAKE.findall(code):
            if tgt not in targets:
                errors.append(f"{rel}: references `make {tgt}` but no such Makefile target")


def check_env_example(errors: list[str]) -> None:
    env = ROOT / ".env.example"
    hf_env = ROOT / "deploy/huggingface/env.example"
    corpus = ""
    for p in (env, hf_env):
        if p.exists():
            corpus += p.read_text(encoding="utf-8")
    if not corpus:
        errors.append(".env.example and deploy/huggingface/env.example both missing")
        return
    for var in REQUIRED_ENV_VARS:
        if var not in corpus:
            errors.append(f"env example files do not document {var}")


def main() -> int:
    errors: list[str] = []
    check_links(errors)
    check_make_targets(errors)
    check_env_example(errors)
    if errors:
        print("✗ docs check FAILED:")
        for e in sorted(set(errors)):
            print(f"  - {e}")
        return 1
    print("✓ docs check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
