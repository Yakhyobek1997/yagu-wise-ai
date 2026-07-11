"""Retriever protocol shared by naive / hybrid / PathRAG retrievers."""

from __future__ import annotations

import abc
import time

from auralynq.retrieval.models import Filter, RetrievalResult


class Retriever(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def retrieve(self, query: str, k: int, filt: Filter | None = None) -> RetrievalResult: ...

    @staticmethod
    def _timer() -> float:
        return time.perf_counter()
