"""Shared fixtures: temporary data folder, keyword retriever, fake generator (Constitution V.2)."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.core.models import GeneratedAnswer, RetrievedChunk
from app.settings import Settings


class FakeGenerator:
    """Deterministic generator: answers with the first supplied passage and cites it."""

    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        self.calls += 1
        return GeneratedAnswer(
            text=f"{chunks[0].chunk.text} [1]", cited=[1], grounded=True, generator_used=self.name
        )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        sample_dir=tmp_path / "sample_data",
        golden_path=tmp_path / "eval" / "golden.yaml",
        retriever="keyword",
        generator="extractive",
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def fake_generator() -> FakeGenerator:
    return FakeGenerator()


@pytest.fixture
async def app(settings: Settings, fake_generator: FakeGenerator) -> AsyncIterator[FastAPI]:
    from app.api.main import create_app

    application = create_app(settings)
    async with application.router.lifespan_context(application):
        application.state.container.qa.generator = fake_generator
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
