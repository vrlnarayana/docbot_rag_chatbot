from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import app.api.deps as deps
from app.core.models import StatusResponse
from app.settings import Settings
from tests.fakes import BagOfWordsEmbedder


def vector_settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", retriever="vector", _env_file=None)  # type: ignore[call-arg]


async def status_of(application: FastAPI) -> StatusResponse:
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        return StatusResponse.model_validate((await c.get("/status")).json())


@pytest.fixture
def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class Unavailable:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise OSError("could not download BAAI/bge-small-en-v1.5")

    monkeypatch.setattr(deps, "FastEmbedEmbedder", Unavailable)


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "FastEmbedEmbedder", lambda *a, **k: BagOfWordsEmbedder())


async def started(settings: Settings) -> AsyncIterator[FastAPI]:
    from app.api.main import create_app

    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.mark.usefixtures("no_model")
async def test_fr_051_falls_back_to_keyword_when_model_unavailable(tmp_path: Path) -> None:
    async for application in started(vector_settings(tmp_path)):
        status = await status_of(application)
        assert status.retriever == "keyword"
        assert status.embed_model is None
        assert len(status.fallbacks) == 1
        assert "keyword" in status.fallbacks[0] and "could not download" in status.fallbacks[0]


@pytest.mark.usefixtures("fake_model")
async def test_fr_011_vector_retriever_active_when_model_loads(tmp_path: Path) -> None:
    async for application in started(vector_settings(tmp_path)):
        status = await status_of(application)
        assert (status.retriever, status.fallbacks) == ("vector", [])
        assert status.embed_model == "BAAI/bge-small-en-v1.5"
