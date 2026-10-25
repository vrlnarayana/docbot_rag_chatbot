"""Ports owned by the core. Adapters implement them; the API wires one of each at startup."""

from typing import Protocol

from app.core.models import (
    ChatTurn,
    Chunk,
    Document,
    GeneratedAnswer,
    IndexedChunk,
    Page,
    RetrievedChunk,
)


class DocumentRepository(Protocol):
    async def add(
        self,
        document: Document,
        chunks: list[Chunk],
        embeddings: list[list[float]] | None,
        embed_model: str | None,
    ) -> None: ...

    async def get(self, document_id: str) -> Document | None: ...

    async def get_by_sha256(self, sha256: str) -> Document | None: ...

    async def list_all(self) -> list[Document]: ...

    async def chunks(self, document_id: str) -> list[Chunk]: ...

    async def delete(self, document_id: str) -> Document | None: ...

    async def counts(self) -> tuple[int, int]: ...

    async def indexed_chunks(self) -> list[IndexedChunk]: ...

    async def set_embeddings(
        self, embeddings: dict[str, list[float]], embed_model: str
    ) -> None: ...


class FileStore(Protocol):
    async def save(self, data: bytes, extension: str) -> str:
        """Store bytes under a generated name and return that name."""
        ...

    async def delete(self, stored_name: str) -> None: ...


class Extractor(Protocol):
    def extract(self, data: bytes, extension: str) -> list[Page]:
        """Blocking; callers run it in a worker thread."""
        ...


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Blocking; callers run it in a worker thread."""
        ...


class Retriever(Protocol):
    name: str
    min_score: float

    def refresh(self, chunks: list[IndexedChunk]) -> None: ...

    def search(self, question: str, k: int) -> list[RetrievedChunk]:
        """Blocking; callers run it in a worker thread."""
        ...


class Generator(Protocol):
    name: str

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer: ...


class QuestionRewriter(Protocol):
    """FR-070: turns a follow-up into a standalone question, or returns None if it cannot."""

    async def rewrite(self, question: str, history: list[ChatTurn]) -> str | None: ...
