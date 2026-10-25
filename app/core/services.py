"""Use cases: ingestion, question answering and evaluation (plan §7)."""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

import anyio

from app.core.chunking import chunk_pages
from app.core.errors import FileTooLarge, NoTextExtracted, UnsupportedFileType
from app.core.models import Chunk, DocType, Document
from app.core.ports import DocumentRepository, Embedder, Extractor, FileStore, Retriever

_TYPES: dict[str, tuple[DocType, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".txt": ("text", "text/plain"),
    ".md": ("text", "text/markdown"),
}


class IngestionService:
    def __init__(
        self,
        repository: DocumentRepository,
        file_store: FileStore,
        extractors: dict[DocType, Extractor],
        embedder: Embedder | None,
        retriever: Retriever | None,
        chunk_size: int,
        chunk_overlap: int,
        max_upload_bytes: int,
    ) -> None:
        self._repo = repository
        self._files = file_store
        self._extractors = extractors
        self._embedder = embedder
        self.retriever = retriever
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._max_bytes = max_upload_bytes

    def check_upload(self, filename: str) -> str:
        """FR-002: return the lower-case extension, or raise if it is not supported."""
        extension = PurePath(filename).suffix.lower()
        if extension not in _TYPES:
            raise UnsupportedFileType(extension)
        return extension

    async def ingest(self, filename: str, data: bytes) -> tuple[Document, bool]:
        """Index one file. Returns the document and whether it was already indexed."""
        extension = self.check_upload(filename)
        if len(data) > self._max_bytes:
            raise FileTooLarge(self._max_bytes // (1024 * 1024))

        sha256 = hashlib.sha256(data).hexdigest()
        existing = await self._repo.get_by_sha256(sha256)
        if existing:
            return existing, True

        doc_type, mime_type = _TYPES[extension]
        extractor = self._extractors[doc_type]
        pages = await anyio.to_thread.run_sync(extractor.extract, data, extension)
        if not any(p.text.strip() for p in pages):
            raise NoTextExtracted()

        document_id = str(uuid.uuid4())
        drafts = chunk_pages(pages, self._chunk_size, self._chunk_overlap)
        chunks = [
            Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                page=d.page,
                ordinal=i,
                source=d.source,
                text=d.text,
            )
            for i, d in enumerate(drafts)
        ]
        embeddings = None
        if self._embedder:
            embeddings = await anyio.to_thread.run_sync(
                self._embedder.embed, [c.text for c in chunks]
            )

        stored_name = await self._files.save(data, extension)
        document = Document(
            id=document_id,
            filename=filename,
            stored_name=stored_name,
            doc_type=doc_type,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=sha256,
            page_count=len(pages),
            ocr_page_count=sum(1 for p in pages if p.source == "ocr"),
            chunk_count=len(chunks),
            status="indexed",
            created_at=datetime.now(UTC),
        )
        try:
            await self._repo.add(
                document, chunks, embeddings, self._embedder.model_name if self._embedder else None
            )
        except Exception:
            await self._files.delete(stored_name)
            raced = await self._repo.get_by_sha256(sha256)  # same bytes uploaded concurrently
            if raced:
                return raced, True
            raise
        await self.refresh_retriever()
        return document, False

    async def refresh_retriever(self) -> None:
        if self.retriever:
            chunks = await self._repo.indexed_chunks()
            await anyio.to_thread.run_sync(self.retriever.refresh, chunks)
