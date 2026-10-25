"""Dependency wiring: every adapter is built once, at startup, from settings (III.5)."""

from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.db import SqliteDocumentRepository, create_engine_for
from app.adapters.file_store import LocalFileStore
from app.core.ports import Generator, Retriever
from app.settings import Settings


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    repository: SqliteDocumentRepository
    file_store: LocalFileStore
    retriever: Retriever | None = None
    generator: Generator | None = None
    fallbacks: list[str] = field(default_factory=list)


async def build_container(settings: Settings) -> Container:
    engine = await create_engine_for(settings.db_path)
    return Container(
        settings=settings,
        engine=engine,
        repository=SqliteDocumentRepository(engine),
        file_store=LocalFileStore(settings.files_dir),
    )


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container
