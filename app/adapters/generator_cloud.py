"""Optional cloud generators: OpenAI and Anthropic Claude (FR-019, constitution 1.1.0).

Both use the provider's official SDK, built once at startup with the configured timeout and the
SDK's own retries (2, exponential backoff with jitter, transient errors only), and both ask for
structured output in the strict `LlmAnswer` schema. Invalid output twice, an API error or a
refusal falls back to the extractive generator, as for Ollama (FR-015…FR-017).
"""

from typing import Any

import anthropic
import openai
from pydantic import ValidationError

from app.adapters.generator_ollama import SYSTEM_PROMPT, VALIDATION_ATTEMPTS, build_prompt
from app.core.models import GeneratedAnswer, LlmAnswer, RetrievedChunk
from app.core.ports import Generator

SCHEMA = LlmAnswer.model_json_schema()


class _Declined(Exception):
    """The provider refused to answer (a policy decline, not an error)."""


class _CloudGenerator:
    name = "cloud"
    provider = "Cloud provider"

    def __init__(self, fallback: Generator) -> None:
        self._fallback = fallback

    async def _complete(self, question: str, chunks: list[RetrievedChunk]) -> str:
        raise NotImplementedError

    def _describe(self, exc: Exception) -> str | None:
        """An actionable reason for a provider error, or None if `exc` is not one."""
        raise NotImplementedError

    async def _fall_back(
        self, question: str, chunks: list[RetrievedChunk], reason: str
    ) -> GeneratedAnswer:
        answer = await self._fallback.generate(question, chunks)
        return answer.model_copy(update={"fallback_reason": reason})

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        for _ in range(VALIDATION_ATTEMPTS):
            try:
                content = await self._complete(question, chunks)
            except _Declined:
                return await self._fall_back(
                    question, chunks, f"{self.provider} declined to answer."
                )
            except Exception as exc:
                reason = self._describe(exc)
                if reason is None:
                    raise
                return await self._fall_back(question, chunks, reason)
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
            question,
            chunks,
            f"{self.provider} returned invalid output {VALIDATION_ATTEMPTS} times.",
        )


class OpenAIGenerator(_CloudGenerator):
    name = "openai"
    provider = "OpenAI"

    def __init__(self, client: openai.AsyncOpenAI, model: str, fallback: Generator) -> None:
        super().__init__(fallback)
        self._client = client
        self._model = model

    async def _complete(self, question: str, chunks: list[RetrievedChunk]) -> str:
        response: Any = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(question, chunks)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "llm_answer", "strict": True, "schema": SCHEMA},
            },
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise _Declined()
        return str(message.content or "")

    def _describe(self, exc: Exception) -> str | None:
        if isinstance(exc, openai.APIConnectionError):  # includes timeouts
            return (
                "OpenAI not reachable — check the internet connection or set "
                "DOCBOT_GENERATOR=extractive."
            )
        if isinstance(exc, openai.AuthenticationError):
            return "OpenAI rejected the API key — check DOCBOT_OPENAI_API_KEY."
        if isinstance(exc, openai.NotFoundError):
            return f"OpenAI model '{self._model}' not found — check DOCBOT_OPENAI_MODEL."
        if isinstance(exc, openai.APIStatusError):
            return f"OpenAI returned HTTP {exc.status_code}."
        return None

    async def aclose(self) -> None:
        await self._client.close()


class AnthropicGenerator(_CloudGenerator):
    name = "anthropic"
    provider = "Claude"

    def __init__(self, client: anthropic.AsyncAnthropic, model: str, fallback: Generator) -> None:
        super().__init__(fallback)
        self._client = client
        self._model = model

    async def _complete(self, question: str, chunks: list[RetrievedChunk]) -> str:
        response: Any = await self._client.beta.messages.create(
            model=self._model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(question, chunks)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            # A policy decline is re-run server-side on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise _Declined()
        return next((str(b.text) for b in response.content if b.type == "text"), "")

    def _describe(self, exc: Exception) -> str | None:
        if isinstance(exc, anthropic.APIConnectionError):  # includes timeouts
            return (
                "Claude API not reachable — check the internet connection or set "
                "DOCBOT_GENERATOR=extractive."
            )
        if isinstance(exc, anthropic.AuthenticationError):
            return "Anthropic rejected the API key — check DOCBOT_ANTHROPIC_API_KEY."
        if isinstance(exc, anthropic.NotFoundError):
            return f"Claude model '{self._model}' not found — check DOCBOT_ANTHROPIC_MODEL."
        if isinstance(exc, anthropic.APIStatusError):
            return f"Claude API returned HTTP {exc.status_code}."
        return None

    async def aclose(self) -> None:
        await self._client.close()
