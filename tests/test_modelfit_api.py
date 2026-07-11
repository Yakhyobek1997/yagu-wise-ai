"""Tests for the ModelFit HTTP router, CLI, benchmark runner, and hardware probing.

Everything runs offline: Ollama / HF Hub interactions are replaced with fakes,
and benchmark streaming is simulated with a canned httpx.AsyncClient double.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import auralynq.modelfit.benchmark_runner as bench_mod
import auralynq.modelfit.catalog_fetcher as fetcher_mod
import auralynq.modelfit.community as community_mod
import auralynq.modelfit.hardware as hw_mod
import auralynq.modelfit.model_registry as registry_mod
import pytest
from auralynq.modelfit.benchmark_runner import (
    BenchmarkResult,
    get_run,
    list_runs,
    run_benchmark,
)
from auralynq.modelfit.cli import app as cli_app
from auralynq.modelfit.community import (
    load_community_results,
    save_community_result,
)
from auralynq.modelfit.hf_catalog import search_hf_models
from auralynq.modelfit.model_metadata import ModelMetadata
from auralynq.modelfit.model_registry import ModelRegistry, _discover_local_gguf, get_registry
from auralynq.modelfit.ollama_catalog import (
    _tag_to_metadata,
    get_model_details,
    list_installed_models,
)
from auralynq.modelfit.router import router as modelfit_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

# ── Shared fakes ──────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient for plain GET/POST calls."""

    def __init__(self, *args, response: _FakeResponse | None = None, **kwargs):
        self._response = response or _FakeResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        return self._response

    async def post(self, *args, **kwargs):
        return self._response


def _client_factory(response: _FakeResponse):
    def factory(*args, **kwargs):
        return _FakeAsyncClient(response=response)

    return factory


class _RaisingAsyncClient:
    def __init__(self, *args, **kwargs):
        raise ConnectionError("connection refused")


# ── Ollama catalog ────────────────────────────────────────────────────────────


def test_tag_metadata_chat_model_with_tools():
    m = _tag_to_metadata("llama3.1:8b", size_bytes=5 * 1024**3)
    assert m.family == "llama"
    assert m.parameter_count_b == 8.0
    assert m.context_length == 128000
    assert m.tool_calling is True
    assert "agents" in m.tasks
    assert m.notes and "Disk size" in m.notes[0]


def test_tag_metadata_vision_model():
    m = _tag_to_metadata("llava:13b")
    assert m.vision is True
    assert "vision" in m.tasks
    assert m.notes == ["Size unknown"]


def test_tag_metadata_embedding_model_has_no_chat_tasks():
    m = _tag_to_metadata("nomic-embed-text:latest")
    assert m.embedding is True
    assert m.tasks == []


def test_tag_metadata_unknown_family():
    m = _tag_to_metadata("some-exotic-model:1b")
    assert m.family == "unknown"


@pytest.mark.asyncio
async def test_list_installed_models_parses_tags(monkeypatch):
    payload = {"models": [{"name": "llama3.1:8b", "size": 4 * 1024**3}, {"name": ""}]}
    monkeypatch.setattr("httpx.AsyncClient", _client_factory(_FakeResponse(200, payload)))
    models, warnings = await list_installed_models()
    assert warnings == []
    assert len(models) == 1
    assert models[0].model_id == "ollama:llama3.1:8b"


@pytest.mark.asyncio
async def test_list_installed_models_http_error(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _client_factory(_FakeResponse(500)))
    models, warnings = await list_installed_models()
    assert models == []
    assert any("HTTP 500" in w for w in warnings)


@pytest.mark.asyncio
async def test_list_installed_models_unreachable(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _RaisingAsyncClient)
    models, warnings = await list_installed_models()
    assert models == []
    assert any("not reachable" in w for w in warnings)


@pytest.mark.asyncio
async def test_get_model_details_found(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _client_factory(_FakeResponse(200, {})))
    meta, warnings = await get_model_details("mistral:7b")
    assert meta is not None
    assert meta.family == "mistral"
    assert warnings == []


@pytest.mark.asyncio
async def test_get_model_details_not_found(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _client_factory(_FakeResponse(404)))
    meta, warnings = await get_model_details("nope:1b")
    assert meta is None
    assert any("not found" in w for w in warnings)


@pytest.mark.asyncio
async def test_get_model_details_unreachable(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _RaisingAsyncClient)
    meta, warnings = await get_model_details("mistral:7b")
    assert meta is None
    assert any("not reachable" in w for w in warnings)


# ── HF catalog live search ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_hf_models_parses_entries(monkeypatch):
    payload = [
        {"modelId": "org/model-a", "tags": ["feature-extraction"], "gated": False},
        {"id": "org/model-b", "tags": [], "gated": True, "license": "mit"},
        {"tags": []},  # no id — skipped
    ]
    monkeypatch.setattr("httpx.AsyncClient", _client_factory(_FakeResponse(200, payload)))
    results, warnings = await search_hf_models("model")
    assert warnings == []
    assert [r.model_id for r in results] == ["hf:org/model-a", "hf:org/model-b"]
    assert results[0].embedding is True
    assert results[1].gated is True


@pytest.mark.asyncio
async def test_search_hf_models_http_error(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _client_factory(_FakeResponse(503)))
    results, warnings = await search_hf_models("model")
    assert results == []
    assert any("HTTP 503" in w for w in warnings)


@pytest.mark.asyncio
async def test_search_hf_models_unreachable(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _RaisingAsyncClient)
    results, warnings = await search_hf_models("model")
    assert results == []
    assert any("not reachable" in w for w in warnings)


# ── Community persistence ─────────────────────────────────────────────────────


def _valid_entry() -> dict:
    return {
        "model_id": "ollama:llama3.1:8b",
        "quantization": "q4_k",
        "hardware": {"cpu_model": "Intel Core i9", "ram_gb": 32},
        "benchmark_version": "auralynq-modelfit-0.1",
        "task": "rag",
        "date": "2026-06-23",
        "source": "auralynq-benchmark-runner",
        "tok_per_sec": 28.4,
    }


def test_save_and_load_community_result(tmp_path, monkeypatch):
    monkeypatch.setattr(community_mod, "_COMMUNITY_DIR", tmp_path)
    ok, errors = save_community_result(_valid_entry())
    assert ok and errors == []
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    data = json.loads(saved[0].read_text())
    assert data["verified_status"] == "self_reported"
    assert "submitted_at" in data

    results = load_community_results()
    assert len(results) == 1
    assert results[0].model_id == "ollama:llama3.1:8b"


def test_save_community_result_invalid_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(community_mod, "_COMMUNITY_DIR", tmp_path)
    entry = _valid_entry()
    del entry["task"]
    ok, errors = save_community_result(entry)
    assert not ok and errors
    assert list(tmp_path.glob("*.json")) == []


def test_load_community_results_verified_only_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(community_mod, "_COMMUNITY_DIR", tmp_path)
    save_community_result(_valid_entry())
    verified = _valid_entry()
    verified["date"] = "2026-06-24"
    verified["verified_status"] = "verified_local"
    save_community_result(verified)

    all_results = load_community_results()
    assert len(all_results) == 2
    only_verified = load_community_results(verified_only=True)
    assert len(only_verified) == 1
    assert only_verified[0].verified_status == "verified_local"


def test_load_community_results_skips_malformed(tmp_path, monkeypatch):
    monkeypatch.setattr(community_mod, "_COMMUNITY_DIR", tmp_path)
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "incomplete.json").write_text(json.dumps({"model_id": "x"}))
    assert load_community_results() == []


# ── Model registry ────────────────────────────────────────────────────────────


def test_discover_local_gguf(tmp_path):
    gguf = tmp_path / "tiny-model.gguf"
    gguf.write_bytes(b"\0" * 1024)
    found = _discover_local_gguf(search_dirs=[str(tmp_path), str(tmp_path / "missing")])
    assert len(found) == 1
    assert found[0].source == "local"
    assert found[0].local_path == str(gguf)


@pytest.mark.asyncio
async def test_registry_refresh_from_ollama(monkeypatch):
    fake_model = _tag_to_metadata("fake-live-model:3b")

    async def fake_list():
        return [fake_model], ["Ollama warning"]

    monkeypatch.setattr(registry_mod, "list_installed_models", fake_list)
    registry = ModelRegistry()
    warnings = await registry.refresh_from_ollama()
    assert warnings == ["Ollama warning"]
    live = registry.get("ollama:fake-live-model:3b")
    assert live is not None
    assert live.notes[0] == "Locally installed in Ollama."


def test_registry_search_filters():
    registry = ModelRegistry()
    small = registry.search(max_params_b=4.0)
    assert all(m.parameter_count_b <= 4.0 for m in small if m.parameter_count_b)
    big = registry.search(min_params_b=30.0)
    assert all(m.parameter_count_b >= 30.0 for m in big if m.parameter_count_b)
    open_lic = registry.search(open_license=True)
    assert all(m.license.lower().replace(" ", "-") in {"apache-2.0", "mit"} for m in open_lic)
    tools = registry.search(tool_calling=True)
    assert all(m.tool_calling for m in tools)
    with_vision = registry.search(vision=True)
    assert all(m.vision for m in with_vision)
    adapters = registry.search(supports_adapters=True)
    assert all(m.supports_adapters for m in adapters)
    rerankers = registry.search(reranker_only=True)
    assert all(m.reranker for m in rerankers)


# ── Benchmark runner ──────────────────────────────────────────────────────────


class _FakeStreamResponse:
    def __init__(self, status_code: int, lines: list[str]):
        self.status_code = status_code
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamContext:
    def __init__(self, resp: _FakeStreamResponse):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return False


class _FakeStreamingClient:
    resp: _FakeStreamResponse | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, json=None):
        assert self.resp is not None
        return _FakeStreamContext(self.resp)


_OK_STREAM_LINES = [
    "",  # skipped
    "not-json",  # skipped
    json.dumps({"response": "Hello"}),
    json.dumps({"response": " world"}),
    json.dumps({"eval_count": 42, "done": True}),
]


@pytest.mark.asyncio
async def test_run_benchmark_completes_and_persists(tmp_path, monkeypatch):
    _FakeStreamingClient.resp = _FakeStreamResponse(200, _OK_STREAM_LINES)
    monkeypatch.setattr("httpx.AsyncClient", _FakeStreamingClient)

    # 5 examples > 3 latency prompts exercises the prompt-repeat branch.
    result = await run_benchmark(
        "ollama:fake:1b", task="latency", num_examples=5, output_dir=str(tmp_path)
    )
    assert result.status == "completed"
    assert result.completed_examples == 5
    assert result.p50_latency_ms is not None
    assert result.p95_latency_ms is not None
    assert result.avg_tok_per_sec is not None
    assert result.time_to_first_token_ms is not None
    assert result.rag_metrics["is_measured"] is False
    assert (tmp_path / f"{result.run_id}.json").exists()


@pytest.mark.asyncio
async def test_run_benchmark_model_not_installed(tmp_path, monkeypatch):
    _FakeStreamingClient.resp = _FakeStreamResponse(404, [])
    monkeypatch.setattr("httpx.AsyncClient", _FakeStreamingClient)
    result = await run_benchmark("ollama:missing:1b", num_examples=1, output_dir=str(tmp_path))
    assert result.status == "failed"
    assert "not found in local Ollama" in (result.error or "")


@pytest.mark.asyncio
async def test_run_benchmark_connection_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _RaisingAsyncClient)
    result = await run_benchmark("ollama:fake:1b", num_examples=1, output_dir=str(tmp_path))
    assert result.status == "failed"
    assert "Ollama connection failed" in (result.error or "")


@pytest.mark.asyncio
async def test_run_benchmark_example_errors_recorded(tmp_path, monkeypatch):
    class _StreamRaises(_FakeStreamingClient):
        def stream(self, method, url, json=None):
            raise RuntimeError("stream blew up")

    monkeypatch.setattr("httpx.AsyncClient", _StreamRaises)
    result = await run_benchmark("ollama:fake:1b", num_examples=2, output_dir=str(tmp_path))
    assert result.status == "completed"
    assert any("Example error" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_run_benchmark_rag_quality_failure_is_soft(tmp_path, monkeypatch):
    _FakeStreamingClient.resp = _FakeStreamResponse(200, _OK_STREAM_LINES)
    monkeypatch.setattr("httpx.AsyncClient", _FakeStreamingClient)

    async def boom(**kwargs):
        raise RuntimeError("no corpus")

    monkeypatch.setattr("auralynq.modelfit.rag_bench.run_rag_benchmark", boom)
    result = await run_benchmark(
        "ollama:fake:1b", task="rag", num_examples=1, output_dir=str(tmp_path)
    )
    assert result.status == "completed"
    assert result.rag_metrics["is_measured"] is False
    assert any("RAG quality benchmark failed" in w for w in result.warnings)


def test_get_run_from_memory_and_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(bench_mod, "_RUNS_DIR", tmp_path)
    monkeypatch.setattr(bench_mod, "_active_runs", {})

    in_mem = BenchmarkResult(
        run_id="mem1", model_id="m", quantization="q4_k", task="latency", status="completed"
    )
    bench_mod._active_runs["mem1"] = in_mem
    assert get_run("mem1") is in_mem

    on_disk = BenchmarkResult(
        run_id="disk1", model_id="m", quantization="q4_k", task="latency", status="completed"
    )
    (tmp_path / "disk1.json").write_text(json.dumps(on_disk.to_dict()))
    loaded = get_run("disk1")
    assert loaded is not None and loaded.run_id == "disk1"

    (tmp_path / "bad1.json").write_text("{corrupt")
    assert get_run("bad1") is None
    assert get_run("unknown") is None


def test_list_runs_merges_memory_and_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(bench_mod, "_RUNS_DIR", tmp_path)
    monkeypatch.setattr(bench_mod, "_active_runs", {})

    mem = BenchmarkResult(
        run_id="mem2", model_id="m", quantization="q4_k", task="latency", status="running"
    )
    bench_mod._active_runs["mem2"] = mem
    disk = BenchmarkResult(
        run_id="disk2", model_id="m", quantization="q4_k", task="latency", status="completed"
    )
    (tmp_path / "disk2.json").write_text(json.dumps(disk.to_dict()))

    runs = list_runs()
    ids = {r["run_id"] for r in runs}
    assert {"mem2", "disk2"} <= ids


# ── Hardware probing branches ─────────────────────────────────────────────────


def _fake_run_factory(handlers: dict[str, object]):
    """subprocess.run double keyed by executable name."""

    def fake_run(cmd, *args, **kwargs):
        exe = cmd[0]
        outcome = handlers.get(exe, FileNotFoundError())
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return fake_run


def test_detect_nvidia_gpus_parses_csv(monkeypatch):
    smi = SimpleNamespace(returncode=0, stdout="NVIDIA RTX 3090, 24576\nNVIDIA A100, 40960\n")
    monkeypatch.setattr(hw_mod.subprocess, "run", _fake_run_factory({"nvidia-smi": smi}))
    gpus = hw_mod._detect_nvidia_gpus()
    assert len(gpus) == 2
    assert gpus[0].vendor == "nvidia" and gpus[0].vram_gb == 24.0
    assert gpus[1].device_index == 1


def test_detect_gpus_nvidia_without_nvcc(monkeypatch):
    smi = SimpleNamespace(returncode=0, stdout="NVIDIA RTX 3090, 24576\n")
    monkeypatch.setattr(hw_mod.subprocess, "run", _fake_run_factory({"nvidia-smi": smi}))
    gpus, cuda, cuda_ver, metal, rocm = hw_mod._detect_gpus()
    assert cuda is True and metal is False and rocm is False
    assert cuda_ver == "detected (version unknown)"
    assert gpus[0].backend == "cuda"


def test_detect_gpus_nvcc_version_parsed(monkeypatch):
    smi = SimpleNamespace(returncode=0, stdout="NVIDIA RTX 3090, 24576\n")
    nvcc = SimpleNamespace(returncode=0, stdout="Cuda compilation tools, release 12.4, V12.4.99\n")
    monkeypatch.setattr(
        hw_mod.subprocess, "run", _fake_run_factory({"nvidia-smi": smi, "nvcc": nvcc})
    )
    _, cuda, cuda_ver, _, _ = hw_mod._detect_gpus()
    assert cuda is True
    assert "release 12.4" in (cuda_ver or "")


def test_detect_amd_gpus_parses_rocm_csv(monkeypatch):
    rocm = SimpleNamespace(
        returncode=0, stdout="device,VRAM Total\ncard0,17163091968\ncard1,not-a-number\n"
    )
    monkeypatch.setattr(hw_mod.subprocess, "run", _fake_run_factory({"rocm-smi": rocm}))
    gpus = hw_mod._detect_amd_gpus()
    assert len(gpus) == 1
    assert gpus[0].vendor == "amd" and gpus[0].backend == "rocm"
    assert gpus[0].vram_gb == 16.0


def test_detect_apple_silicon(monkeypatch):
    monkeypatch.setattr(hw_mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hw_mod, "_detect_ram_gb", lambda: 32.0)
    profiler = SimpleNamespace(returncode=0, stdout="Chipset Model: Apple M3\n")
    monkeypatch.setattr(hw_mod.subprocess, "run", _fake_run_factory({"system_profiler": profiler}))
    gpus = hw_mod._detect_apple_silicon()
    assert len(gpus) == 1
    assert gpus[0].vendor == "apple" and gpus[0].backend == "metal"
    assert gpus[0].vram_gb == 24.0  # 75% of unified memory


def test_detect_apple_silicon_skipped_off_darwin(monkeypatch):
    monkeypatch.setattr(hw_mod.platform, "system", lambda: "Linux")
    assert hw_mod._detect_apple_silicon() == []


def test_detect_ollama_present(monkeypatch):
    monkeypatch.setattr(hw_mod.shutil, "which", lambda _: "/usr/bin/ollama")
    version = SimpleNamespace(returncode=0, stdout="ollama version is 0.5.1\n", stderr="")
    monkeypatch.setattr(hw_mod.subprocess, "run", _fake_run_factory({"ollama": version}))
    available, ver = hw_mod._detect_ollama()
    assert available is True
    assert "0.5.1" in (ver or "")


def test_detect_ollama_absent(monkeypatch):
    monkeypatch.setattr(hw_mod.shutil, "which", lambda _: None)
    assert hw_mod._detect_ollama() == (False, None)


# ── HTTP router ───────────────────────────────────────────────────────────────


@pytest.fixture()
def api():
    app = FastAPI()
    app.include_router(modelfit_router)
    return TestClient(app)


def _any_model_id() -> str:
    return get_registry().list_all()[0].model_id


def test_api_hardware(api):
    r = api.get("/api/modelfit/hardware")
    assert r.status_code == 200
    body = r.json()
    assert "best_backend" in body and "ram_gb" in body


def test_api_list_models_with_filters(api):
    r = api.get("/api/modelfit/models", params={"task": "rag", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] <= 5
    assert all("model_id" in m for m in body["models"])


def test_api_search_models(api, monkeypatch):
    async def fake_list():
        return [], ["ollama offline"]

    monkeypatch.setattr(registry_mod, "list_installed_models", fake_list)
    r = api.get("/api/modelfit/models/search", params={"q": "llama", "refresh_ollama": "true"})
    assert r.status_code == 200
    assert r.json()["warnings"] == ["ollama offline"]


def test_api_installed_models(api, monkeypatch):
    async def fake_list():
        return [_tag_to_metadata("fake-installed:1b")], []

    monkeypatch.setattr(registry_mod, "list_installed_models", fake_list)
    r = api.get("/api/modelfit/models/installed")
    assert r.status_code == 200
    ids = [m["model_id"] for m in r.json()["models"]]
    assert "ollama:fake-installed:1b" in ids


def test_api_get_model_found_and_missing(api):
    model_id = _any_model_id()
    ok = api.get(f"/api/modelfit/models/{model_id}")
    assert ok.status_code == 200
    assert ok.json()["model_id"] == model_id
    missing = api.get("/api/modelfit/models/does:not:exist")
    assert missing.status_code == 404


def test_api_estimate(api):
    r = api.post(
        "/api/modelfit/estimate",
        json={"model_id": "x", "params_b": 8.0, "quantization": "q4_k"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["estimated_vram_gb"] > 0


def test_api_recommend_quantization(api):
    r = api.post("/api/modelfit/recommend-quantization", params={"params_b": 8.0})
    assert r.status_code == 200
    body = r.json()
    assert body["is_estimate"] is True
    assert body["recommended_quantization"]


def test_api_score_found_and_missing(api):
    ok = api.post("/api/modelfit/score", json={"model_id": _any_model_id()})
    assert ok.status_code == 200
    assert 0 <= ok.json()["overall_score"] <= 100
    missing = api.post("/api/modelfit/score", json={"model_id": "does:not:exist"})
    assert missing.status_code == 404


def test_api_recommendations(api):
    r = api.get("/api/modelfit/recommendations", params={"task": "rag", "limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert len(body["recommendations"]) <= 3
    assert "hardware_summary" in body


def test_api_benchmark_preview(api):
    r = api.post(
        "/api/modelfit/benchmark/preview",
        json={"model_id": "ollama:fake:1b", "task": "latency", "num_examples": 2},
    )
    assert r.status_code == 200
    assert "dry-run" in r.json()["note"]


def test_api_benchmark_run_requires_confirmation(api):
    r = api.post(
        "/api/modelfit/benchmark/run",
        json={"model_id": "ollama:fake:1b", "confirmed": False},
    )
    assert r.status_code == 400


def test_api_benchmark_run_confirmed(api, monkeypatch):
    fake_result = BenchmarkResult(
        run_id="r1",
        model_id="ollama:fake:1b",
        quantization="q4_k",
        task="latency",
        status="completed",
    )

    async def fake_run(**kwargs):
        return fake_result

    monkeypatch.setattr("auralynq.modelfit.router.run_benchmark", fake_run)
    r = api.post(
        "/api/modelfit/benchmark/run",
        json={"model_id": "ollama:fake:1b", "confirmed": True},
    )
    assert r.status_code == 200
    assert r.json()["run_id"] == "r1"


def test_api_benchmark_runs_and_get(api, tmp_path, monkeypatch):
    monkeypatch.setattr(bench_mod, "_RUNS_DIR", tmp_path)
    monkeypatch.setattr(bench_mod, "_active_runs", {})
    result = BenchmarkResult(
        run_id="api1", model_id="m", quantization="q4_k", task="latency", status="completed"
    )
    bench_mod._active_runs["api1"] = result

    runs = api.get("/api/modelfit/benchmark/runs")
    assert runs.status_code == 200
    assert runs.json()["total"] >= 1

    one = api.get("/api/modelfit/benchmark/api1")
    assert one.status_code == 200
    missing = api.get("/api/modelfit/benchmark/nope")
    assert missing.status_code == 404


def test_api_community_results_and_validate(api, tmp_path, monkeypatch):
    monkeypatch.setattr(community_mod, "_COMMUNITY_DIR", tmp_path)
    save_community_result(_valid_entry())

    r = api.get("/api/modelfit/community/results", params={"model_id": "ollama:"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert "disclaimer" in body

    valid = api.post("/api/modelfit/community/validate", json=_valid_entry())
    assert valid.status_code == 200
    assert valid.json()["valid"] is True

    invalid = api.post("/api/modelfit/community/validate", json={"model_id": "x"})
    assert invalid.json()["valid"] is False


def test_api_discover(api, monkeypatch):
    ollama_model = _tag_to_metadata("llama3.1:8b", size_bytes=5 * 1024**3)
    hf_model = ModelMetadata(
        model_id="hf:org/gguf-model",
        source="huggingface",
        display_name="org/gguf-model",
        family="llama",
        parameter_count_b=8.0,
        hf_repo="org/gguf-model",
        tasks=["chat", "rag"],
    )
    embed_model = _tag_to_metadata("nomic-embed-text:latest")

    async def fake_ollama(vram_gb, ram_gb):
        return [ollama_model, embed_model]

    async def fake_hf(vram_gb):
        return [hf_model]

    monkeypatch.setattr(fetcher_mod, "fetch_ollama_catalog", fake_ollama)
    monkeypatch.setattr(fetcher_mod, "fetch_hf_gguf_catalog", fake_hf)
    monkeypatch.setattr(fetcher_mod, "invalidate_cache", lambda: None)

    r = api.post(
        "/api/modelfit/discover",
        json={"task": "rag", "include_hf": True, "refresh": True, "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    recs = body["recommendations"]
    # Embedding model filtered out for a non-embedding task.
    ids = {m["model_meta"]["model_id"] for m in recs}
    assert "ollama:nomic-embed-text:latest" not in ids
    pulls = {m["model_meta"]["model_id"]: m["pull_command"] for m in recs}
    assert pulls["ollama:llama3.1:8b"] == "ollama pull llama3.1:8b"
    assert "huggingface-cli download org/gguf-model" in pulls["hf:org/gguf-model"]


def test_api_discover_catalog_error_is_soft(api, monkeypatch):
    async def fake_ollama(vram_gb, ram_gb):
        raise RuntimeError("registry down")

    monkeypatch.setattr(fetcher_mod, "fetch_ollama_catalog", fake_ollama)
    r = api.post("/api/modelfit/discover", json={"include_hf": False})
    assert r.status_code == 200
    assert r.json()["total_candidates"] == 0


def test_api_pull_requires_confirmation(api):
    r = api.post("/api/modelfit/pull", json={"model_id": "ollama:x", "confirmed": False})
    assert r.status_code == 400


def test_api_pull_bad_prefix(api):
    r = api.post("/api/modelfit/pull", json={"model_id": "weird:x", "confirmed": True})
    assert r.status_code == 400
    assert "Unrecognised" in r.json()["detail"]


def test_api_pull_ollama(api, monkeypatch):
    async def fake_pull(tag):
        return True, f"pulled {tag}"

    monkeypatch.setattr(fetcher_mod, "pull_ollama_model", fake_pull)
    r = api.post("/api/modelfit/pull", json={"model_id": "ollama:llama3.2:1b", "confirmed": True})
    assert r.status_code == 200
    assert r.json()["status"] == "pulled"


def test_api_pull_ollama_failure(api, monkeypatch):
    async def fake_pull(tag):
        return False, "disk full"

    monkeypatch.setattr(fetcher_mod, "pull_ollama_model", fake_pull)
    r = api.post("/api/modelfit/pull", json={"model_id": "ollama:llama3.2:1b", "confirmed": True})
    assert r.status_code == 500


def test_api_pull_hf_validations(api):
    no_slash = api.post("/api/modelfit/pull", json={"model_id": "hf:justname", "confirmed": True})
    assert no_slash.status_code == 400
    not_gguf = api.post(
        "/api/modelfit/pull", json={"model_id": "hf:org/repo/file.bin", "confirmed": True}
    )
    assert not_gguf.status_code == 400


def test_api_pull_hf_download(api, monkeypatch):
    def fake_pull(repo_id, filename, token):
        return True, f"/models/{filename}"

    monkeypatch.setattr(fetcher_mod, "pull_hf_gguf", fake_pull)
    r = api.post(
        "/api/modelfit/pull",
        json={"model_id": "hf:org/repo/model.gguf", "confirmed": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "downloaded"
    assert body["local_path"] == "/models/model.gguf"


# ── CLI ───────────────────────────────────────────────────────────────────────

cli_runner = CliRunner()


def test_cli_hardware():
    result = cli_runner.invoke(cli_app, ["hardware"])
    assert result.exit_code == 0
    assert "Hardware Profile" in result.stdout


def test_cli_estimate():
    result = cli_runner.invoke(cli_app, ["estimate", "--model", "ollama:fake:8b", "--params", "8"])
    assert result.exit_code == 0
    assert "Resource Estimate" in result.stdout


def test_cli_score_known_model():
    result = cli_runner.invoke(cli_app, ["score", "--model", _any_model_id()])
    assert result.exit_code == 0
    assert "ModelFit Score" in result.stdout


def test_cli_score_unknown_model_exits_nonzero():
    result = cli_runner.invoke(cli_app, ["score", "--model", "does:not:exist"])
    assert result.exit_code == 1


def test_cli_recommend():
    result = cli_runner.invoke(cli_app, ["recommend", "--task", "rag", "--limit", "3"])
    assert result.exit_code == 0
    assert "Top 3 models" in result.stdout


def test_cli_benchmark_dry_run():
    result = cli_runner.invoke(cli_app, ["benchmark", "--model", "fake:1b", "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run" in result.stdout


def test_cli_benchmark_declined():
    result = cli_runner.invoke(cli_app, ["benchmark", "--model", "fake:1b"], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout


def test_cli_benchmark_confirmed(monkeypatch):
    fake_result = BenchmarkResult(
        run_id="cli1",
        model_id="ollama:fake:1b",
        quantization="q4_k",
        task="latency",
        status="completed",
        avg_tok_per_sec=25.0,
        p50_latency_ms=120.0,
        p95_latency_ms=300.0,
    )

    async def fake_run(*args, **kwargs):
        return fake_result

    monkeypatch.setattr(bench_mod, "run_benchmark", fake_run)
    result = cli_runner.invoke(cli_app, ["benchmark", "--model", "fake:1b"], input="y\n")
    assert result.exit_code == 0
    assert "Benchmark completed" in result.stdout


def test_cli_benchmark_failure_exits_nonzero(monkeypatch):
    fake_result = BenchmarkResult(
        run_id="cli2",
        model_id="ollama:fake:1b",
        quantization="q4_k",
        task="latency",
        status="failed",
        error="model missing",
    )

    async def fake_run(*args, **kwargs):
        return fake_result

    monkeypatch.setattr(bench_mod, "run_benchmark", fake_run)
    result = cli_runner.invoke(cli_app, ["benchmark", "--model", "fake:1b"], input="y\n")
    assert result.exit_code == 1
    assert "Benchmark failed" in result.stdout
