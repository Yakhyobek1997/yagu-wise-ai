"""RAG answer-quality metrics.

Uses Ragas when installed *and* a real LLM is configured; otherwise computes
deterministic, dependency-free proxies so a number is always produced (clearly
labelled with the provider used, per ADR-0010):

* faithfulness        — fraction of answer tokens supported by the context
* answer_relevancy    — cosine(answer, question) embeddings
* context_precision   — fraction of retrieved contexts that overlap the answer
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from auralynq.config import get_settings
from auralynq.embeddings.factory import get_embedder
from auralynq.utils import tokenize

_STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "on", "and", "or", "that"}


@dataclass
class RagasScores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    provider: str
    n: int


def _faithfulness(answer: str, contexts: list[str]) -> float:
    a = {t for t in tokenize(answer) if t not in _STOP and len(t) > 2}
    if not a:
        return 0.0
    ctx = set()
    for c in contexts:
        ctx |= set(tokenize(c))
    return len(a & ctx) / len(a)


def _answer_relevancy(answer: str, question: str) -> float:
    if not answer.strip():
        return 0.0
    emb = get_embedder()
    return max(0.0, emb.cosine(emb.embed_query(answer).dense, emb.embed_query(question).dense))


def _context_precision(answer: str, contexts: list[str]) -> float:
    if not contexts:
        return 0.0
    a = {t for t in tokenize(answer) if t not in _STOP and len(t) > 2}
    if not a:
        return 0.0
    relevant = sum(1 for c in contexts if a & set(tokenize(c)))
    return relevant / len(contexts)


def proxy_scores(samples: list[dict]) -> RagasScores:
    n = len(samples) or 1
    f = sum(_faithfulness(s["answer"], s["contexts"]) for s in samples) / n
    ar = sum(_answer_relevancy(s["answer"], s["question"]) for s in samples) / n
    cp = sum(_context_precision(s["answer"], s["contexts"]) for s in samples) / n
    return RagasScores(round(f, 4), round(ar, 4), round(cp, 4), "proxy", len(samples))


def evaluate(samples: list[dict]) -> RagasScores:
    """samples: [{question, answer, contexts:[str], ground_truth?}]."""
    s = get_settings()
    real_llm = s.llm.provider not in ("extractive",) and (
        s.openai_api_key or s.anthropic_api_key or s.llm.provider == "ollama"
    )
    if importlib.util.find_spec("ragas") and real_llm:  # pragma: no cover - heavy/paid
        try:
            return _ragas_real(samples)
        except Exception:
            pass
    return proxy_scores(samples)


def _ragas_real(samples: list[dict]) -> RagasScores:  # pragma: no cover - heavy/paid
    from datasets import Dataset
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    ds = Dataset.from_list(
        [
            {
                "question": s["question"],
                "answer": s["answer"],
                "contexts": s["contexts"],
                "ground_truth": s.get("ground_truth", ""),
            }
            for s in samples
        ]
    )
    res = ragas_evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])
    df = res.to_pandas()
    return RagasScores(
        faithfulness=round(float(df["faithfulness"].mean()), 4),
        answer_relevancy=round(float(df["answer_relevancy"].mean()), 4),
        context_precision=round(float(df["context_precision"].mean()), 4),
        provider="ragas",
        n=len(samples),
    )
