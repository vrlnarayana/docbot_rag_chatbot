from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.adapters.generator_cloud import AnthropicGenerator, OpenAIGenerator
from app.core.models import StatusResponse
from app.settings import Settings

KEYS = {"openai": "sk-test-OPENAI-secret", "anthropic": "sk-ant-test-CLAUDE-secret"}


def cloud_settings(tmp_path: Path, generator: str) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        retriever="keyword",
        generator=generator,
        llm_timeout_s=12,
        _env_file=None,  # type: ignore[call-arg]
        **{f"{generator}_api_key": KEYS[generator]},
    )


async def started(settings: Settings) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    from app.api.main import create_app

    application = create_app(settings)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield application, client


@pytest.mark.parametrize(
    ("generator", "cls", "provider"),
    [("openai", OpenAIGenerator, "OpenAI"), ("anthropic", AnthropicGenerator, "Anthropic")],
)
async def test_fr_054_cloud_generator_is_wired_and_announced(
    tmp_path: Path, generator: str, cls: type, provider: str
) -> None:
    async for application, client in started(cloud_settings(tmp_path, generator)):
        qa_generator = application.state.container.qa.generator
        assert isinstance(qa_generator, cls)
        sdk_client = qa_generator._client
        assert sdk_client.max_retries == 2  # FR-017: two retries on transient errors
        assert sdk_client.timeout == 12
        resp = await client.get("/status")
        status = StatusResponse.model_validate(resp.json())
        assert status.generator == generator
        assert len(status.notices) == 1 and provider in status.notices[0]
        assert "retrieved passages" in status.notices[0]
        assert KEYS[generator] not in resp.text


async def test_fr_054_local_setup_has_no_cloud_notice(client: httpx.AsyncClient) -> None:
    status = StatusResponse.model_validate((await client.get("/status")).json())
    assert status.notices == []
