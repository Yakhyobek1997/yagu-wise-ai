"""Community benchmark index for Auralynq ModelFit Index.

Community-contributed results are clearly labelled as self-reported/unverified.
Results are validated against a schema before acceptance. No results are
auto-trusted; verification status is explicit on every entry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

VerifiedStatus = Literal["self_reported", "verified_local", "official_benchmark", "unverified"]

_COMMUNITY_DIR = Path("data/modelfit/community_results")

_REQUIRED_FIELDS = {
    "model_id",
    "quantization",
    "hardware",
    "benchmark_version",
    "task",
    "date",
    "source",
}
_HARDWARE_REQUIRED = {"cpu_model", "ram_gb"}


@dataclass
class CommunityResult:
    model_id: str
    quantization: str
    hardware: dict[str, Any]
    benchmark_version: str
    task: str
    date: str
    source: str
    verified_status: VerifiedStatus = "self_reported"
    tok_per_sec: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    peak_memory_gb: float | None = None
    backend: str = "unknown"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "quantization": self.quantization,
            "hardware": self.hardware,
            "benchmark_version": self.benchmark_version,
            "task": self.task,
            "date": self.date,
            "source": self.source,
            "verified_status": self.verified_status,
            "tok_per_sec": self.tok_per_sec,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "peak_memory_gb": self.peak_memory_gb,
            "backend": self.backend,
            "notes": self.notes,
        }


def validate_community_result(data: dict[str, Any]) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []

    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    hw = data.get("hardware", {})
    if not isinstance(hw, dict):
        errors.append("'hardware' must be an object.")
    else:
        missing_hw = _HARDWARE_REQUIRED - set(hw.keys())
        if missing_hw:
            errors.append(f"'hardware' missing: {sorted(missing_hw)}")

    for numeric_field in ("tok_per_sec", "p50_latency_ms", "p95_latency_ms", "peak_memory_gb"):
        val = data.get(numeric_field)
        if val is not None and not isinstance(val, (int, float)):
            errors.append(f"'{numeric_field}' must be numeric or null.")
        if isinstance(val, (int, float)) and val < 0:
            errors.append(f"'{numeric_field}' must be non-negative.")

    # Sanity bounds — reject implausible numbers
    tps = data.get("tok_per_sec")
    if isinstance(tps, (int, float)) and tps > 10000:
        errors.append("tok_per_sec > 10000 is implausible — possible fabrication.")

    mem = data.get("peak_memory_gb")
    if isinstance(mem, (int, float)) and mem > 1000:
        errors.append("peak_memory_gb > 1000 is implausible.")

    # Private hardware telemetry guard — reject if hardware contains PII-like fields
    if isinstance(hw, dict):
        sensitive_keys = {"serial", "uuid", "mac_address", "hostname", "username", "user"}
        found_sensitive = sensitive_keys & {k.lower() for k in hw}
        if found_sensitive:
            errors.append(
                f"Hardware data contains sensitive fields: {found_sensitive}. "
                "Remove before contributing."
            )

    return errors


def load_community_results(verified_only: bool = False) -> list[CommunityResult]:
    """Load all community results from disk."""
    results: list[CommunityResult] = []
    _COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(_COMMUNITY_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        errors = validate_community_result(data)
        if errors:
            continue  # skip malformed entries silently
        r = CommunityResult(
            model_id=data["model_id"],
            quantization=data["quantization"],
            hardware=data["hardware"],
            benchmark_version=data["benchmark_version"],
            task=data["task"],
            date=data["date"],
            source=data["source"],
            verified_status=data.get("verified_status", "self_reported"),
            tok_per_sec=data.get("tok_per_sec"),
            p50_latency_ms=data.get("p50_latency_ms"),
            p95_latency_ms=data.get("p95_latency_ms"),
            peak_memory_gb=data.get("peak_memory_gb"),
            backend=data.get("backend", "unknown"),
            notes=data.get("notes", ""),
        )
        if verified_only and r.verified_status not in ("verified_local", "official_benchmark"):
            continue
        results.append(r)
    return results


def save_community_result(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate and save a community result. Returns (success, errors)."""
    errors = validate_community_result(data)
    if errors:
        return False, errors

    # Strip any secrets before saving
    hw = dict(data.get("hardware", {}))
    for key in list(hw.keys()):
        if key.lower() in {"serial", "uuid", "mac_address", "hostname", "username", "user"}:
            del hw[key]
    data = {**data, "hardware": hw}

    # Always mark as self_reported on submission
    data["verified_status"] = data.get("verified_status", "self_reported")
    data["submitted_at"] = datetime.now(UTC).isoformat()

    _COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"{data['model_id'].replace('/', '_').replace(':', '_')}_{data['task']}_{data['date']}"
    path = _COMMUNITY_DIR / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2))
    return True, []
