"""Local embedding generation for candidate and JD text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None

from src.utils import get_logger

LOGGER = get_logger(__name__)


@dataclass(slots=True)
class EmbeddingArtifacts:
    vectors: np.ndarray
    ids: list[str]
    texts: list[str] | None = None


class EmbeddingModel:
    def __init__(self, model_name: str, lsa_components: int = 256, force_fallback: bool = False) -> None:
        self.model_name = model_name
        self.lsa_components = lsa_components
        
        import torch
        device = "cpu"
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            
        LOGGER.info("Initializing EmbeddingModel on device: %s", device)
        if device == "cuda":
            LOGGER.info("CUDA Device details: %s", torch.cuda.get_device_name(0))
            
        self.model = None if force_fallback else (SentenceTransformer(model_name, device=device) if SentenceTransformer else None)

    def encode(self, texts: list[str], batch_size: int = 64, normalize: bool = True) -> np.ndarray:
        if self.model is not None:
            vectors = self.model.encode(texts, batch_size=batch_size, normalize_embeddings=normalize, show_progress_bar=True)
            return np.asarray(vectors, dtype=np.float32)
        return self._hashed_embeddings(texts)

    @staticmethod
    def _hashed_embeddings(texts: list[str], dim: int = 384) -> np.ndarray:
        vectors = np.zeros((len(texts), dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in text.lower().split():
                vectors[row, hash(token) % dim] += 1.0
            norm = np.linalg.norm(vectors[row])
            if norm > 0:
                vectors[row] /= norm
        return vectors


def save_embeddings(path: str | Path, artifacts: EmbeddingArtifacts) -> None:
    """Persist candidate vectors and their ordering information."""
    path = Path(path)
    tmp_path = path.with_name(path.name + ".tmp.npz")
    np.savez(
        tmp_path,
        vectors=artifacts.vectors,
        ids=np.array(artifacts.ids),
    )
    tmp_path.replace(path)


def load_embeddings(path: str | Path) -> EmbeddingArtifacts:
    """Load artifacts previously written by :func:`save_embeddings`."""
    with np.load(path, allow_pickle=True) as stored:
        texts = stored["texts"].tolist() if "texts" in stored else []
        return EmbeddingArtifacts(
            vectors=np.asarray(stored["vectors"], dtype=np.float32),
            ids=stored["ids"].tolist(),
            texts=texts,
        )


def load_embedding_ids(path: str | Path) -> list[str]:
    """Load only the candidate IDs from a persisted embeddings file."""
    with np.load(path, allow_pickle=True) as stored:
        return stored["ids"].tolist()

