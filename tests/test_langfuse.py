"""Tests for the optional Langfuse trace exporter (ADR-0019).

All offline: the `langfuse` SDK is stubbed so we exercise enable-detection and the
export path without the real dependency, and confirm export is a safe no-op when
disabled and never raises.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types

from auralynq.telemetry.langfuse_export import export_trace, langfuse_enabled
from auralynq.telemetry.tracing import Trace


def _trace() -> Trace:
    t = Trace(trace_id="t-test")
    with t.span("planner", q="x"):
        pass
    with t.span("synthesizer", provider="extractive"):
        pass
    return t


def test_disabled_without_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    from auralynq.config import reload_settings

    reload_settings()
    assert langfuse_enabled() is False
    # export is a no-op (returns False), never raises
    assert export_trace(_trace(), question="q", answer="a") is False


def _install_fake_langfuse(monkeypatch, recorder):
    fake = types.ModuleType("langfuse")
    fake.__spec__ = importlib.machinery.ModuleSpec("langfuse", loader=None)

    class _Span:
        def span(self, **kw):
            recorder["spans"].append(kw)
            return self

    class _Trace(_Span):
        pass

    class _Langfuse:
        def __init__(self, **kw):
            recorder["init"] = kw

        def trace(self, **kw):
            recorder["trace"] = kw
            return _Trace()

        def flush(self):
            recorder["flushed"] = True

    fake.Langfuse = _Langfuse
    monkeypatch.setitem(sys.modules, "langfuse", fake)


def test_enabled_and_exports_with_keys_and_sdk(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    from auralynq.config import reload_settings

    reload_settings()
    rec = {"spans": []}
    _install_fake_langfuse(monkeypatch, rec)
    # reset the cached client so it picks up the stub + keys
    from auralynq.telemetry import langfuse_export as lx

    lx._client.cache_clear()

    assert langfuse_enabled() is True
    ok = export_trace(
        _trace(),
        question="What is the capital of France?",
        answer="Paris [1]",
        metadata={"route": "fast"},
    )
    assert ok is True
    assert rec["trace"]["input"] == {"question": "What is the capital of France?"}
    assert rec["trace"]["output"] == {"answer": "Paris [1]"}
    assert [s["name"] for s in rec["spans"]] == ["planner", "synthesizer"]
    assert rec.get("flushed") is True
    lx._client.cache_clear()


def test_export_never_raises_on_sdk_error(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    from auralynq.config import reload_settings

    reload_settings()
    fake = types.ModuleType("langfuse")
    fake.__spec__ = importlib.machinery.ModuleSpec("langfuse", loader=None)

    class _Boom:
        def __init__(self, **kw):
            raise RuntimeError("network down")

    fake.Langfuse = _Boom
    monkeypatch.setitem(sys.modules, "langfuse", fake)
    from auralynq.telemetry import langfuse_export as lx

    lx._client.cache_clear()
    # must swallow the error and return False, not propagate
    assert export_trace(_trace(), question="q", answer="a") is False
    lx._client.cache_clear()
