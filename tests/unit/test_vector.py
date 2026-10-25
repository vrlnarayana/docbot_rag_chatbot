from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.adapters.db import SqliteDocumentRepository, create_engine_for
from app.adapters.file_store import LocalFileStore
from app.adapters.retriever_vector import VectorRetriever
from app.core.models import Chunk, IndexedChunk, Page
from app.core.services import IngestionService
from tests.fakes import BagOfWordsEmbedder


def ic(i: int, text: str, model: str | None = "fake-bow") -> IndexedChunk:
    emb = BagOfWordsEmbedder().embed([text])[0] if model == "fake-bow" else [1.0] * 10
    return IndexedChunk(
        chunk=Chunk(id=f"c{i}", document_id="d", page=1, ordinal=i, source="text", text=text),
        filename="f.pdf",
        embedding=emb if model else None,
        embed_model=model,
    )


def test_fr_011_vector_retriever_ranks_by_cosine() -> None:
    r = VectorRetriever(BagOfWordsEmbedder(), min_score=0.5)
    r.refresh([ic(0, "engine oil capacity"), ic(1, "front brake disc thickness 3.5 mm"),
               ic(2, "rear tyre pressure 33 psi")])
    hits = r.search("minimum thickness of the brake disc", 2)
    assert [h.chunk.id for h in hits][0] == "c1"
    assert len(hits) == 2
    assert 0.9 < hits[0].score <= 1.0001
    assert r.name == "vector" and r.min_score == 0.5


def test_vector_retriever_ignores_chunks_from_other_models() -> None:
    r = VectorRetriever(BagOfWordsEmbedder(), min_score=0.5)
    r.refresh([ic(0, "brake disc", model="old-model"), ic(1, "brake disc", model=None),
               ic(2, "tyre pressure")])
    assert [h.chunk.id for h in r.search("brake disc", 4)] == ["c2"]


def test_vector_retriever_empty_index() -> None:
    assert VectorRetriever(BagOfWordsEmbedder(), min_score=0.5).search("brake", 4) == []


@pytest.fixture
async def repo(tmp_path: Path) -> AsyncIterator[SqliteDocumentRepository]:
    engine = await create_engine_for(tmp_path / "t.db")
    yield SqliteDocumentRepository(engine)
    await engine.dispose()


class OneTextExtractor:
    def extract(self, data: bytes, extension: str) -> list[Page]:
        return [Page(number=1, text=data.decode() * 3, source="text")]


async def test_reembed_stale_chunks_after_model_change(
    repo: SqliteDocumentRepository, tmp_path: Path
) -> None:
    def service(embedder: BagOfWordsEmbedder | None) -> IngestionService:
        return IngestionService(
            repository=repo, file_store=LocalFileStore(tmp_path / "files"),
            extractors={"text": OneTextExtractor(), "pdf": OneTextExtractor(),
                        "image": OneTextExtractor()},
            embedder=embedder, retriever=None, chunk_size=800, chunk_overlap=100,
            max_upload_bytes=10_000,
        )

    await service(None).ingest("a.txt", b"Brake disc thickness 3.5 mm. ")
    [before] = await repo.indexed_chunks()
    assert before.embedding is None

    embedder = BagOfWordsEmbedder()
    assert await service(embedder).reembed_stale() == 1
    [after] = await repo.indexed_chunks()
    assert after.embed_model == "fake-bow" and after.embedding is not None
    assert await service(embedder).reembed_stale() == 0
