from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi import FastAPI

import app.api.deps as deps
from app.adapters.embedder_openai import OpenAIEmbedder
from app.adapters.generator_extractive import ExtractiveGenerator
from app.core.models import AskResponse, ErrorResponse, StatusResponse
from app.settings import Settings
from tests.fakes import BagOfWordsEmbedder, FakeOpenAIEmbeddings

REQ = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
AUTH_ERROR = openai.AuthenticationError("bad key", response=httpx.Response(401, request=REQ),
                                        body=None)
DOCS = {
    "manual.md": b"Demo Motors Velo 125 manual. Recommended rear tyre pressure 33 psi.",
    "brake.txt": b"Demo Motors brake standard. Front brake disc minimum thickness 3.5 mm.",
    "oil.txt": b"Demo Motors engine oil SAE 10W-30, capacity 1.0 L.",
}


def settings_for(tmp_path: Path, embedder: str) -> Settings:
    return Settings(data_dir=tmp_path / "data", retriever="vector", embedder=embedder,
                    openai_api_key="sk-test-embed", min_score_vector=0.3,
                    _env_file=None)  # type: ignore[call-arg]


def use_fake_openai(monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAIEmbeddings) -> None:
    monkeypatch.setattr(deps, "OpenAIEmbedder",
                        lambda client, model: OpenAIEmbedder(
                            SimpleNamespace(embeddings=fake, close=lambda: None), model))


async def started(settings: Settings) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    from app.api.main import create_app

    application = create_app(settings)
    async with application.router.lifespan_context(application):
        container = application.state.container
        container.qa.generator = ExtractiveGenerator(container.ingestion.gate)
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield application, client


async def upload_all(client: httpx.AsyncClient) -> None:
    for name, data in DOCS.items():
        assert (await client.post("/documents", files={"file": (name, data)})).status_code == 201


async def test_fr_055_openai_embedder_answers_and_is_announced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeOpenAIEmbeddings()
    use_fake_openai(monkeypatch, fake)
    async for _app, client in started(settings_for(tmp_path, "openai")):
        await upload_all(client)
        assert any("tyre pressure" in text for text in fake.inputs)  # chunks went to "OpenAI"
        status = StatusResponse.model_validate((await client.get("/status")).json())
        assert (status.retriever, status.embed_model) == ("vector", "text-embedding-3-small")
        assert any("OpenAI" in n and "every indexed" in n for n in status.notices)
        reply = AskResponse.model_validate((await client.post(
            "/ask", json={"question": "What is the recommended rear tyre pressure?"})).json())
        assert reply.grounded and reply.citations[0].filename == "manual.md"
        assert "sk-test-embed" not in (await client.get("/status")).text


async def test_fr_055_switching_to_openai_reembeds_existing_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deps, "FastEmbedEmbedder", lambda *a, **k: BagOfWordsEmbedder())
    async for _app, client in started(settings_for(tmp_path, "fastembed")):
        await upload_all(client)
    fake = FakeOpenAIEmbeddings()
    use_fake_openai(monkeypatch, fake)
    async for application, _client in started(settings_for(tmp_path, "openai")):
        indexed = await application.state.container.repository.indexed_chunks()
        assert {c.embed_model for c in indexed} == {"openai:text-embedding-3-small"}
        assert len(fake.inputs) == len(indexed) == 3


async def test_fr_056_startup_failure_falls_back_to_keyword(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deps, "FastEmbedEmbedder", lambda *a, **k: BagOfWordsEmbedder())
    async for _app, client in started(settings_for(tmp_path, "fastembed")):
        await upload_all(client)
    use_fake_openai(monkeypatch, FakeOpenAIEmbeddings(error=AUTH_ERROR))
    async for _app, client in started(settings_for(tmp_path, "openai")):
        status = StatusResponse.model_validate((await client.get("/status")).json())
        assert status.retriever == "keyword"
        assert any("keyword" in f and "DOCBOT_OPENAI_API_KEY" in f for f in status.fallbacks)


async def test_fr_056_failure_while_indexing_or_asking_is_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeOpenAIEmbeddings()
    use_fake_openai(monkeypatch, fake)
    async for _app, client in started(settings_for(tmp_path, "openai")):
        await upload_all(client)
        fake.error = AUTH_ERROR
        resp = await client.post("/documents", files={"file": ("new.txt", b"Demo Motors new doc.")})
        assert resp.status_code == 503
        assert ErrorResponse.model_validate(resp.json()).code == "embedding_unavailable"
        assert (await client.get("/status")).json()["documents"] == 3
        resp = await client.post("/ask", json={"question": "What is the rear tyre pressure?"})
        assert resp.status_code == 503
        assert "DOCBOT_EMBEDDER=fastembed" in ErrorResponse.model_validate(resp.json()).message
