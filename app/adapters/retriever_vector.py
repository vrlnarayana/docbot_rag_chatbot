"""Vector retriever: cosine similarity in NumPy over a cached matrix of chunk embeddings."""

import numpy as np
import numpy.typing as npt

from app.core.models import IndexedChunk, RetrievedChunk
from app.core.ports import Embedder


def _normalise(matrix: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


class VectorRetriever:
    name = "vector"

    def __init__(self, embedder: Embedder, min_score: float) -> None:
        self.min_score = min_score
        self._embedder = embedder
        self._index: tuple[npt.NDArray[np.float32] | None, list[IndexedChunk]] = (None, [])

    def refresh(self, chunks: list[IndexedChunk]) -> None:
        usable = [
            c
            for c in chunks
            if c.embedding is not None and c.embed_model == self._embedder.model_name
        ]
        matrix = (
            _normalise(np.asarray([c.embedding for c in usable], dtype=np.float32))
            if usable
            else None
        )
        self._index = (matrix, usable)  # swapped in one assignment

    def search(self, question: str, k: int) -> list[RetrievedChunk]:
        matrix, chunks = self._index
        if matrix is None:
            return []
        query = _normalise(np.asarray(self._embedder.embed([question])[0], dtype=np.float32))
        scores = matrix @ query
        ranked = np.argsort(-scores, kind="stable")[:k]
        return [
            RetrievedChunk(
                chunk=chunks[i].chunk, filename=chunks[i].filename, score=float(scores[i])
            )
            for i in ranked
        ]
