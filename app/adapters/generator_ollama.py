"""Ollama generator: a local LLM over HTTP, behind one resilient client (Constitution III.4).

Transient errors (connection errors, timeouts, 5xx) are retried twice with exponential backoff
and jitter; 4xx is never retried. Output is parsed into the strict `LlmAnswer` schema; if that
fails twice, or Ollama cannot be used, the extractive generator answers instead (FR-015…FR-017).
The same client rewrites follow-up questions (FR-070).
"""

from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base

from app.core.models import ChatTurn, GeneratedAnswer, LlmAnswer, RetrievedChunk, StandaloneQuestion
from app.core.ports import Generator

SYSTEM_PROMPT = (
    "You are DocBot, a friendly assistant for engineering documents. Answer only from the "
    "numbered passages, in one to three natural, conversational sentences. Cite every passage "
    "you use as [n]. If the passages do not contain the answer, set grounded to false."
)
REWRITE_PROMPT = (
    "Rewrite the user's last message as one standalone question that can be understood without "
    "the conversation, keeping every detail it refers to. Do not answer it. If it is already "
    "standalone, return it unchanged."
)
VALIDATION_ATTEMPTS = 2
TRANSIENT_RETRIES = 2


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):  # connection errors and timeouts
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    passages = "\n\n".join(
        f"[{n}] ({c.filename}, p. {c.chunk.page})\n{c.chunk.text}"
        for n, c in enumerate(chunks, start=1)
    )
    return f"Passages:\n\n{passages}\n\nQuestion: {question}"


def build_rewrite_prompt(question: str, history: list[ChatTurn]) -> str:
    turns = "\n".join(f"{t.role.capitalize()}: {t.content}" for t in history)
    return f"Conversation:\n{turns}\n\nLast message: {question}"


def parse_standalone(content: str) -> str | None:
    try:
        return StandaloneQuestion.model_validate_json(content, strict=True).question
    except ValidationError:
        return None


class OllamaGenerator:
    name = "ollama"

    def __init__(
        self,
        client: httpx.AsyncClient,
        model: str,
        base_url: str,
        fallback: Generator,
        wait: wait_base | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._base_url = base_url
        self._fallback = fallback
        self._wait = wait or wait_exponential_jitter(initial=0.5, max=4)

    async def _chat(self, system: str, user: str, schema: dict[str, Any]) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "options": {"temperature": 0},
            "format": schema,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(1 + TRANSIENT_RETRIES),
            wait=self._wait,
            retry=retry_if_exception(_is_transient),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post("/api/chat", json=payload)
                response.raise_for_status()
        content: str = response.json()["message"]["content"]
        return content

    async def _fall_back(
        self, question: str, chunks: list[RetrievedChunk], reason: str
    ) -> GeneratedAnswer:
        answer = await self._fallback.generate(question, chunks)
        return answer.model_copy(update={"fallback_reason": reason})

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        for _ in range(VALIDATION_ATTEMPTS):
            try:
                content = await self._chat(
                    SYSTEM_PROMPT, build_prompt(question, chunks), LlmAnswer.model_json_schema()
                )
            except httpx.TransportError:
                return await self._fall_back(
                    question,
                    chunks,
                    f"Ollama not reachable at {self._base_url} — start it with `ollama serve` "
                    "or set DOCBOT_GENERATOR=extractive.",
                )
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                hint = " Is the model pulled (`ollama pull`)?" if code == 404 else ""
                return await self._fall_back(
                    question, chunks, f"Ollama returned HTTP {code}.{hint}"
                )
            except (KeyError, TypeError, ValueError):
                continue  # malformed envelope: counts as invalid output
            try:
                parsed = LlmAnswer.model_validate_json(content, strict=True)
            except ValidationError:
                continue
            return GeneratedAnswer(
                text=parsed.answer,
                cited=parsed.citations,
                grounded=parsed.grounded,
                generator_used=self.name,
            )
        return await self._fall_back(
            question, chunks, f"Ollama returned invalid output {VALIDATION_ATTEMPTS} times."
        )

    async def rewrite(self, question: str, history: list[ChatTurn]) -> str | None:
        """FR-070: a standalone version of a follow-up, or None (the local rule takes over)."""
        try:
            content = await self._chat(
                REWRITE_PROMPT,
                build_rewrite_prompt(question, history),
                StandaloneQuestion.model_json_schema(),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return None
        return parse_standalone(content)

    async def aclose(self) -> None:
        await self._client.aclose()
