"""Dependency wiring: every adapter is built once, at startup, from settings (III.5)."""

from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.db import SqliteDocumentRepository, create_engine_for
from app.adapters.extractors import ImageExtractor, OcrEngine, PdfExtractor, TextFileExtractor
from app.adapters.file_store import LocalFileStore
from app.core.ports import Generator, Retriever
from app.core.services import IngestionService
from app.settings import Settings


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    repository: SqliteDocumentRepository
    file_store: LocalFileStore
    ingestion: IngestionService
    retriever: Retriever | None = None
    generator: Generator | None = None
    fallbacks: list[str] = field(default_factory=list)


async def build_container(settings: Settings) -> Container:
    engine = await create_engine_for(settings.db_path)
    repository = SqliteDocumentRepository(engine)
    file_store = LocalFileStore(settings.files_dir)
    ocr = OcrEngine()
    ingestion = IngestionService(
        repository=repository,
        file_store=file_store,
        extractors={
            "pdf": PdfExtractor(ocr),
            "image": ImageExtractor(ocr),
            "text": TextFileExtractor(),
        },
        embedder=None,
        retriever=None,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        max_upload_bytes=settings.max_upload_bytes,
    )
    return Container(
        settings=settings,
        engine=engine,
        repository=repository,
        file_store=file_store,
        ingestion=ingestion,
    )


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container
