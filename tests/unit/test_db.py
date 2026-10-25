from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.adapters.db import SqliteDocumentRepository, create_engine_for
from app.core.models import Chunk, Document


def doc(doc_id: str = "d1", sha: str = "a" * 64) -> Document:
    return Document(
        id=doc_id, filename="f.pdf", stored_name=f"{doc_id}.pdf", doc_type="pdf",
        mime_type="application/pdf", size_bytes=5, sha256=sha, page_count=2,
        ocr_page_count=1, chunk_count=3, status="indexed",
        created_at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )


def chunks(doc_id: str = "d1") -> list[Chunk]:
    # deliberately out of order
    return [
        Chunk(id=f"{doc_id}c2", document_id=doc_id, page=2, ordinal=2, source="ocr", text="p2"),
        Chunk(id=f"{doc_id}c0", document_id=doc_id, page=1, ordinal=0, source="text", text="p1a"),
        Chunk(id=f"{doc_id}c1", document_id=doc_id, page=1, ordinal=1, source="text", text="p1b"),
    ]


@pytest.fixture
async def repo(tmp_path: Path) -> AsyncIterator[SqliteDocumentRepository]:
    engine = await create_engine_for(tmp_path / "t.db")
    yield SqliteDocumentRepository(engine)
    await engine.dispose()


async def test_fr_020_add_get_and_list(repo: SqliteDocumentRepository) -> None:
    await repo.add(doc(), chunks(), None, None)
    assert await repo.get("d1") == doc()
    assert await repo.list_all() == [doc()]
    assert await repo.get("missing") is None


async def test_fr_008_lookup_by_sha256(repo: SqliteDocumentRepository) -> None:
    await repo.add(doc(), chunks(), None, None)
    found = await repo.get_by_sha256("a" * 64)
    assert found is not None and found.id == "d1"
    assert await repo.get_by_sha256("b" * 64) is None


async def test_fr_021_chunks_in_page_order(repo: SqliteDocumentRepository) -> None:
    await repo.add(doc(), chunks(), None, None)
    got = await repo.chunks("d1")
    assert [c.ordinal for c in got] == [0, 1, 2]
    assert [c.page for c in got] == [1, 1, 2]


async def test_fr_022_delete_removes_document_and_chunks(
    repo: SqliteDocumentRepository,
) -> None:
    await repo.add(doc(), chunks(), [[1.0, 0.0]] * 3, "m")
    await repo.add(doc("d2", "b" * 64), chunks("d2"), None, None)
    deleted = await repo.delete("d1")
    assert deleted is not None and deleted.id == "d1"
    assert await repo.get("d1") is None
    assert await repo.chunks("d1") == []
    assert await repo.counts() == (1, 3)
    assert {ic.chunk.document_id for ic in await repo.indexed_chunks()} == {"d2"}
    assert await repo.delete("d1") is None


async def test_embeddings_round_trip_and_update(repo: SqliteDocumentRepository) -> None:
    await repo.add(doc(), chunks(), [[0.5, 0.25], [1.0, 0.0], [0.0, 1.0]], "m1")
    indexed = {ic.chunk.id: ic for ic in await repo.indexed_chunks()}
    assert indexed["d1c2"].embedding == [0.5, 0.25]
    assert indexed["d1c2"].embed_model == "m1"
    assert indexed["d1c2"].filename == "f.pdf"
    await repo.set_embeddings({"d1c2": [0.75, 0.125]}, "m2")
    indexed = {ic.chunk.id: ic for ic in await repo.indexed_chunks()}
    assert indexed["d1c2"].embedding == [0.75, 0.125]
    assert indexed["d1c2"].embed_model == "m2"


async def test_fr_009_failed_insert_stores_nothing(repo: SqliteDocumentRepository) -> None:
    await repo.add(doc(), chunks(), None, None)
    with pytest.raises(Exception):  # noqa: B017 - duplicate primary key on chunks
        await repo.add(doc("d2", "c" * 64), chunks("d1"), None, None)
    assert await repo.get("d2") is None
    assert await repo.counts() == (1, 3)
