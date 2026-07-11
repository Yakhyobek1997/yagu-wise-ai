"""Cross-encoder reranking: BGE reranker / Cohere (optional) + lexical fallback."""

from __future__ import annotations

import abc
import importlib.util
import math
from collections import Counter

from auralynq.config import get_settings
from auralynq.retrieval.models import ScoredChunk
from auralynq.telemetry import get_logger
from auralynq.utils import tokenize

_log = get_logger("auralynq.rerank")


class Reranker(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def score(self, query: str, texts: list[str]) -> list[float]: ...

    def rerank(self, query: str, chunks: list[ScoredChunk], k: int) -> list[ScoredChunk]:
        if not chunks:
            return []
        scores = self.score(query, [c.chunk.text for c in chunks])
        rescored = [
            c.model_copy(update={"score": float(s), "method": f"rerank:{self.name}"})
            for c, s in zip(chunks, scores, strict=False)
        ]
        rescored.sort(key=lambda c: c.score, reverse=True)
        for i, c in enumerate(rescored[:k]):
            c.rank = i
        return rescored[:k]


class LexicalReranker(Reranker):
    """BM25-style lexical scorer — the $0 fallback."""

    name = "lexical"

    def score(self, query: str, texts: list[str]) -> list[float]:
        q_tokens = tokenize(query)
        q_set = set(q_tokens)
        n = len(texts)
        df: Counter[str] = Counter()
        doc_tokens = [tokenize(t) for t in texts]
        for toks in doc_tokens:
            for term in set(toks) & q_set:
                df[term] += 1
        out = []
        for toks in doc_tokens:
            counts = Counter(toks)
            dl = len(toks) or 1
            score = 0.0
            for term in q_set:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * dl / 50.0))
            out.append(score)
        return out


class BGEReranker(Reranker):  # pragma: no cover - heavy optional path
    name = "bge"

    def __init__(self, model: str = "BAAI/bge-reranker-v2-m3") -> None:
        from FlagEmbedding import FlagReranker

        self._model = FlagReranker(model, use_fp16=True)

    def score(self, query: str, texts: list[str]) -> list[float]:
        pairs = [[query, t] for t in texts]
        scores = self._model.compute_score(pairs, normalize=True)
        return [float(s) for s in (scores if isinstance(scores, list) else [scores])]


class CohereReranker(Reranker):  # pragma: no cover - paid path
    name = "cohere"

    def __init__(self, api_key: str, model: str = "rerank-v3.5") -> None:
        import cohere

        self._client = cohere.ClientV2(api_key)
        self._model = model
        self._lexical = LexicalReranker()  # call-time fallback

    def score(self, query: str, texts: list[str]) -> list[float]:
        try:
            resp = self._client.rerank(
                query=query, documents=texts, model=self._model, top_n=len(texts)
            )
            ordered = sorted(resp.results, key=lambda r: r.index)
            return [r.relevance_score for r in ordered]
        except Exception as exc:  # provider error must not break retrieval
            _log.warning("rerank.cohere_runtime_fallback_lexical", error=str(exc)[:160])
            return self._lexical.score(query, texts)


# Cohere's hosted reranker uses its own model ids, not a local BGE checkpoint.
# If the configured model looks like a local HF reranker, fall back to Cohere's
# default so a COHERE_API_KEY doesn't 404 on `BAAI/bge-reranker-*`.
_COHERE_DEFAULT_RERANK = "rerank-v3.5"


def _cohere_rerank_model(configured: str) -> str:
    if "/" in configured or configured.lower().startswith(("bge", "baai")):
        _log.info(
            "rerank.model_defaulted",
            provider="cohere",
            model=_COHERE_DEFAULT_RERANK,
            ignored=configured,
        )
        return _COHERE_DEFAULT_RERANK
    return configured


def build_reranker(provider: str | None = None) -> Reranker:
    s = get_settings()
    provider = provider or s.rerank.provider
    if provider == "auto":
        if s.cohere_api_key and importlib.util.find_spec("cohere"):
            provider = "cohere"
        elif importlib.util.find_spec("FlagEmbedding"):
            provider = "bge"
        else:
            provider = "lexical"
    try:
        if provider == "cohere":
            return CohereReranker(s.cohere_api_key, _cohere_rerank_model(s.rerank.model))
        if provider == "bge":
            return BGEReranker(s.rerank.model)
        if provider == "none":
            return LexicalReranker()
    except Exception as exc:  # pragma: no cover
        _log.warning("rerank.fallback_lexical", error=str(exc))
    return LexicalReranker()
