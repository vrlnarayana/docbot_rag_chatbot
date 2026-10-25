from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.adapters.db import SqliteDocumentRepository, create_engine_for
from app.adapters.file_store import LocalFileStore
from app.core.errors import FileTooLarge, NoTextExtracted, UnsupportedFileType
from app.core.models import Chunk, Document, IndexedChunk, Page
from app.core.services import IngestionService

LONG = "Rear sprocket changes from 42T to 43T on the Velo 125. " * 3


class FakeExtractor:
    def __init__(self, pages: list[Page]) -> None:
        self.pages = pages
        self.calls = 0

    def extract(self, data: bytes, extension: str) -> list[Page]:
        self.calls += 1
        return self.pages


class FakeEmbedder:
    model_name = "fake-embed"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 1.0] for t in texts]


class SpyRetriever:
    name = "spy"
    min_score = 0.0

    def __init__(self) -> None:
        self.seen: list[IndexedChunk] = []

    def refresh(self, chunks: list[IndexedChunk]) -> None:
        self.seen = chunks

    def search(self, question: str, k: int) -> list[object]:
        return []


class FailingRepo(SqliteDocumentRepository):
    async def add(
        self, document: Document, chunk_list: list[Chunk],
        embeddings: list[list[float]] | None, embed_model: str | None,
    ) -> None:
        raise RuntimeError("disk full")


@pytest.fixture
async def repo(tmp_path: Path) -> AsyncIterator[SqliteDocumentRepository]:
    engine = await create_engine_for(tmp_path / "t.db")
    yield SqliteDocumentRepository(engine)
    await engine.dispose()


def make_service(
    repo: SqliteDocumentRepository, tmp_path: Path, extractor: FakeExtractor,
    embedder: FakeEmbedder | None = None, retriever: SpyRetriever | None = None,
) -> IngestionService:
    return IngestionService(
        repository=repo,
        file_store=LocalFileStore(tmp_path / "files"),
        extractors={"pdf": extractor, "image": extractor, "text": extractor},
        embedder=embedder,
        retriever=retriever,
        chunk_size=800,
        chunk_overlap=100,
        max_upload_bytes=1000,
    )


def stored_files(tmp_path: Path) -> list[Path]:
    folder = tmp_path / "files"
    return list(folder.iterdir()) if folder.exists() else []


async def test_fr_001_ingest_indexes_document_and_chunks(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    pages = [Page(number=1, text=LONG, source="text"), Page(number=2, text=LONG, source="ocr")]
    retriever = SpyRetriever()
    svc = make_service(repo, tmp_path, FakeExtractor(pages), retriever=retriever)
    doc, duplicate = await svc.ingest("../ECN 0457.pdf", b"%PDF bytes")
    assert duplicate is False
    assert doc.status == "indexed"
    assert (doc.doc_type, doc.page_count, doc.ocr_page_count, doc.chunk_count) == ("pdf", 2, 1, 2)
    assert doc.filename == "../ECN 0457.pdf"  # display only
    assert ".." not in doc.stored_name and "/" not in doc.stored_name
    assert [c.page for c in await repo.chunks(doc.id)] == [1, 2]
    assert len(stored_files(tmp_path)) == 1
    assert {ic.chunk.document_id for ic in retriever.seen} == {doc.id}


async def test_fr_002_unsupported_type_stores_nothing(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    svc = make_service(repo, tmp_path, FakeExtractor([]))
    with pytest.raises(UnsupportedFileType):
        await svc.ingest("spec.docx", b"PK..")
    assert await repo.counts() == (0, 0)


async def test_fr_003_too_large_is_rejected(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    svc = make_service(repo, tmp_path, FakeExtractor([]))
    with pytest.raises(FileTooLarge):
        await svc.ingest("big.txt", b"x" * 1001)
    assert stored_files(tmp_path) == []


async def test_fr_008_duplicate_returns_existing_without_reindexing(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    extractor = FakeExtractor([Page(number=1, text=LONG, source="text")])
    svc = make_service(repo, tmp_path, extractor)
    first, _ = await svc.ingest("a.txt", b"same bytes")
    again, duplicate = await svc.ingest("renamed.txt", b"same bytes")
    assert duplicate is True
    assert again.id == first.id
    assert extractor.calls == 1
    assert await repo.counts() == (1, 1)
    assert len(stored_files(tmp_path)) == 1


async def test_fr_009_no_text_stores_nothing(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    svc = make_service(repo, tmp_path, FakeExtractor([Page(number=1, text="  \n", source="ocr")]))
    with pytest.raises(NoTextExtracted):
        await svc.ingest("blank.png", b"img")
    assert await repo.counts() == (0, 0)
    assert stored_files(tmp_path) == []


async def test_fr_009_failed_insert_removes_saved_file(tmp_path: Path) -> None:
    engine = await create_engine_for(tmp_path / "t.db")
    svc = make_service(
        FailingRepo(engine), tmp_path, FakeExtractor([Page(number=1, text=LONG, source="text")])
    )
    with pytest.raises(RuntimeError):
        await svc.ingest("a.txt", b"bytes")
    assert stored_files(tmp_path) == []
    await engine.dispose()


async def test_embeddings_stored_when_embedder_configured(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    svc = make_service(
        repo, tmp_path, FakeExtractor([Page(number=1, text=LONG, source="text")]), FakeEmbedder()
    )
    await svc.ingest("a.md", b"bytes")
    [indexed] = await repo.indexed_chunks()
    assert indexed.embed_model == "fake-embed"
    assert indexed.embedding == [float(len(indexed.chunk.text)), 1.0]
