"""Tests for the enhanced accuracy features: will-it-run verdicts, live free-VRAM
awareness, and cross-platform CPU/GPU detection."""

from __future__ import annotations

from types import SimpleNamespace

import auralynq.modelfit.hardware as hw_mod
import pytest
from auralynq.modelfit.resource_estimator import estimate_resources

# ── Verdict logic ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "params_b,quant,vram,ram,expected_verdict,expected_fits",
    [
        (8.0, "q4_k", 24.0, 64.0, "runs_great", True),  # loads of headroom
        (8.0, "q4_k", 6.0, 32.0, "runs_ok", True),  # tight but in VRAM
        (70.0, "q4_k", 24.0, 128.0, "runs_offload", True),  # spills to RAM, runs
        (70.0, "fp16", 8.0, 16.0, "too_big", False),  # 140 GB, cannot fit
        (3.0, "q4_k", 0.0, 32.0, "runs_cpu", True),  # CPU-only, comfortable
        (13.0, "q4_k", 0.0, 12.0, "runs_cpu_tight", True),  # CPU-only, low headroom
    ],
)
def test_verdict_matrix(params_b, quant, vram, ram, expected_verdict, expected_fits):
    e = estimate_resources("m", params_b, quant, vram, ram, context_tokens=8192)
    assert e.verdict == expected_verdict
    assert e.fits is expected_fits


def test_runs_great_fits_in_vram_and_headroom():
    e = estimate_resources("m", 8.0, "q4_k", 24.0, 64.0)
    assert e.fits_in_vram is True
    assert e.requires_cpu_offload is False
    assert e.headroom_gb > 10


def test_offload_flags_and_not_fully_in_vram():
    e = estimate_resources("m", 70.0, "q4_k", 24.0, 128.0)
    assert e.requires_cpu_offload is True
    assert e.fits_in_vram is False
    assert any("offload" in w.lower() for w in e.warnings)


def test_new_fields_in_dict():
    d = estimate_resources("m", 8.0, "q4_k", 24.0, 64.0).to_dict()
    for k in ("verdict", "fits_in_vram", "requires_cpu_offload", "headroom_gb", "vram_free_gb"):
        assert k in d


def test_free_vram_used_for_live_headroom_and_warning():
    # Model fits the 24 GB card by capacity, but only 3 GB is free right now.
    e = estimate_resources(
        "m", 8.0, "q4_k", 24.0, 64.0, context_tokens=4096, available_vram_free_gb=3.0
    )
    assert e.vram_free_gb == 3.0
    # headroom is computed against *free* VRAM, so it should be negative here.
    assert e.headroom_gb < 0
    assert any("free right now" in w for w in e.warnings)


def test_kv_cache_grows_with_context():
    short = estimate_resources("m", 8.0, "q4_k", 24.0, 64.0, context_tokens=2048)
    long = estimate_resources("m", 8.0, "q4_k", 24.0, 64.0, context_tokens=32768)
    assert long.estimated_vram_gb > short.estimated_vram_gb


# ── CPU detection (cross-platform) ────────────────────────────────────────────


def test_read_proc_cpuinfo_parses(monkeypatch, tmp_path):
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(
        "processor\t: 0\n"
        "model name\t: Intel(R) Xeon(R) Silver 4210\n"
        "flags\t\t: fpu vme avx avx2 avx512f sse4_2\n"
        "core id\t\t: 0\n"
        "processor\t: 1\n"
        "core id\t\t: 1\n"
    )
    import builtins

    real_open = builtins.open

    def fake_open(path, *a, **k):
        if path == "/proc/cpuinfo":
            return real_open(cpuinfo, *a, **k)
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", fake_open)
    model, cores, flags = hw_mod._read_proc_cpuinfo()
    assert "Xeon" in model
    assert cores == 2
    assert "avx2" in flags and "avx512f" in flags


def test_detect_cpu_linux_reports_avx(monkeypatch):
    monkeypatch.setattr(hw_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hw_mod.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(hw_mod, "_read_proc_cpuinfo", lambda: ("Test CPU", 8, {"avx2", "avx512f"}))
    model, _phys, _log, arch, avx2, avx512 = hw_mod._detect_cpu()
    assert model == "Test CPU"
    assert arch == "x86_64"
    assert avx2 is True
    assert avx512 is True


def test_probe_warns_on_missing_avx2(monkeypatch):
    monkeypatch.setattr(hw_mod, "_detect_cpu", lambda: ("Old CPU", 4, 4, "x86_64", False, False))
    monkeypatch.setattr(hw_mod, "_detect_gpus", lambda: ([], False, None, False, False))
    monkeypatch.setattr(hw_mod, "_detect_ram_gb", lambda: 16.0)
    monkeypatch.setattr(hw_mod, "_detect_disk_free_gb", lambda: 200.0)
    monkeypatch.setattr(hw_mod, "_detect_ollama", lambda: (False, None))
    monkeypatch.setattr(hw_mod, "_detect_hf", lambda: (False, None))
    hw = hw_mod.probe_hardware()
    assert hw.avx2 is False
    assert any("AVX2" in w for w in hw.warnings)


# ── NVIDIA free/used VRAM ─────────────────────────────────────────────────────


def test_detect_nvidia_parses_free_used(monkeypatch):
    smi = SimpleNamespace(
        returncode=0,
        stdout="NVIDIA RTX 3090, 24576, 20480, 4096\nNVIDIA RTX 3090, 24576, 24000, 576\n",
    )

    def fake_run(cmd, *a, **k):
        return smi

    monkeypatch.setattr(hw_mod.subprocess, "run", fake_run)
    gpus = hw_mod._detect_nvidia_gpus()
    assert len(gpus) == 2
    assert gpus[0].vram_gb == 24.0
    assert gpus[0].vram_free_gb == 20.0
    assert gpus[0].vram_used_gb == 4.0


def test_total_vram_free_property():
    from auralynq.modelfit.hardware import GPUInfo, HardwareProfile

    hw = HardwareProfile(
        gpus=[
            GPUInfo("nvidia", "A", 11.0, "cuda", 0, vram_free_gb=5.0),
            GPUInfo("nvidia", "B", 11.0, "cuda", 1, vram_free_gb=10.0),
        ]
    )
    assert hw.total_vram_free_gb == 15.0


def test_total_vram_free_none_when_unreported():
    from auralynq.modelfit.hardware import GPUInfo, HardwareProfile

    hw = HardwareProfile(gpus=[GPUInfo("apple", "M3", 24.0, "metal", 0, integrated=True)])
    assert hw.total_vram_free_gb is None


# ── Apple Silicon unified-memory tiering ──────────────────────────────────────


@pytest.mark.parametrize(
    "ram,expected_fraction",
    [(8.0, 0.65), (16.0, 0.70), (64.0, 0.75)],
)
def test_apple_silicon_unified_memory_tiers(monkeypatch, ram, expected_fraction):
    monkeypatch.setattr(hw_mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hw_mod, "_detect_ram_gb", lambda: ram)
    profiler = SimpleNamespace(returncode=0, stdout="Chipset Model: Apple M3 Max\n")

    def fake_run(cmd, *a, **k):
        return profiler

    monkeypatch.setattr(hw_mod.subprocess, "run", fake_run)
    gpus = hw_mod._detect_apple_silicon()
    assert len(gpus) == 1
    assert gpus[0].integrated is True
    assert gpus[0].name == "Apple M3 Max"
    assert gpus[0].vram_gb == round(ram * expected_fraction, 1)
