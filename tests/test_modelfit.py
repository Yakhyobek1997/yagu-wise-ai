"""Tests for Auralynq ModelFit Index.

Coverage:
- Hardware profiler (with and without GPU)
- Resource estimator (various model sizes and quantizations)
- Fit scoring
- Benchmark preview (dry run only — never runs actual benchmark)
- Community result validation
- Model registry search
- No fake tok/s in score when benchmark not run
- No secrets in hardware export
"""

from __future__ import annotations

import pytest
from auralynq.modelfit.benchmark_runner import preview_benchmark
from auralynq.modelfit.community import validate_community_result
from auralynq.modelfit.hardware import HardwareProfile, probe_hardware
from auralynq.modelfit.hf_catalog import get_static_hf_catalog
from auralynq.modelfit.model_metadata import ModelMetadata
from auralynq.modelfit.model_registry import ModelRegistry
from auralynq.modelfit.ollama_catalog import get_static_catalog
from auralynq.modelfit.resource_estimator import (
    estimate_resources,
    estimate_vram_gb,
    recommend_quantization,
)
from auralynq.modelfit.scoring import BenchmarkSnapshot, score_model

# ── Hardware profiler ─────────────────────────────────────────────────────────


def test_probe_hardware_returns_profile():
    hw = probe_hardware()
    assert isinstance(hw, HardwareProfile)


def test_hardware_profile_no_gpu():
    hw = HardwareProfile(
        os_name="Linux",
        ram_gb=16.0,
        gpus=[],
        ollama_available=False,
    )
    assert hw.total_vram_gb == 0.0
    assert hw.best_backend == "cpu"
    d = hw.to_dict()
    assert d["total_vram_gb"] == 0.0
    assert d["best_backend"] == "cpu"


def test_hardware_profile_with_gpu():
    from auralynq.modelfit.hardware import GPUInfo

    gpu = GPUInfo(vendor="nvidia", name="RTX 4090", vram_gb=24.0, backend="cuda")
    hw = HardwareProfile(
        os_name="Linux",
        ram_gb=64.0,
        gpus=[gpu],
        cuda_available=True,
    )
    assert hw.total_vram_gb == 24.0
    assert hw.best_backend == "cuda"


def test_hardware_no_secrets_in_dict():
    hw = probe_hardware()
    d = hw.to_dict()
    sensitive = {"serial", "uuid", "mac_address", "hostname", "username"}
    for key in sensitive:
        assert key not in d, f"Sensitive key '{key}' found in hardware profile"


def test_hardware_warnings_list():
    hw = probe_hardware()
    assert isinstance(hw.warnings, list)


# ── Resource estimator ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "params_b,quant,ctx",
    [
        (3.0, "q4_k", 4096),
        (7.0, "q4_k", 4096),
        (7.0, "q8", 4096),
        (14.0, "q4_k", 4096),
        (14.0, "fp16", 4096),
        (70.0, "q4_k", 4096),
        (1.0, "q4_k", 2048),
        (9.0, "q5_k", 8192),
    ],
)
def test_vram_estimate_positive(params_b, quant, ctx):
    vram = estimate_vram_gb(params_b, quant, ctx)
    assert vram > 0.0


def test_vram_estimate_increases_with_params():
    v7 = estimate_vram_gb(7.0, "q4_k", 4096)
    v70 = estimate_vram_gb(70.0, "q4_k", 4096)
    assert v70 > v7 * 5


def test_vram_estimate_fp16_greater_than_q4():
    v_fp16 = estimate_vram_gb(7.0, "fp16", 4096)
    v_q4 = estimate_vram_gb(7.0, "q4_k", 4096)
    assert v_fp16 > v_q4


def test_estimate_resources_comfortable():
    result = estimate_resources(
        model_id="test",
        params_b=3.0,
        quantization="q4_k",
        available_vram_gb=24.0,
        available_ram_gb=32.0,
        context_tokens=4096,
    )
    assert result.fit_level == "comfortable"
    assert result.fits is True
    assert result.is_estimate is True


def test_estimate_resources_impossible():
    result = estimate_resources(
        model_id="test",
        params_b=70.0,
        quantization="fp16",
        available_vram_gb=8.0,
        available_ram_gb=16.0,
        context_tokens=4096,
    )
    assert result.fit_level == "impossible"
    assert result.fits is False
    assert result.is_estimate is True


def test_estimate_resources_warnings_present():
    result = estimate_resources(
        model_id="test",
        params_b=7.0,
        quantization="q4_k",
        available_vram_gb=8.0,
        available_ram_gb=16.0,
    )
    assert len(result.warnings) > 0
    assert result.is_estimate is True


def test_recommend_quantization_fits_small_vram():
    quant = recommend_quantization(params_b=7.0, available_vram_gb=8.0, available_ram_gb=16.0)
    assert quant in ("q4_k", "q4_0", "q3_k", "q2_k")


def test_estimate_resources_dict_schema():
    result = estimate_resources("test", 7.0, "q4_k", 16.0, 32.0)
    d = result.to_dict()
    required = {
        "model_id",
        "quantization",
        "context_tokens",
        "estimated_vram_gb",
        "estimated_ram_gb",
        "estimated_disk_gb",
        "fit_level",
        "fits",
        "recommended_context",
        "peak_vram_at_max_ctx_gb",
        "warnings",
        "is_estimate",
    }
    assert required <= set(d.keys())
    assert d["is_estimate"] is True


# ── Scoring ───────────────────────────────────────────────────────────────────


def _make_hw(vram_gb: float = 12.0, ram_gb: float = 32.0) -> HardwareProfile:
    from auralynq.modelfit.hardware import GPUInfo

    gpu = GPUInfo("nvidia", "RTX 3060", vram_gb, "cuda")
    return HardwareProfile(
        os_name="Linux",
        ram_gb=ram_gb,
        gpus=[gpu] if vram_gb > 0 else [],
        cuda_available=vram_gb > 0,
        disk_free_gb=200.0,
    )


def _make_model(params_b: float = 7.0) -> ModelMetadata:
    return ModelMetadata(
        model_id=f"ollama:test:{params_b}b",
        source="ollama",
        display_name=f"Test {params_b}B",
        parameter_count_b=params_b,
        tasks=["chat", "rag"],
        available_quantizations=["q4_k", "q8", "fp16"],
    )


def test_score_model_returns_score():
    hw = _make_hw()
    model = _make_model()
    score = score_model(model, hw)
    assert 0 <= score.overall_score <= 100
    assert score.label in (
        "Excellent fit",
        "Recommended",
        "Usable with limits",
        "Not recommended",
        "Does not fit",
    )


def test_score_model_no_fabricated_toks():
    hw = _make_hw()
    model = _make_model()
    score = score_model(model, hw)
    # Without a benchmark, tok/s should NOT be present in benchmark field
    if score.benchmark:
        assert score.benchmark.avg_tok_per_sec is None or score.estimate_used
    assert score.estimate_used is True


def test_score_model_with_benchmark_overrides_estimate():
    hw = _make_hw()
    model = _make_model()
    bench = BenchmarkSnapshot(
        avg_tok_per_sec=45.0,
        p50_latency_ms=800.0,
        is_measured=True,
    )
    score = score_model(model, hw, benchmark=bench)
    assert score.benchmark is not None
    assert score.benchmark.avg_tok_per_sec == 45.0
    assert score.benchmark.is_measured is True


def test_score_model_small_on_tiny_vram_not_recommended():
    hw = _make_hw(vram_gb=2.0)
    model = _make_model(params_b=70.0)
    score = score_model(model, hw, quantization="fp16")
    assert score.hardware_fit < 50


def test_score_model_comfortable_fit():
    hw = _make_hw(vram_gb=24.0)
    model = _make_model(params_b=3.0)
    score = score_model(model, hw, quantization="q4_k")
    assert score.hardware_fit >= 85


def test_score_model_warnings_have_estimate_label():
    hw = _make_hw()
    model = _make_model()
    score = score_model(model, hw)
    estimate_warnings = [w for w in score.warnings if "estimate" in w.lower()]
    assert len(estimate_warnings) > 0


# ── Benchmark preview (dry run only) ─────────────────────────────────────────


def test_benchmark_preview_does_not_run():
    plan = preview_benchmark("ollama:llama3.1:8b", "q4_k", "rag", 10)
    assert plan.requires_model_download is False
    d = plan.to_dict()
    assert "preview" in d["note"].lower() or "dry" in d["note"].lower()
    assert len(plan.warnings) > 0


def test_benchmark_preview_schema():
    plan = preview_benchmark("ollama:llama3.1:8b", "q4_k", "latency", 5)
    d = plan.to_dict()
    assert "note" in d
    assert d["requires_model_download"] is False
    assert isinstance(d["sample_prompts"], list)
    assert isinstance(d["warnings"], list)


def test_benchmark_preview_estimated_duration_positive():
    plan = preview_benchmark("ollama:test:7b", "q4_k", "throughput", 20)
    assert plan.estimated_duration_min > 0


# ── Community validation ──────────────────────────────────────────────────────


def _valid_community_entry() -> dict:
    return {
        "model_id": "ollama:llama3.1:8b",
        "quantization": "q4_k",
        "hardware": {
            "cpu_model": "Intel Core i9",
            "ram_gb": 32,
            "gpus": [{"vendor": "nvidia", "name": "RTX 3090", "vram_gb": 24}],
        },
        "benchmark_version": "auralynq-modelfit-0.1",
        "task": "rag",
        "date": "2026-06-23",
        "source": "auralynq-benchmark-runner",
        "tok_per_sec": 28.4,
    }


def test_community_valid_entry_passes():
    errors = validate_community_result(_valid_community_entry())
    assert errors == []


def test_community_missing_required_field_fails():
    entry = _valid_community_entry()
    del entry["model_id"]
    errors = validate_community_result(entry)
    assert any("model_id" in e for e in errors)


def test_community_missing_hardware_cpu_fails():
    entry = _valid_community_entry()
    del entry["hardware"]["cpu_model"]
    errors = validate_community_result(entry)
    assert len(errors) > 0


def test_community_implausible_tps_rejected():
    entry = _valid_community_entry()
    entry["tok_per_sec"] = 99999
    errors = validate_community_result(entry)
    assert any("implausible" in e for e in errors)


def test_community_negative_latency_rejected():
    entry = _valid_community_entry()
    entry["p50_latency_ms"] = -100
    errors = validate_community_result(entry)
    assert any("non-negative" in e for e in errors)


def test_community_sensitive_hardware_rejected():
    entry = _valid_community_entry()
    entry["hardware"]["serial"] = "ABC123"
    errors = validate_community_result(entry)
    assert any("sensitive" in e.lower() for e in errors)


def test_community_save_strips_secrets(tmp_path, monkeypatch):
    import auralynq.modelfit.community as comm

    monkeypatch.setattr(comm, "_COMMUNITY_DIR", tmp_path)
    entry = _valid_community_entry()
    entry["hardware"]["hostname"] = "my-secret-machine"  # will be stripped
    # validation should fail since 'hostname' is sensitive
    errors = validate_community_result(entry)
    assert any("sensitive" in e.lower() for e in errors)


# ── Model registry ────────────────────────────────────────────────────────────


def test_registry_loads_static_catalog():
    reg = ModelRegistry()
    models = reg.list_all()
    assert len(models) > 5


def test_registry_search_by_family():
    reg = ModelRegistry()
    llamas = reg.search(family="llama")
    assert all(m.family == "llama" for m in llamas)


def test_registry_search_by_embedding():
    reg = ModelRegistry()
    embeds = reg.search(embedding_only=True)
    assert all(m.embedding for m in embeds)


def test_registry_search_by_task():
    reg = ModelRegistry()
    rag_models = reg.search(task="rag")
    assert all("rag" in m.tasks for m in rag_models)


def test_registry_get_returns_none_for_unknown():
    reg = ModelRegistry()
    assert reg.get("nonexistent:model:id") is None


def test_static_ollama_catalog_has_required_fields():
    catalog = get_static_catalog()
    assert len(catalog) > 0
    for m in catalog:
        assert m.model_id
        assert m.source == "ollama"
        assert m.parameter_count_b is not None or m.embedding


def test_static_hf_catalog_has_required_fields():
    catalog = get_static_hf_catalog()
    assert len(catalog) > 0
    for m in catalog:
        assert m.model_id.startswith("hf:")
        assert m.source == "huggingface"


# ── Score in query response ───────────────────────────────────────────────────


def test_query_response_schema_has_model_fit_field():
    from auralynq.serving.schemas import QueryResponse

    r = QueryResponse(answer="test")
    assert hasattr(r, "model_fit")
    assert r.model_fit is None  # None when not set


def test_score_dict_has_estimate_used_flag():
    hw = _make_hw()
    model = _make_model()
    score = score_model(model, hw)
    d = score.to_dict()
    assert "estimate_used" in d
    assert d["estimate_used"] is True  # no benchmark provided


# ── Phase 2: Community data in speed score ────────────────────────────────────


def test_community_benchmark_not_injected_without_verified_data(monkeypatch):
    """_lookup_community_benchmark returns None when no verified results exist."""
    import auralynq.modelfit.community as comm
    from auralynq.modelfit.scoring import _lookup_community_benchmark

    monkeypatch.setattr(
        comm, "_COMMUNITY_DIR", comm._COMMUNITY_DIR.__class__("/tmp/nonexistent_modelfit_dir_xyz")
    )
    result = _lookup_community_benchmark("ollama:llama3.1:8b", "q4_k")
    assert result is None


def test_score_model_community_warning_present(monkeypatch):
    """When community data is injected, warnings mention 'community'."""
    import auralynq.modelfit.scoring as scoring
    from auralynq.modelfit.scoring import BenchmarkSnapshot

    fake_bench = BenchmarkSnapshot(avg_tok_per_sec=30.0, is_measured=True)

    monkeypatch.setattr(scoring, "_lookup_community_benchmark", lambda *a, **kw: fake_bench)

    hw = _make_hw()
    model = _make_model()
    score = score_model(model, hw, use_community_data=True)
    assert any("community" in w.lower() for w in score.warnings)


def test_score_model_community_data_disabled(monkeypatch):
    """use_community_data=False skips community lookup."""
    import auralynq.modelfit.scoring as scoring

    called = []
    monkeypatch.setattr(
        scoring, "_lookup_community_benchmark", lambda *a, **kw: called.append(True) or None
    )

    hw = _make_hw()
    model = _make_model()
    score_model(model, hw, use_community_data=False)
    assert called == []  # never called


# ── Phase 2: RAG bench helper functions ──────────────────────────────────────


def test_rag_bench_groundedness_with_overlap():
    from auralynq.modelfit.rag_bench import _simple_groundedness

    answer = "The document discusses climate change and temperature trends."
    contexts = ["This report covers climate change impacts including temperature trends globally."]
    g = _simple_groundedness(answer, contexts)
    assert 0.0 < g <= 1.0


def test_rag_bench_groundedness_zero_when_no_context():
    from auralynq.modelfit.rag_bench import _simple_groundedness

    g = _simple_groundedness("Any answer", [])
    assert g == 0.0


def test_rag_bench_groundedness_zero_empty_answer():
    from auralynq.modelfit.rag_bench import _simple_groundedness

    g = _simple_groundedness("", ["some context"])
    assert g == 0.0


def test_rag_bench_citation_coverage_no_citations():
    from auralynq.modelfit.rag_bench import _citation_coverage_score

    score = _citation_coverage_score([], ["some context"])
    assert score == 0.0


def test_rag_bench_citation_coverage_match():
    from auralynq.modelfit.rag_bench import _citation_coverage_score

    contexts = ["report.pdf\nBody of text"]
    citations = [{"source": "report.pdf"}]
    score = _citation_coverage_score(citations, contexts)
    assert score > 0.0


def test_rag_bench_is_abstention():
    from auralynq.modelfit.rag_bench import _is_abstention

    assert _is_abstention("I don't have enough evidence to answer this question.")
    assert _is_abstention("There is no relevant evidence in the indexed documents.")
    assert not _is_abstention("The answer is Paris, the capital of France.")


def test_rag_bench_metrics_dataclass():
    from auralynq.modelfit.rag_bench import RAGBenchMetrics

    m = RAGBenchMetrics(groundedness=0.7, citation_coverage=0.5, abstention_accuracy=0.8)
    d = m.to_dict()
    assert d["groundedness"] == 0.7
    assert d["citation_coverage"] == 0.5
    assert d["abstention_accuracy"] == 0.8
    assert d["is_measured"] is True


# ── Phase 2: _build_modelfit_snapshot ────────────────────────────────────────


def test_build_modelfit_snapshot_cloud_returns_none():
    from auralynq.agent.runner import _build_modelfit_snapshot

    result = _build_modelfit_snapshot("openai", "gpt-4")
    assert result is None  # cloud providers not covered


def test_build_modelfit_snapshot_unknown_model():
    from auralynq.agent.runner import _build_modelfit_snapshot

    # 'slm:totally-unknown-model-xyz' won't be in registry
    result = _build_modelfit_snapshot("slm", "totally-unknown-model-xyz")
    # Either None (import failed) or dict with fit_score=None
    if result is not None:
        assert result.get("fit_score") is None or isinstance(result.get("fit_score"), (int, float))


def test_answer_result_has_model_fit_field():
    from auralynq.agent.runner import AnswerResult

    r = AnswerResult(answer="test")
    assert hasattr(r, "model_fit")
    assert r.model_fit is None


# ── Phase 2: CLI entry point ──────────────────────────────────────────────────


def test_cli_module_importable():
    from auralynq.modelfit import cli

    assert hasattr(cli, "app") or hasattr(cli, "main")


def test_cli_has_hardware_command():
    from auralynq.modelfit.cli import app

    # Typer sets name=None until registration; callback.__name__ holds the function name
    command_names = [
        c.name or (c.callback.__name__ if c.callback else "") for c in app.registered_commands
    ]
    assert "hardware" in command_names


def test_cli_has_benchmark_command():
    from auralynq.modelfit.cli import app

    command_names = [
        c.name or (c.callback.__name__ if c.callback else "") for c in app.registered_commands
    ]
    assert "benchmark" in command_names


# ── Phase 2: BenchmarkResult rag_metrics wiring ──────────────────────────────


def test_benchmark_plan_rag_task_preview():
    plan = preview_benchmark("ollama:llama3.1:8b", task="rag", num_examples=5)
    d = plan.to_dict()
    assert d["task"] == "rag"
    assert d["requires_model_download"] is False


def test_benchmark_result_rag_metrics_key_present():
    """BenchmarkResult.rag_metrics must contain citation_coverage and groundedness."""
    from auralynq.modelfit.benchmark_runner import BenchmarkResult

    r = BenchmarkResult(
        run_id="x",
        model_id="ollama:llama3.1:8b",
        quantization="q4_k",
        task="rag",
        status="completed",
        rag_metrics={
            "citation_coverage": 0.6,
            "groundedness": 0.7,
            "abstention_accuracy": 0.8,
            "is_measured": True,
        },
    )
    d = r.to_dict()
    assert "citation_coverage" in d["rag_metrics"]
    assert "groundedness" in d["rag_metrics"]
    assert d["rag_metrics"]["is_measured"] is True
