"""In-process numpy vector store — the $0 offline fallback (ADR-0003).

Brute-force dense (cosine) and sparse (dot-product) search with metadata filters.
Persists to ``<index_dir>/memory_store/`` as npy + json so ``make index`` builds a
durable index that survives across processes. Fast enough for laptop-scale corpora.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from auralynq.config import get_settings
from auralynq.embeddings.base import EmbeddingBatch, SparseVector
from auralynq.ingest.models import Chunk
from auralynq.retrieval.models import Filter, ScoredChunk
from auralynq.telemetry import get_logger
from auralynq.vectorstore.base import VectorStore

_log = get_logger("auralynq.vectorstore.memory")


class MemoryStore(VectorStore):
    backend = "memory"

    def __init__(self, path: Path | None = None) -> None:
        s = get_settings()
        self.path = path or (s.index_dir / "memory_store")
        self._chunks: dict[str, Chunk] = {}
        self._order: list[str] = []
        self._dense: np.ndarray | None = None
        self._sparse: list[SparseVector] = []
        self._vec: dict[str, np.ndarray] = {}
        self._spvec: dict[str, SparseVector] = {}
        self._dim = 0
        self.load()

    # --------------------------------------------------------------- io ----
    def ensure_collection(self, dim: int) -> None:
        self._dim = dim
        if self._dense is None:
            self._dense = np.zeros((0, dim), dtype=np.float32)

    def upsert(self, chunks: list[Chunk], embeddings: EmbeddingBatch) -> int:
        if not chunks:
            return 0
        self.ensure_collection(int(embeddings.dense.shape[1]))
        for ch in chunks:
            if ch.id not in self._chunks:
                self._order.append(ch.id)
            self._chunks[ch.id] = ch
        # Rebuild dense matrix + sparse list aligned to self._order.
        self._reindex(chunks, embeddings)
        return len(chunks)

    def _reindex(self, new_chunks: list[Chunk], emb: EmbeddingBatch) -> None:
        new_dense = {c.id: emb.dense[i] for i, c in enumerate(new_chunks)}
        new_sparse = {c.id: emb.sparse[i] for i, c in enumerate(new_chunks)} if emb.sparse else {}
        # Keep parallel dicts of vectors so re-indexing preserves prior upserts.
        self._vec.update(new_dense)
        self._spvec.update(new_sparse)
        mat = (
            np.stack([self._vec[cid] for cid in self._order])
            if self._order
            else np.zeros((0, self._dim), dtype=np.float32)
        )
        self._dense = mat.astype(np.float32)
        self._sparse = [self._spvec.get(cid, {}) for cid in self._order]

    # ----------------------------------------------------------- search ----
    def _passes(self, ch: Chunk, filt: Filter | None) -> bool:
        if filt is None:
            return True
        if filt.doc_ids is not None and ch.doc_id not in filt.doc_ids:
            return False
        if filt.source_types is not None and ch.source_type.value not in filt.source_types:
            return False
        return all(ch.metadata.get(key) == val for key, val in filt.must.items())

    def search_dense(self, dense, k: int, filt: Filter | None = None) -> list[ScoredChunk]:
        if self._dense is None or self._dense.shape[0] == 0:
            return []
        q = np.asarray(dense, dtype=np.float32)
        qn = np.linalg.norm(q) or 1.0
        mat = self._dense
        norms = np.linalg.norm(mat, axis=1)
        norms[norms == 0] = 1.0
        sims = (mat @ q) / (norms * qn)
        return self._topk(sims, k, filt, "dense")

    def search_sparse(
        self, sparse: SparseVector, k: int, filt: Filter | None = None
    ) -> list[ScoredChunk]:
        if not self._order:
            return []
        scores = np.zeros(len(self._order), dtype=np.float32)
        for i, sp in enumerate(self._sparse):
            if not sp:
                continue
            scores[i] = sum(w * sp.get(t, 0.0) for t, w in sparse.items())
        return self._topk(scores, k, filt, "sparse")

    def _topk(
        self, scores: np.ndarray, k: int, filt: Filter | None, method: str
    ) -> list[ScoredChunk]:
        order = np.argsort(-scores)
        out: list[ScoredChunk] = []
        for idx in order:
            cid = self._order[int(idx)]
            ch = self._chunks[cid]
            if not self._passes(ch, filt):
                continue
            out.append(
                ScoredChunk(chunk=ch, score=float(scores[idx]), method=method, rank=len(out))
            )
            if len(out) >= k:
                break
        return out

    def get(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    def all_chunks(self) -> list[Chunk]:
        return [self._chunks[cid] for cid in self._order]

    def count(self) -> int:
        return len(self._order)

    def clear(self) -> None:
        self._chunks.clear()
        self._order.clear()
        self._sparse.clear()
        self._dense = np.zeros((0, self._dim), dtype=np.float32)
        if hasattr(self, "_vec"):
            self._vec.clear()
            self._spvec.clear()

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Remove all chunks for *doc_id* and rebuild the dense/sparse matrices."""
        to_remove = [cid for cid, ch in self._chunks.items() if ch.doc_id == doc_id]
        if not to_remove:
            return 0
        for cid in to_remove:
            self._chunks.pop(cid, None)
            self._vec.pop(cid, None)
            self._spvec.pop(cid, None)
        self._order = [cid for cid in self._order if cid not in set(to_remove)]
        if self._order:
            self._dense = np.stack([self._vec[cid] for cid in self._order]).astype(np.float32)
            self._sparse = [self._spvec.get(cid, {}) for cid in self._order]
        else:
            self._dense = np.zeros((0, self._dim), dtype=np.float32)
            self._sparse = []
        return len(to_remove)

    # --------------------------------------------------------- persist -----
    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        np.save(
            self.path / "dense.npy",
            self._dense if self._dense is not None else np.zeros((0, self._dim), dtype=np.float32),
        )
        (self.path / "chunks.json").write_text(
            json.dumps(
                {
                    "dim": self._dim,
                    "order": self._order,
                    "chunks": {cid: self._chunks[cid].model_dump() for cid in self._order},
                    "sparse": [{str(k): v for k, v in sp.items()} for sp in self._sparse],
                }
            ),
            encoding="utf-8",
        )
        _log.info("memory_store.saved", n=len(self._order), path=str(self.path))

    def load(self) -> None:
        meta_p = self.path / "chunks.json"
        dense_p = self.path / "dense.npy"
        if not meta_p.exists() or not dense_p.exists():
            return
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        self._dim = meta["dim"]
        self._order = meta["order"]
        self._chunks = {cid: Chunk.model_validate(c) for cid, c in meta["chunks"].items()}
        self._sparse = [{int(k): float(v) for k, v in sp.items()} for sp in meta["sparse"]]
        self._dense = np.load(dense_p)
        self._vec = {cid: self._dense[i] for i, cid in enumerate(self._order)}
        self._spvec = {cid: self._sparse[i] for i, cid in enumerate(self._order)}
        _log.info("memory_store.loaded", n=len(self._order))
