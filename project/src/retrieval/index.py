"""FAISS candidate retrieval index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None


@dataclass(slots=True)
class RetrievalHit:
    candidate_id: str
    score: float


class CandidateIndex:
    def __init__(self) -> None:
        self.index: Any = None
        self.candidate_ids: list[str] = []

    def build(self, vectors: np.ndarray, candidate_ids: list[str]) -> None:
        self.candidate_ids = list(candidate_ids)
        if faiss is None:
            self.index = {"vectors": vectors.astype(np.float32, copy=False)}
            return
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors.astype(np.float32, copy=False))

    def save(self, path: str | Path) -> None:
        """Persist the index.  The NumPy fallback remains usable without FAISS."""
        output = Path(path)
        if isinstance(self.index, dict):
            np.savez_compressed(output, vectors=self.index["vectors"], candidate_ids=np.array(self.candidate_ids))
            return
        if faiss is None or self.index is None:
            raise RuntimeError("Cannot save an unbuilt FAISS index")
        faiss.write_index(self.index, str(output))

    def load(self, path: str | Path, candidate_ids: list[str]) -> None:
        """Load a persisted index whose candidate ordering has been validated by the caller."""
        source = Path(path)
        self.candidate_ids = list(candidate_ids)
        if source.suffix == ".npz":
            with np.load(source) as stored:
                stored_ids = stored["candidate_ids"].tolist()
                if stored_ids != self.candidate_ids:
                    raise ValueError("Cached index candidate IDs do not match the requested candidates")
                self.index = {"vectors": np.asarray(stored["vectors"], dtype=np.float32)}
            return
        if faiss is None:
            raise RuntimeError("FAISS is required to load the cached FAISS index")
        self.index = faiss.read_index(str(source))
        if self.index.ntotal != len(self.candidate_ids):
            raise ValueError(f"FAISS index size ({self.index.ntotal}) does not match candidate count ({len(self.candidate_ids)})")

    def search(self, query_vector: np.ndarray, top_k: int = 100) -> list[RetrievalHit]:
        if isinstance(self.index, dict):
            vectors = self.index["vectors"]
            scores = vectors @ query_vector.astype(np.float32)
            order = np.argsort(-scores)[:top_k]
            return [RetrievalHit(self.candidate_ids[i], float(scores[i])) for i in order]
        scores, indices = self.index.search(query_vector.astype(np.float32).reshape(1, -1), top_k)
        return [RetrievalHit(self.candidate_ids[int(idx)], float(score)) for idx, score in zip(indices[0], scores[0]) if idx >= 0]
