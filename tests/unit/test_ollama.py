import json
from collections.abc import Callable

import httpx
import pytest
from tenacity import wait_none

from app.adapters.generator_ollama import OllamaGenerator
from app.core.models import Chunk, GeneratedAnswer, RetrievedChunk

CHUNKS = [
    RetrievedChunk(
        chunk=Chunk(id="c0", document_id="d", page=2, ordinal=0, source="text",
                    text="Front | 276 mm | 3.5 mm"),
        filename="brake.pdf",
        score=0.8,
    )
]
GOOD = {"answer": "The minimum thickness is 3.5 mm [1].", "citations": [1], "grounded": True}


class Extractive:
    name = "extractive"

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        return GeneratedAnswer(text="Front | 276 mm | 3.5 mm [1]", cited=[1], grounded=True,
                               generator_used="extractive")


def chat_reply(content: object) -> httpx.Response:
    body = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(200, json={"message": {"role": "assistant", "content": body}})


def make(responses: list[Callable[[httpx.Request], httpx.Response]]) -> tuple[
    OllamaGenerator, list[httpx.Request]
]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[min(len(seen), len(responses)) - 1](request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama")
    gen = OllamaGenerator(client=client, model="llama3.2:3b", base_url="http://ollama",
                          fallback=Extractive(), wait=wait_none())
    return gen, seen


async def ask(gen: OllamaGenerator) -> GeneratedAnswer:
    return await gen.generate("What is the minimum front disc thickness?", CHUNKS)


async def test_fr_015_valid_json_is_parsed_into_strict_schema() -> None:
    gen, seen = make([lambda r: chat_reply(GOOD)])
    answer = await ask(gen)
    assert answer.generator_used == "ollama" and answer.fallback_reason is None
    assert answer.cited == [1] and "3.5 mm" in answer.text and answer.grounded
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/api/chat"
    assert body["stream"] is False and body["options"]["temperature"] == 0
    assert body["model"] == "llama3.2:3b"
    assert body["format"]["additionalProperties"] is False
    assert set(body["format"]["required"]) == {"answer", "citations", "grounded"}
    assert "[1]" in body["messages"][-1]["content"]


@pytest.mark.parametrize(
    "bad", ["not json", {"answer": "x", "citations": [1]}, {**GOOD, "extra": 1},
            {**GOOD, "citations": ["1"]}]
)
async def test_fr_016_invalid_output_twice_falls_back(bad: object) -> None:
    gen, seen = make([lambda r: chat_reply(bad)])
    answer = await ask(gen)
    assert len(seen) == 2
    assert answer.generator_used == "extractive"
    assert answer.fallback_reason and "invalid" in answer.fallback_reason


async def test_fr_016_invalid_once_then_valid_uses_llm() -> None:
    gen, seen = make([lambda r: chat_reply("oops"), lambda r: chat_reply(GOOD)])
    answer = await ask(gen)
    assert len(seen) == 2 and answer.generator_used == "ollama"


async def test_fr_017_retries_5xx_then_succeeds() -> None:
    gen, seen = make([lambda r: httpx.Response(503), lambda r: chat_reply(GOOD)])
    answer = await ask(gen)
    assert len(seen) == 2 and answer.generator_used == "ollama"


async def test_fr_017_gives_up_after_two_retries() -> None:
    gen, seen = make([lambda r: httpx.Response(500)])
    answer = await ask(gen)
    assert len(seen) == 3
    assert answer.generator_used == "extractive" and answer.fallback_reason


async def test_fr_017_never_retries_4xx() -> None:
    gen, seen = make([lambda r: httpx.Response(404, json={"error": "model not found"})])
    answer = await ask(gen)
    assert len(seen) == 1 and answer.generator_used == "extractive"


async def test_fr_017_unreachable_ollama_falls_back_with_actionable_reason() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    gen, seen = make([refuse])
    answer = await ask(gen)
    assert len(seen) == 3
    assert answer.generator_used == "extractive"
    reason = answer.fallback_reason or ""
    assert "not reachable at http://ollama" in reason and "ollama serve" in reason


async def test_fr_017_timeout_is_transient() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    gen, seen = make([slow, lambda r: chat_reply(GOOD)])
    assert (await ask(gen)).generator_used == "ollama" and len(seen) == 2
