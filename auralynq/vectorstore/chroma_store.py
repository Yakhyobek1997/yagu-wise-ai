"""ChromaDB-backed vector store — local persistent store, no server required."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from auralynq.embeddings.base import EmbeddingBatch, SparseVector
from auralynq.ingest.models import Chunk
from auralynq.retrieval.models import Filter, ScoredChunk
from auralynq.telemetry import get_logger
from auralynq.vectorstore.base import VectorStore

_log = get_logger("auralynq.vectorstore.chroma")


class ChromaStore(VectorStore):
    backend = "chroma"

    def __init__(
        self,
        persist_dir: str | Path = "./data/vectorstore",
        collection: str = "auralynq",
    ) -> None:
        import chromadb

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection_name = collection
        self._collection = None
        self._dim = 0

    def ensure_collection(self, dim: int) -> None:
        self._dim = dim
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )

    def _col(self):
        if self._collection is None:
            self.ensure_collection(self._dim)
        return self._collection

    # ---------------------------------------------------------------- write --

    def upsert(self, chunks: list[Chunk], embeddings: EmbeddingBatch) -> int:
        if not chunks:
            return 0
        self.ensure_collection(int(embeddings.dense.shape[1]))
        self._col().upsert(
            ids=[c.id for c in chunks],
            embeddings=embeddings.dense.tolist(),
            documents=[c.text for c in chunks],
            metadatas=[self._chunk_to_meta(c) for c in chunks],
        )
        _log.info("chroma.upsert", n=len(chunks))
        return len(chunks)

    @staticmethod
    def _chunk_to_meta(chunk: Chunk) -> dict[str, Any]:
        return {
            "doc_id": chunk.doc_id,
            "source": chunk.source,
            "source_type": chunk.source_type.value,
            "page": chunk.span.page if chunk.span.page is not None else -1,
            "ordinal": chunk.ordinal,
            "title": chunk.title or "",
            "_chunk_json": chunk.model_dump_json(),
        }

    @staticmethod
    def _meta_to_chunk(chunk_id: str, document: str, metadata: dict) -> Chunk:
        if "_chunk_json" in metadata:
            try:
                return Chunk.model_validate_json(metadata["_chunk_json"])
            except Exception:
                pass
        from auralynq.ingest.models import SourceType

        return Chunk(
            id=chunk_id,
            doc_id=metadata.get("doc_id", ""),
            text=document,
            source=metadata.get("source", ""),
            source_type=SourceType(metadata.get("source_type", "unknown")),
        )

    # --------------------------------------------------------------- search --

    def search_dense(
        self, dense: np.ndarray, k: int, filt: Filter | None = None
    ) -> list[ScoredChunk]:
        col = self._col()
        n = col.count()
        if n == 0:
            return []
        where = self._build_where(filt)
        kwargs: dict[str, Any] = {
            "query_embeddings": [dense.tolist()],
            "n_results": min(k, n),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        try:
            results = col.query(**kwargs)
        except Exception as exc:
            _log.warning("chroma.query_failed", error=str(exc))
            return []

        scored: list[ScoredChunk] = []
        for i, cid in enumerate(results["ids"][0]):
            chunk = self._meta_to_chunk(cid, results["documents"][0][i], results["metadatas"][0][i])
            score = max(0.0, 1.0 - float(results["distances"][0][i]))
            scored.append(ScoredChunk(chunk=chunk, score=score, method="dense", rank=i))
        return scored

    def search_sparse(
        self, sparse: SparseVector, k: int, filt: Filter | None = None
    ) -> list[ScoredChunk]:
        # ChromaDB is dense-only; the hybrid fusion in VectorStore.search handles empty sparse.
        return []

    @staticmethod
    def _build_where(filt: Filter | None) -> dict | None:
        if not filt:
            return None
        conditions: list[dict] = []
        if filt.doc_ids:
            conditions.append({"doc_id": {"$in": list(filt.doc_ids)}})
        if filt.source_types:
            conditions.append({"source_type": {"$in": list(filt.source_types)}})
        for k, v in (filt.must or {}).items():
            conditions.append({k: {"$eq": v}})
        if not conditions:
            return None
        return conditions[0] if len(conditions) == 1 else {"$and": conditions}

    # ---------------------------------------------------------------- misc ---

    def count(self) -> int:
        try:
            return self._col().count()
        except Exception:
            return 0

    def clear(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._collection = None

    def delete_by_doc_id(self, doc_id: str) -> int:
        try:
            results = self._col().get(where={"doc_id": {"$eq": doc_id}})
            ids = results["ids"]
            if ids:
                self._col().delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    def get(self, chunk_id: str) -> Chunk | None:
        try:
            results = self._col().get(ids=[chunk_id], include=["documents", "metadatas"])
            if results["ids"]:
                return self._meta_to_chunk(
                    results["ids"][0], results["documents"][0], results["metadatas"][0]
                )
        except Exception:
            pass
        return None

    def all_chunks(self) -> list[Chunk]:
        try:
            results = self._col().get(include=["documents", "metadatas"])
            return [
                self._meta_to_chunk(cid, doc, meta)
                for cid, doc, meta in zip(
                    results["ids"], results["documents"], results["metadatas"], strict=True
                )
            ]
        except Exception:
            return []
