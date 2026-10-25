"""Dependency wiring: every adapter is built once, at startup, from settings (III.5)."""

import logging
from dataclasses import dataclass, field

import anthropic
import anyio
import httpx
import openai
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.db import SqliteDocumentRepository, create_engine_for
from app.adapters.embedder_fastembed import FastEmbedEmbedder
from app.adapters.extractors import ImageExtractor, OcrEngine, PdfExtractor, TextFileExtractor
from app.adapters.file_store import LocalFileStore
from app.adapters.generator_cloud import AnthropicGenerator, OpenAIGenerator
from app.adapters.generator_extractive import ExtractiveGenerator
from app.adapters.generator_ollama import OllamaGenerator
from app.adapters.retriever_bm25 import Bm25Retriever
from app.adapters.retriever_vector import VectorRetriever
from app.core.answerability import AnswerabilityGate
from app.core.ports import Embedder, Generator, Retriever
from app.core.services import IngestionService, QAService
from app.settings import Settings


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    repository: SqliteDocumentRepository
    file_store: LocalFileStore
    ingestion: IngestionService
    qa: QAService
    retriever: Retriever
    fallbacks: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    llm: OllamaGenerator | OpenAIGenerator | AnthropicGenerator | None = None

    async def aclose(self) -> None:
        if self.llm:
            await self.llm.aclose()
        await self.engine.dispose()


logger = logging.getLogger("docbot.startup")


async def _build_retrieval(settings: Settings) -> tuple[Retriever, Embedder | None, list[str]]:
    """FR-011 and the edge case in spec §3: no embedding model means keyword retrieval."""
    if settings.retriever == "vector":
        try:
            embedder: Embedder = await anyio.to_thread.run_sync(
                FastEmbedEmbedder, settings.embed_model, settings.models_dir
            )
        except Exception as exc:
            reason = f"Embedding model '{settings.embed_model}' could not be loaded ({exc}); "
            reason += "using the keyword retriever instead."
            logger.warning(reason)
            return Bm25Retriever(settings.min_score_keyword), None, [reason]
        return VectorRetriever(embedder, settings.min_score_vector), embedder, []
    return Bm25Retriever(settings.min_score_keyword), None, []


LLM_RETRIES = 2  # FR-017


def _build_llm(
    settings: Settings, fallback: Generator
) -> tuple[OllamaGenerator | OpenAIGenerator | AnthropicGenerator | None, list[str]]:
    """The configured LLM generator (None for extractive) and any notice to show (FR-054)."""
    timeout = settings.llm_timeout_s
    if settings.generator == "ollama":
        client = httpx.AsyncClient(base_url=settings.ollama_url, timeout=timeout)
        return OllamaGenerator(client, settings.ollama_model, settings.ollama_url, fallback), []
    if settings.generator == "openai" and settings.openai_api_key:
        openai_client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=timeout,
            max_retries=LLM_RETRIES,
        )
        notice = _cloud_notice("OpenAI", settings.openai_model)
        return OpenAIGenerator(openai_client, settings.openai_model, fallback), [notice]
    if settings.generator == "anthropic" and settings.anthropic_api_key:
        anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=timeout,
            max_retries=LLM_RETRIES,
        )
        notice = _cloud_notice("Anthropic", settings.anthropic_model)
        return AnthropicGenerator(anthropic_client, settings.anthropic_model, fallback), [notice]
    return None, []


def _cloud_notice(provider: str, model: str) -> str:
    return (
        f"Cloud generator active: each question and its retrieved passages are sent to "
        f"{provider} ({model}). Set DOCBOT_GENERATOR=extractive to keep everything local."
    )


async def build_container(settings: Settings) -> Container:
    engine = await create_engine_for(settings.db_path)
    repository = SqliteDocumentRepository(engine)
    file_store = LocalFileStore(settings.files_dir)
    ocr = OcrEngine()
    ingestion = IngestionService(
        repository=repository,
        file_store=file_store,
        extractors={
            "pdf": PdfExtractor(ocr),
            "image": ImageExtractor(ocr),
            "text": TextFileExtractor(),
        },
        embedder=None,
        retriever=None,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        max_upload_bytes=settings.max_upload_bytes,
        max_pdf_bytes=settings.max_pdf_bytes,
    )
    retriever, embedder, fallbacks = await _build_retrieval(settings)
    gate = AnswerabilityGate()
    ingestion.embedder = embedder
    ingestion.retriever = retriever
    ingestion.gate = gate
    await ingestion.reembed_stale()
    await ingestion.refresh_retriever()

    extractive = ExtractiveGenerator(gate)
    llm, notices = _build_llm(settings, extractive)
    generator: Generator = llm or extractive
    qa = QAService(repository, retriever, generator, gate, settings.min_coverage, extractive)
    return Container(
        settings=settings,
        engine=engine,
        repository=repository,
        file_store=file_store,
        ingestion=ingestion,
        qa=qa,
        retriever=retriever,
        fallbacks=fallbacks,
        notices=notices,
        llm=llm,
    )


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container
