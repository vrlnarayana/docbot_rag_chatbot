"""Keyword retriever: BM25 over all chunks, rebuilt in memory on refresh (FR-011)."""

from rank_bm25 import BM25Okapi

from app.core.models import IndexedChunk, RetrievedChunk
from app.core.text import tokenize


class Bm25Retriever:
    name = "keyword"

    def __init__(self, min_score: float) -> None:
        self.min_score = min_score
        self._index: tuple[BM25Okapi | None, list[IndexedChunk]] = (None, [])

    def refresh(self, chunks: list[IndexedChunk]) -> None:
        bm25 = BM25Okapi([tokenize(c.chunk.text) for c in chunks]) if chunks else None
        self._index = (bm25, list(chunks))  # swapped in one assignment

    def search(self, question: str, k: int) -> list[RetrievedChunk]:
        bm25, chunks = self._index
        terms = tokenize(question)
        if bm25 is None or not terms:
            return []
        scores = bm25.get_scores(terms)
        ranked = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))[:k]
        return [
            RetrievedChunk(
                chunk=chunks[i].chunk, filename=chunks[i].filename, score=float(scores[i])
            )
            for i in ranked
            if scores[i] > 0
        ]
