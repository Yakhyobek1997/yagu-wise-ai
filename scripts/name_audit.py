#!/usr/bin/env python3
"""Repository-wide naming audit (ADR-0001).

Fails if forbidden/legacy product names appear, or if the canonical strings are
missing from key files. PathRAG is allowed (algorithm name).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Legacy / off-brand product names that must never appear.
FORBIDDEN = [
    r"\bVoiceRAG\b",
    r"\bAuralynx\b",
    r"\bAuraLynq\b",  # wrong casing
    r"\bAurLynq\b",
    r"\bTalkRAG\b",
]

# Directories/files to skip.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "data",
    "models",
    "reports",
}
TEXT_EXT = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".txt",
    ".cfg",
    ".ini",
    ".env",
    ".example",
    ".Dockerfile",
}


def iter_files():
    for p in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and (p.suffix in TEXT_EXT or p.name.endswith("Dockerfile")):
            yield p


def main() -> int:
    violations: list[str] = []
    patterns = [re.compile(p) for p in FORBIDDEN]
    for path in iter_files():
        if path.name == "name_audit.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pat in patterns:
            for m in pat.finditer(text):
                line = text[: m.start()].count("\n") + 1
                violations.append(f"{path.relative_to(ROOT)}:{line}: forbidden name '{m.group()}'")

    # Canonical presence checks.
    required = {
        "pyproject.toml": ['name = "auralynq"'],
        "README.md": ["Auralynq", "Talk to Your Data"],
    }
    for rel, needles in required.items():
        fp = ROOT / rel
        if not fp.exists():
            violations.append(f"{rel}: missing (expected canonical naming)")
            continue
        content = fp.read_text(encoding="utf-8")
        for n in needles:
            if n not in content:
                violations.append(f"{rel}: missing required string {n!r}")

    if violations:
        print("✗ Name audit FAILED:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("✓ Name audit passed: Auralynq naming is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
