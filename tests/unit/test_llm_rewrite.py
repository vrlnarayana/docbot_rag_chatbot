"""FR-070 / FR-072: LLM generators rewrite follow-ups and answer conversationally."""

import json

import anthropic
import httpx
import openai
from tenacity import wait_none

from app.adapters.generator_ollama import SYSTEM_PROMPT, OllamaGenerator
from app.core.models import ChatTurn
from tests.unit.test_cloud_generators import (
    CLAUDE_REQ,
    OPENAI_REQ,
    Extractive,
    Scripted,
    claude_gen,
    claude_reply,
    openai_gen,
    openai_reply,
)

HISTORY = [
    ChatTurn(role="user", content="What is the minimum thickness of the front brake disc?"),
    ChatTurn(role="assistant", content="The front disc minimum thickness is 3.5 mm [1]."),
]
REAR = "What is the minimum thickness of the rear brake disc?"


def test_fr_072_system_prompt_is_conversational_and_grounded() -> None:
    prompt = SYSTEM_PROMPT.lower()
    assert "conversational" in prompt and "only from the numbered passages" in prompt
    assert "[n]" in prompt and "grounded to false" in prompt


async def test_fr_070_openai_rewrites_with_strict_schema() -> None:
    script = Scripted(openai_reply(json.dumps({"question": REAR})))
    result = await openai_gen(script).rewrite("and the rear one?", HISTORY)
    assert result == REAR
    call = script.calls[0]
    fmt = call["response_format"]["json_schema"]
    assert fmt["strict"] is True and fmt["schema"]["required"] == ["question"]
    prompt = call["messages"][-1]["content"]
    assert "front brake disc" in prompt and "and the rear one?" in prompt


async def test_fr_070_openai_rewrite_failures_return_none() -> None:
    assert await openai_gen(Scripted(openai_reply("not json"))).rewrite("and?", HISTORY) is None
    assert await openai_gen(Scripted(openai_reply('{"question": ""}'))).rewrite(
        "and?", HISTORY) is None
    error = openai.APIConnectionError(request=OPENAI_REQ)
    assert await openai_gen(Scripted(error)).rewrite("and?", HISTORY) is None


async def test_fr_070_claude_rewrites_and_handles_refusal() -> None:
    script = Scripted(claude_reply(json.dumps({"question": REAR})))
    assert await claude_gen(script).rewrite("and the rear one?", HISTORY) == REAR
    assert script.calls[0]["output_config"]["format"]["schema"]["required"] == ["question"]
    refused = Scripted(claude_reply("", stop_reason="refusal"))
    assert await claude_gen(refused).rewrite("and the rear one?", HISTORY) is None
    error = anthropic.APIConnectionError(request=CLAUDE_REQ)
    assert await claude_gen(Scripted(error)).rewrite("and the rear one?", HISTORY) is None


def ollama(responses: list[httpx.Response]) -> tuple[OllamaGenerator, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[min(len(seen), len(responses)) - 1]

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://o")
    return OllamaGenerator(client, "llama3.2:3b", "http://o", Extractive(), wait=wait_none()), seen


async def test_fr_070_ollama_rewrites_and_returns_none_when_down() -> None:
    reply = {"message": {"content": json.dumps({"question": REAR})}}
    gen, seen = ollama([httpx.Response(200, json=reply)])
    assert await gen.rewrite("and the rear one?", HISTORY) == REAR
    body = json.loads(seen[0].content)
    assert body["format"]["required"] == ["question"]

    gen, seen = ollama([httpx.Response(503)])
    assert await gen.rewrite("and the rear one?", HISTORY) is None
    assert len(seen) == 3  # transient errors are still retried twice
