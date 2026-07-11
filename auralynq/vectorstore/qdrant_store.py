"""Qdrant vector store (optional, requires the ``vector`` extra + a running server).

Uses named vectors: a ``dense`` vector and a ``sparse`` lexical vector for true
hybrid retrieval. Supports payload indexes, metadata filters, and scalar/binary
quantization (benchmarked by ``make bench``). Falls back to MemoryStore upstream
if the server/library is unavailable (see factory).
"""

from __future__ import annotations

import contextlib
from typing import Any

import numpy as np

from auralynq.config import get_settings
from auralynq.embeddings.base import EmbeddingBatch, SparseVector
from auralynq.ingest.models import Chunk
from auralynq.retrieval.models import Filter, ScoredChunk
from auralynq.telemetry import get_logger
from auralynq.vectorstore.base import VectorStore

_log = get_logger("auralynq.vectorstore.qdrant")
DENSE = "dense"
SPARSE = "sparse"


class QdrantStore(VectorStore):
    backend = "qdrant"

    def __init__(
        self, url: str | None = None, collection: str | None = None, quantization: str = "none"
    ) -> None:
        from qdrant_client import QdrantClient

        s = get_settings()
        self.collection = collection or s.vector.collection
        self.quantization = quantization or s.vector.quantization
        self._hnsw_m = s.vector.hnsw_m
        self.client = QdrantClient(url=url or s.vector.url, timeout=30)
        self._dim = 0
        self._exists_cached = False
        _log.info("qdrant.connected", url=url or s.vector.url, collection=self.collection)

    def _exists(self) -> bool:
        # Memoize the positive result: a present collection isn't dropped under
        # search traffic, so we skip one Qdrant RPC per query. clear() resets it.
        if self._exists_cached:
            return True
        if self.client.collection_exists(self.collection):
            self._exists_cached = True
            return True
        return False

    def ensure_collection(self, dim: int) -> None:
        from qdrant_client import models as qm

        self._dim = dim
        if self.client.collection_exists(self.collection):
            self._exists_cached = True
            return

        quant: Any = None  # qdrant accepts several quantization config types
        if self.quantization == "scalar":
            quant = qm.ScalarQuantization(
                scalar=qm.ScalarQuantizationConfig(type=qm.ScalarType.INT8, always_ram=True)
            )
        elif self.quantization == "binary":
            quant = qm.BinaryQuantization(binary=qm.BinaryQuantizationConfig(always_ram=True))

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                DENSE: qm.VectorParams(
                    size=dim,
                    distance=qm.Distance.COSINE,
                    hnsw_config=qm.HnswConfigDiff(m=self._hnsw_m),
                )
            },
            sparse_vectors_config={
                SPARSE: qm.SparseVectorParams(index=qm.SparseIndexParams(on_disk=False))
            },
            quantization_config=quant,
        )
        for field, schema in (
            ("doc_id", qm.PayloadSchemaType.KEYWORD),
            ("source_type", qm.PayloadSchemaType.KEYWORD),
            ("speaker", qm.PayloadSchemaType.KEYWORD),
        ):
            with contextlib.suppress(Exception):  # index may already exist
                self.client.create_payload_index(self.collection, field, schema)
        self._exists_cached = True

    def upsert(self, chunks: list[Chunk], embeddings: EmbeddingBatch) -> int:
        from qdrant_client import models as qm

        if not chunks:
            return 0
        self.ensure_collection(int(embeddings.dense.shape[1]))
        points = []
        for i, ch in enumerate(chunks):
            sparse = embeddings.sparse[i] if embeddings.sparse else {}
            points.append(
                qm.PointStruct(
                    id=_uuid(ch.id),
                    vector={
                        DENSE: embeddings.dense[i].tolist(),
                        SPARSE: qm.SparseVector(
                            indices=list(sparse.keys()),
                            values=[float(v) for v in sparse.values()],
                        ),
                    },
                    payload=_payload(ch),
                )
            )
        self.client.upsert(self.collection, points=points, wait=True)
        return len(points)

    def _filter(self, filt: Filter | None):
        from qdrant_client import models as qm

        if filt is None:
            return None
        must = []
        if filt.doc_ids:
            must.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=filt.doc_ids)))
        if filt.source_types:
            must.append(
                qm.FieldCondition(key="source_type", match=qm.MatchAny(any=filt.source_types))
            )
        for k, v in filt.must.items():
            must.append(qm.FieldCondition(key=k, match=qm.MatchValue(value=v)))
        return qm.Filter(must=must) if must else None

    def search_dense(self, dense, k: int, filt: Filter | None = None) -> list[ScoredChunk]:
        if not self._exists():
            return []
        res = self.client.query_points(
            self.collection,
            query=np.asarray(dense).tolist(),
            using=DENSE,
            limit=k,
            with_payload=True,
            query_filter=self._filter(filt),
        )
        return _to_scored(res.points, "dense")

    def search_sparse(
        self, sparse: SparseVector, k: int, filt: Filter | None = None
    ) -> list[ScoredChunk]:
        from qdrant_client import models as qm

        if not sparse or not self._exists():
            return []
        res = self.client.query_points(
            self.collection,
            query=qm.SparseVector(
                indices=list(sparse.keys()), values=[float(v) for v in sparse.values()]
            ),
            using=SPARSE,
            limit=k,
            with_payload=True,
            query_filter=self._filter(filt),
        )
        return _to_scored(res.points, "sparse")

    def get(self, chunk_id: str) -> Chunk | None:
        try:
            pts = self.client.retrieve(self.collection, ids=[_uuid(chunk_id)], with_payload=True)
        except Exception:  # pragma: no cover
            return None
        if not pts:
            return None
        payload = dict(pts[0].payload or {})
        payload.pop("speaker", None)
        return Chunk.model_validate(payload)

    def count(self) -> int:
        # A not-yet-created collection means an empty index (don't 404).
        if not self._exists():
            return 0
        return int(self.client.count(self.collection, exact=True).count)

    def all_chunks(self, max_points: int = 20_000) -> list[Chunk]:
        """Scroll the whole collection and reconstruct chunks from their full
        payload. Enables rebuilding the knowledge graph and synthesizing the
        Compounding Wiki from an existing remote index (not just fresh ingests).
        Bounded to stay tractable on large collections; best-effort."""
        if not self._exists():
            return []
        out: list[Chunk] = []
        offset: Any = None
        try:
            while len(out) < max_points:
                points, offset = self.client.scroll(
                    self.collection,
                    limit=512,
                    with_payload=True,
                    with_vectors=False,
                    offset=offset,
                )
                if not points:
                    break
                for p in points:
                    payload = dict(p.payload or {})
                    payload.pop("speaker", None)
                    try:
                        out.append(Chunk.model_validate(payload))
                    except Exception:
                        continue
                if offset is None:
                    break
        except Exception:  # pragma: no cover - defensive; best-effort enumeration
            pass
        return out

    def document_facts(self, max_points: int = 20_000) -> dict[str, Any]:
        """Distinct source documents + source-type histogram via a bounded scroll.

        ``all_chunks`` returns nothing for the remote store (rebuilding the KG
        from a full payload pull would be wasteful), but corpus stats only need
        payload metadata — so scroll just the source/doc_id/type fields. Bounded
        to keep the corpus-summary call cheap on large indices.
        """
        if not self._exists():
            return {"titles": [], "source_types": {}}
        titles: list[str] = []
        seen: set[str] = set()
        stype: dict[str, int] = {}
        offset: Any = None
        scanned = 0
        try:
            while scanned < max_points:
                points, offset = self.client.scroll(
                    self.collection,
                    limit=512,
                    with_payload=["source", "title", "doc_id", "source_type"],
                    with_vectors=False,
                    offset=offset,
                )
                if not points:
                    break
                for p in points:
                    scanned += 1
                    pl = p.payload or {}
                    src = str(pl.get("title") or pl.get("source") or pl.get("doc_id") or "").strip()
                    st = str(pl.get("source_type") or "unknown")
                    stype[st] = stype.get(st, 0) + 1
                    if src and src not in seen:
                        seen.add(src)
                        titles.append(src)
                if offset is None:
                    break
        except Exception:  # pragma: no cover - defensive; stats are best-effort
            pass
        return {"titles": titles[:200], "source_types": stype}

    def clear(self) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self._exists_cached = False

    def delete_by_doc_id(self, doc_id: str) -> int:
        from qdrant_client import models as qm

        if not self._exists():
            return 0
        before = self.count()
        self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]
                )
            ),
            wait=True,
        )
        after = self.count()
        return max(0, before - after)


def _uuid(chunk_id: str) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _payload(ch: Chunk) -> dict[str, Any]:
    p = ch.model_dump(mode="json")
    p["speaker"] = ch.audio.speaker if ch.audio else None
    p["source_type"] = ch.source_type.value
    return p


def _to_scored(points, method: str) -> list[ScoredChunk]:
    out: list[ScoredChunk] = []
    for rank, pt in enumerate(points):
        payload = dict(pt.payload or {})
        payload.pop("speaker", None)
        ch = Chunk.model_validate(payload)
        out.append(ScoredChunk(chunk=ch, score=float(pt.score), method=method, rank=rank))
    return out
