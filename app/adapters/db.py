"""SQLite storage for documents, chunks and embeddings (plan §5)."""

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import (
    BLOB,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    event,
    func,
    select,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.models import Chunk, Document, IndexedChunk

metadata = MetaData()

documents = Table(
    "documents",
    metadata,
    Column("id", String, primary_key=True),
    Column("filename", Text, nullable=False),
    Column("stored_name", String, unique=True, nullable=False),
    Column("doc_type", String, nullable=False),
    Column("mime_type", String, nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("sha256", String, unique=True, nullable=False),
    Column("page_count", Integer, nullable=False),
    Column("ocr_page_count", Integer, nullable=False),
    Column("chunk_count", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", String, nullable=False),
)

chunks = Table(
    "chunks",
    metadata,
    Column("id", String, primary_key=True),
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
    Column("page", Integer, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("source", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("embedding", BLOB, nullable=True),
    Column("embed_model", String, nullable=True),
    Index("ix_chunks_document_id", "document_id"),
)


async def create_engine_for(db_path: Path) -> AsyncEngine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys_on(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    return engine


def _to_blob(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _from_blob(blob: bytes | None) -> list[float] | None:
    if blob is None:
        return None
    return [float(x) for x in np.frombuffer(blob, dtype=np.float32)]


def _document(row: Row[Any]) -> Document:
    data = dict(row._mapping)
    data["created_at"] = datetime.fromisoformat(data["created_at"])
    return Document(**data)


def _chunk(row: Row[Any]) -> Chunk:
    return Chunk(
        id=row.id,
        document_id=row.document_id,
        page=row.page,
        ordinal=row.ordinal,
        source=row.source,
        text=row.text,
    )


class SqliteDocumentRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(
        self,
        document: Document,
        chunk_list: list[Chunk],
        embeddings: list[list[float]] | None,
        embed_model: str | None,
    ) -> None:
        doc_row = document.model_dump()
        doc_row["created_at"] = document.created_at.isoformat()
        chunk_rows = [
            {
                **c.model_dump(),
                "embedding": _to_blob(embeddings[i]) if embeddings else None,
                "embed_model": embed_model if embeddings else None,
            }
            for i, c in enumerate(chunk_list)
        ]
        async with self._engine.begin() as conn:
            await conn.execute(documents.insert().values(**doc_row))
            if chunk_rows:
                await conn.execute(chunks.insert(), chunk_rows)

    async def get(self, document_id: str) -> Document | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(select(documents).where(documents.c.id == document_id))
            ).first()
        return _document(row) if row else None

    async def get_by_sha256(self, sha256: str) -> Document | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(select(documents).where(documents.c.sha256 == sha256))
            ).first()
        return _document(row) if row else None

    async def list_all(self) -> list[Document]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(documents).order_by(documents.c.created_at))).all()
        return [_document(r) for r in rows]

    async def chunks(self, document_id: str) -> list[Chunk]:
        query = (
            select(chunks)
            .where(chunks.c.document_id == document_id)
            .order_by(chunks.c.page, chunks.c.ordinal)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [_chunk(r) for r in rows]

    async def delete(self, document_id: str) -> Document | None:
        async with self._engine.begin() as conn:
            row = (
                await conn.execute(select(documents).where(documents.c.id == document_id))
            ).first()
            if row is None:
                return None
            await conn.execute(delete(documents).where(documents.c.id == document_id))
        return _document(row)

    async def counts(self) -> tuple[int, int]:
        async with self._engine.connect() as conn:
            n_docs = (await conn.execute(select(func.count()).select_from(documents))).scalar_one()
            n_chunks = (await conn.execute(select(func.count()).select_from(chunks))).scalar_one()
        return int(n_docs), int(n_chunks)

    async def indexed_chunks(self) -> list[IndexedChunk]:
        query = (
            select(chunks, documents.c.filename)
            .join(documents, chunks.c.document_id == documents.c.id)
            .order_by(documents.c.created_at, chunks.c.page, chunks.c.ordinal)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [
            IndexedChunk(
                chunk=_chunk(r),
                filename=r.filename,
                embedding=_from_blob(r.embedding),
                embed_model=r.embed_model,
            )
            for r in rows
        ]

    async def set_embeddings(self, embeddings: dict[str, list[float]], embed_model: str) -> None:
        async with self._engine.begin() as conn:
            for chunk_id, vector in embeddings.items():
                await conn.execute(
                    update(chunks)
                    .where(chunks.c.id == chunk_id)
                    .values(embedding=_to_blob(vector), embed_model=embed_model)
                )
