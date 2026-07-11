#!/usr/bin/env python3
"""Dataset downloader for Auralynq.

Downloads small evaluation/demo corpora via Hugging Face ``datasets`` when
available, with ``--sample`` (default) and ``--full`` modes, caching, and
graceful skips. **It never requires paid keys** and ALWAYS produces a usable
local corpus: if ``datasets`` is unavailable or offline, it writes a curated
synthetic corpus + golden QA set + a synthetic audio sample, so ``make data``,
``make demo``, ``make eval`` and ``make bench`` work at $0 with no network.

Outputs:
    data/corpus/        ingestible text + audio sources
    data/golden/        golden_qa.json (frozen eval set), asr_refs.json
    data/manifests/     dataset_manifest.json (provenance + checksums)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path
from typing import Any

from auralynq.config import get_settings
from auralynq.telemetry import configure_logging, get_logger

_log = get_logger("auralynq.data")

# Text multi-hop QA datasets (HF ids). Each entry is best-effort; failures skip.
TEXT_DATASETS = [
    {"name": "hotpotqa", "hf": "hotpot_qa", "config": "distractor", "split": "validation"},
    {"name": "musique", "hf": "dgslibisey/MuSiQue", "config": None, "split": "validation"},
    {
        "name": "2wikimultihopqa",
        "hf": "scholarly-shadows-syndicate/2wikimultihopqa_with_q_gpt35",
        "config": None,
        "split": "train",
    },
]
VOICE_DATASETS = [
    {
        "name": "librispeech",
        "hf": "openslr/librispeech_asr",
        "config": "clean",
        "split": "validation",
    },
]


def _dirs() -> dict[str, Path]:
    s = get_settings()
    base = s.data_dir
    d = {
        "corpus": base / "corpus",
        "corpus_hf": base / "corpus_hf",
        "golden": base / "golden",
        "manifests": base / "manifests",
    }
    for p in d.values():
        p.mkdir(parents=True, exist_ok=True)
    return d


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------- synthetic ----
_SYNTHETIC_DOCS = {
    "pathrag.md": (
        "# PathRAG\n\nPathRAG is a graph-based retrieval-augmented generation method. "
        "It performs node retrieval to find seed entities, then relational path "
        "expansion across the knowledge graph, then flow-based pruning that allocates "
        "a resource budget from the seeds and keeps only high-flow paths. Each path is "
        "scored by reliability and rendered to text with golden-region ordering.\n\n"
        "## Hybrid retrieval\n\nAuralynq fuses dense and sparse vectors with reciprocal "
        "rank fusion, reranks with a cross-encoder, and applies maximal marginal "
        "relevance to remove redundancy before answering.\n"
    ),
    "geography.md": (
        "# Geography\n\nParis is the capital of France. France is a country in Europe. "
        "The Seine river flows through Paris. Berlin is the capital of Germany, which is "
        "also in Europe. The Rhine flows through Germany.\n"
    ),
    "auralynq.md": (
        "# Auralynq\n\nAuralynq is a local-first agentic voice RAG platform. It ingests "
        "documents and audio, builds a hybrid vector index in Qdrant and a relational "
        "knowledge graph, and answers questions through an adaptive agent that routes "
        "simple queries to hybrid retrieval and multi-hop queries to PathRAG. Answers "
        "include citations with source spans, speaker labels and timestamps.\n"
    ),
}

_SYNTHETIC_GOLDEN = [
    {
        "id": "q1",
        "question": "What is the capital of France?",
        "answer": "Paris",
        "type": "single",
        "supporting": ["geography.md"],
    },
    {
        "id": "q2",
        "question": "Which river flows through the capital of France?",
        "answer": "The Seine",
        "type": "multi",
        "supporting": ["geography.md"],
    },
    {
        "id": "q3",
        "question": "How does PathRAG prune relational paths?",
        "answer": "With a flow-based resource-allocation algorithm that keeps high-flow paths.",
        "type": "single",
        "supporting": ["pathrag.md"],
    },
    {
        "id": "q4",
        "question": "What does Auralynq use to remove redundant retrieved chunks?",
        "answer": "Maximal marginal relevance.",
        "type": "single",
        "supporting": ["auralynq.md"],
    },
    {
        "id": "q5",
        "question": "Which continent are France and Germany both in?",
        "answer": "Europe",
        "type": "multi",
        "supporting": ["geography.md"],
    },
]


def _write_synthetic_audio(corpus: Path) -> dict[str, Any]:
    """Write a real (silent) WAV plus a sidecar transcript for the voice path."""
    audio = corpus / "lecture_pathrag.wav"
    sr = 16_000
    duration = 6.0
    with wave.open(str(audio), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(sr * duration)):
            val = int(1500 * math.sin(2 * math.pi * 220 * i / sr) * (0.3 if i % 32000 else 1))
            frames += struct.pack("<h", val)
        wf.writeframes(bytes(frames))
    transcript = {
        "language": "en",
        "segments": [
            {
                "start_s": 0.0,
                "end_s": 3.2,
                "speaker": "SPEAKER_00",
                "text": "PathRAG performs flow based pruning of relational paths in the "
                "knowledge graph.",
            },
            {
                "start_s": 3.6,
                "end_s": 6.0,
                "speaker": "SPEAKER_01",
                "text": "Auralynq cites answers with speaker labels and timestamps.",
            },
        ],
    }
    (corpus / "lecture_pathrag.transcript.json").write_text(
        json.dumps(transcript, indent=2), encoding="utf-8"
    )
    return {"audio": str(audio), "segments": len(transcript["segments"])}


def _write_synthetic(dirs: dict[str, Path]) -> dict[str, Any]:
    for name, text in _SYNTHETIC_DOCS.items():
        (dirs["corpus"] / name).write_text(text, encoding="utf-8")
    (dirs["golden"] / "golden_qa.json").write_text(
        json.dumps({"version": 1, "frozen": True, "items": _SYNTHETIC_GOLDEN}, indent=2),
        encoding="utf-8",
    )
    audio_info = _write_synthetic_audio(dirs["corpus"])
    (dirs["golden"] / "asr_refs.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "audio": "lecture_pathrag.wav",
                        "reference": "PathRAG performs flow based pruning of relational paths "
                        "in the knowledge graph. Auralynq cites answers with "
                        "speaker labels and timestamps.",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"docs": list(_SYNTHETIC_DOCS), "golden_items": len(_SYNTHETIC_GOLDEN), **audio_info}


# ------------------------------------------------------------------ HF -------
def _try_hf_text(spec: dict, n: int, dirs: Path) -> dict[str, Any] | None:
    try:
        from datasets import load_dataset
    except ImportError:
        _log.info("data.datasets_missing", note="install auralynq[eval] for HF datasets")
        return None
    try:  # pragma: no cover - network path
        ds = load_dataset(spec["hf"], spec["config"], split=f"{spec['split']}[:{n}]")
    except Exception as exc:  # pragma: no cover
        _log.warning("data.skip", dataset=spec["name"], error=str(exc))
        return None
    written, golden = 0, []  # pragma: no cover
    for i, row in enumerate(ds):  # pragma: no cover
        q = row.get("question") or row.get("query") or ""
        ans = row.get("answer") or (row.get("answers") or {})
        context = _flatten_context(row)
        if not q or not context:
            continue
        doc = dirs / f"{spec['name']}_{i}.md"
        doc.write_text(f"# {spec['name']} {i}\n\n{context}\n", encoding="utf-8")
        written += 1
        golden.append(
            {
                "id": f"{spec['name']}_{i}",
                "question": q,
                "answer": ans if isinstance(ans, str) else json.dumps(ans),
                "type": "multi",
                "supporting": [doc.name],
            }
        )
    return {"written": written, "golden": golden}  # pragma: no cover


def _flatten_context(row: dict) -> str:  # pragma: no cover - network path
    ctx = row.get("context")
    if isinstance(ctx, dict):
        sentences = ctx.get("sentences") or []
        return " ".join(" ".join(s) if isinstance(s, list) else str(s) for s in sentences)
    if isinstance(ctx, str):
        return ctx
    paras = row.get("paragraphs")
    if isinstance(paras, list):
        return " ".join(
            p.get("paragraph_text", "") if isinstance(p, dict) else str(p) for p in paras
        )
    return ""


def download(sample: bool = True, full: bool = False) -> dict[str, Any]:
    configure_logging()
    dirs = _dirs()
    n = 200 if full else 20
    manifest: dict[str, Any] = {"mode": "full" if full else "sample", "datasets": {}}

    # Always lay down the curated synthetic corpus first (guarantees $0 offline).
    synth = _write_synthetic(dirs)
    manifest["datasets"]["synthetic"] = synth
    _log.info("data.synthetic_written", **{k: v for k, v in synth.items() if k != "docs"})

    # Best-effort HF augmentation. HF docs land in a *separate* corpus dir so the
    # default index/eval run on the curated synthetic corpus (clean, matches the
    # frozen golden set). Point AURALYNQ at data/corpus_hf for larger experiments.
    extra_golden: list[dict] = []
    for spec in TEXT_DATASETS:
        info = _try_hf_text(spec, n, dirs["corpus_hf"])
        if info:  # pragma: no cover - network path
            manifest["datasets"][spec["name"]] = {"written": info["written"]}
            extra_golden.extend(info["golden"][:5])

    # Keep the *frozen* golden set (golden_qa.json) curated and reproducible
    # (ADR-0010). HF-derived QA is written to a separate, optional file so the
    # drift baseline is stable regardless of upstream dataset availability.
    if extra_golden:  # pragma: no cover - network path
        (dirs["golden"] / "golden_qa_hf.json").write_text(
            json.dumps({"version": 1, "frozen": False, "items": extra_golden}, indent=2),
            encoding="utf-8",
        )

    manifest["checksums"] = {
        p.name: _sha256(p.read_text(encoding="utf-8", errors="ignore"))
        for p in sorted(dirs["corpus"].glob("*.md"))
    }
    (dirs["manifests"] / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    _log.info("data.done", corpus=str(dirs["corpus"]), docs=len(list(dirs["corpus"].glob("*"))))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Download Auralynq datasets.")
    ap.add_argument("--sample", action="store_true", default=True, help="small sample (default)")
    ap.add_argument("--full", action="store_true", help="larger subsets")
    args = ap.parse_args()
    download(sample=not args.full, full=args.full)


if __name__ == "__main__":
    main()
