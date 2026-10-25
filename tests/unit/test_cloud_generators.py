"""OpenAI and Anthropic generators, against stand-in SDK clients (no network, no real LLM)."""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest

from app.adapters.generator_cloud import AnthropicGenerator, OpenAIGenerator
from app.core.models import Chunk, GeneratedAnswer, RetrievedChunk

CHUNKS = [
    RetrievedChunk(
        chunk=Chunk(id="c0", document_id="d", page=2, ordinal=0, source="text",
                    text="Front | 276 mm | 3.5 mm"),
        filename="brake.pdf",
        score=0.8,
    )
]
GOOD = json.dumps({"answer": "The minimum is 3.5 mm [1].", "citations": [1], "grounded": True})
Q = "What is the minimum front disc thickness?"


class Extractive:
    name = "extractive"

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        return GeneratedAnswer(text="Front | 276 mm | 3.5 mm [1]", cited=[1], grounded=True,
                               generator_used="extractive")


class Scripted:
    """Returns (or raises) the scripted items in order; records every call's kwargs."""

    def __init__(self, *items: object) -> None:
        self.items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        item = self.items[min(len(self.calls), len(self.items)) - 1]
        if isinstance(item, BaseException):
            raise item
        return item


def openai_reply(content: str | None, refusal: str | None = None) -> object:
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def claude_reply(text: str, stop_reason: str = "end_turn") -> object:
    return SimpleNamespace(stop_reason=stop_reason,
                           content=[SimpleNamespace(type="thinking", thinking=""),
                                    SimpleNamespace(type="text", text=text)])


def openai_gen(script: Scripted) -> OpenAIGenerator:
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=script)))
    return OpenAIGenerator(client, "gpt-5-mini", Extractive())  # type: ignore[arg-type]


def claude_gen(script: Scripted) -> AnthropicGenerator:
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=script)))
    return AnthropicGenerator(client, "claude-opus-5-5", Extractive())  # type: ignore[arg-type]


OPENAI_REQ = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
CLAUDE_REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


# --- OpenAI ---------------------------------------------------------------------------------


async def test_fr_019_openai_answer_uses_strict_structured_output() -> None:
    script = Scripted(openai_reply(GOOD))
    answer = await openai_gen(script).generate(Q, CHUNKS)
    assert answer.generator_used == "openai" and answer.cited == [1] and answer.grounded
    call = script.calls[0]
    assert call["model"] == "gpt-5-mini"
    fmt = call["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False
    assert "[1] (brake.pdf, p. 2)" in call["messages"][-1]["content"]


async def test_fr_016_openai_invalid_output_twice_falls_back() -> None:
    script = Scripted(openai_reply('{"answer": "x"}'))
    answer = await openai_gen(script).generate(Q, CHUNKS)
    assert len(script.calls) == 2
    assert answer.generator_used == "extractive" and "invalid" in (answer.fallback_reason or "")


async def test_fr_016_openai_refusal_falls_back() -> None:
    answer = await openai_gen(Scripted(openai_reply(None, refusal="no"))).generate(Q, CHUNKS)
    assert answer.generator_used == "extractive" and "declined" in (answer.fallback_reason or "")


@pytest.mark.parametrize(
    ("error", "hint"),
    [
        (openai.APIConnectionError(request=OPENAI_REQ), "not reachable"),
        (openai.APITimeoutError(request=OPENAI_REQ), "not reachable"),
        (openai.AuthenticationError("bad key", response=httpx.Response(401, request=OPENAI_REQ),
                                    body=None), "DOCBOT_OPENAI_API_KEY"),
        (openai.NotFoundError("no model", response=httpx.Response(404, request=OPENAI_REQ),
                              body=None), "DOCBOT_OPENAI_MODEL"),
        (openai.InternalServerError("boom", response=httpx.Response(500, request=OPENAI_REQ),
                                    body=None), "HTTP 500"),
    ],
)
async def test_fr_017_openai_errors_fall_back_with_actionable_reason(
    error: Exception, hint: str
) -> None:
    script = Scripted(error)
    answer = await openai_gen(script).generate(Q, CHUNKS)
    assert len(script.calls) == 1  # the SDK already retried transient errors
    assert answer.generator_used == "extractive"
    assert hint in (answer.fallback_reason or "")
    assert "sk-" not in (answer.fallback_reason or "")


# --- Anthropic ------------------------------------------------------------------------------


async def test_fr_019_claude_answer_uses_structured_output_and_fallbacks() -> None:
    script = Scripted(claude_reply(GOOD))
    answer = await claude_gen(script).generate(Q, CHUNKS)
    assert answer.generator_used == "anthropic" and answer.cited == [1]
    call = script.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in call and "thinking" not in call
    assert "[1] (brake.pdf, p. 2)" in call["messages"][-1]["content"]


async def test_fr_016_claude_refusal_falls_back() -> None:
    answer = await claude_gen(Scripted(claude_reply("", stop_reason="refusal"))).generate(
        Q, CHUNKS
    )
    assert answer.generator_used == "extractive" and "declined" in (answer.fallback_reason or "")


async def test_fr_016_claude_invalid_once_then_valid() -> None:
    script = Scripted(claude_reply("not json"), claude_reply(GOOD))
    answer = await claude_gen(script).generate(Q, CHUNKS)
    assert len(script.calls) == 2 and answer.generator_used == "anthropic"


@pytest.mark.parametrize(
    ("error", "hint"),
    [
        (anthropic.APIConnectionError(request=CLAUDE_REQ), "not reachable"),
        (anthropic.AuthenticationError("bad key",
                                       response=httpx2.Response(401, request=CLAUDE_REQ),
                                       body=None), "DOCBOT_ANTHROPIC_API_KEY"),
        (anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=CLAUDE_REQ),
                                  body=None), "HTTP 429"),
    ],
)
async def test_fr_017_claude_errors_fall_back_with_actionable_reason(
    error: Exception, hint: str
) -> None:
    script = Scripted(error)
    answer = await claude_gen(script).generate(Q, CHUNKS)
    assert len(script.calls) == 1
    assert answer.generator_used == "extractive" and hint in (answer.fallback_reason or "")
