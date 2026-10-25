import httpx
import pytest
from fastapi import FastAPI

from app.adapters.generator_cloud import OpenAIGenerator
from app.adapters.generator_extractive import ExtractiveGenerator
from app.core.models import AskResponse
from tests.api.test_ask import load_corpus

FRONT = "What is the minimum thickness of the front brake disc?"


@pytest.fixture
def extractive(app: FastAPI) -> None:
    container = app.state.container
    container.qa.generator = ExtractiveGenerator(container.ingestion.gate)


async def ask(client: httpx.AsyncClient, question: str, history: list[dict[str, str]] | None = None
              ) -> AskResponse:
    body: dict[str, object] = {"question": question}
    if history is not None:
        body["history"] = history
    resp = await client.post("/ask", json=body)
    assert resp.status_code == 200, resp.text
    return AskResponse.model_validate(resp.json())


@pytest.mark.usefixtures("extractive")
async def test_fr_070_follow_up_uses_the_previous_question(client: httpx.AsyncClient) -> None:
    await load_corpus(client)
    first_q = "What is the recommended tyre pressure for a solo rider?"
    first = await ask(client, first_q)
    history = [{"role": "user", "content": first_q},
               {"role": "assistant", "content": first.answer}]
    follow = await ask(client, "and for the rear?", history)
    assert follow.standalone_question == f"{first_q} and for the rear?"
    assert follow.grounded and "33 psi" in follow.answer
    assert follow.citations[0].filename == "manual.md"


@pytest.mark.usefixtures("extractive")
async def test_fr_070_local_rule_keeps_the_previous_subject(client: httpx.AsyncClient) -> None:
    # Without an LLM, "and the rear one?" is joined to the previous question: retrieval finds
    # the right document, but the extractive quote may still favour the earlier row (front).
    await load_corpus(client)
    history = [{"role": "user", "content": FRONT}]
    follow = await ask(client, "and the rear one?", history)
    assert follow.standalone_question == f"{FRONT} and the rear one?"
    assert follow.citations[0].filename == "brake.pdf"


async def test_fr_071_small_talk_over_the_api(client: httpx.AsyncClient) -> None:
    reply = await ask(client, "hi")  # 2 characters is now allowed
    assert reply.small_talk and reply.generator_used == "none" and reply.citations == []


async def test_fr_073_too_much_history_is_rejected(client: httpx.AsyncClient) -> None:
    history = [{"role": "user", "content": "q"}] * 7
    resp = await client.post("/ask", json={"question": "and?", "history": history})
    assert resp.status_code == 422


async def test_fr_070_llm_generator_is_also_the_rewriter(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    from app.api.main import create_app
    from app.settings import Settings

    settings = Settings(data_dir=Path(str(tmp_path)) / "data", retriever="keyword",
                        generator="openai", openai_api_key="sk-test",
                        _env_file=None)  # type: ignore[call-arg]
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        qa = application.state.container.qa
        assert isinstance(qa.rewriter, OpenAIGenerator) and qa.rewriter is qa.generator
        notices = application.state.container.notices
        assert any("conversation" in n for n in notices)
