"""Shared provenance metadata for eval/bench reports.

Every report written to ``reports/`` should be traceable back to exactly
what produced it — see CONTRIBUTING.md: "Never hand-write benchmark
numbers." This module adds the git commit, a UTC timestamp, a hardware
summary (reusing the ModelFit hardware probe rather than duplicating
detection logic), and a caller-supplied dataset version/description.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any


def git_commit() -> str:
    """Return the current commit hash, or "unknown" outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def hardware_summary() -> dict[str, Any]:
    """Best-effort hardware summary; never raises (reports must still write)."""
    try:
        from auralynq.modelfit.hardware import probe_hardware

        return probe_hardware().to_dict()
    except Exception as e:  # pragma: no cover - defensive
        return {"error": f"hardware probe unavailable: {e}"}


def report_provenance(dataset_version: str) -> dict[str, Any]:
    """Provenance block to embed in every eval/bench report.

    ``dataset_version`` is a short, caller-supplied description of exactly
    which data produced the report (e.g. golden-set size, corpus dir names)
    — not a numeric version scheme, since the underlying datasets don't have
    one yet.
    """
    return {
        "git_commit": git_commit(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware_summary(),
        "dataset_version": dataset_version,
    }
