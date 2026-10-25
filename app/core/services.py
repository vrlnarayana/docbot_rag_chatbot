"""Use cases: ingestion, question answering and evaluation (plan §7)."""

import hashlib
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

import anyio

from app.core.answerability import AnswerabilityGate
from app.core.chunking import chunk_pages
from app.core.conversation import local_standalone, small_talk_kind, small_talk_reply
from app.core.errors import (
    DocumentNotFound,
    FileTooLarge,
    NoDocuments,
    NoTextExtracted,
    UnsupportedFileType,
)
from app.core.models import (
    AskResponse,
    ChatTurn,
    Chunk,
    CitationOut,
    DocType,
    Document,
    EvalCaseResult,
    EvalRunResponse,
    EvalSummary,
    GeneratedAnswer,
    GoldenCase,
    RetrievedChunk,
)
from app.core.ports import (
    DocumentRepository,
    Embedder,
    Extractor,
    FileStore,
    Generator,
    QuestionRewriter,
    Retriever,
)

REFUSAL = "I couldn't find this in the uploaded documents."
EMPTY_LIBRARY = (
    "There are no documents yet. Load the sample set (Documents page → "
    '"Generate & load sample documents") or upload your own files.'
)
NO_GENERATOR = "none"
_MARKER = re.compile(r"\s?\[(\d+)\]")

_TYPES: dict[str, tuple[DocType, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".txt": ("text", "text/plain"),
    ".md": ("text", "text/markdown"),
}


class IngestionService:
    def __init__(
        self,
        repository: DocumentRepository,
        file_store: FileStore,
        extractors: dict[DocType, Extractor],
        embedder: Embedder | None,
        retriever: Retriever | None,
        chunk_size: int,
        chunk_overlap: int,
        max_upload_bytes: int,
        max_pdf_bytes: int | None = None,
        gate: AnswerabilityGate | None = None,
    ) -> None:
        self._repo = repository
        self._files = file_store
        self._extractors = extractors
        self.embedder = embedder
        self.retriever = retriever
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._max_bytes = max_upload_bytes
        self._max_pdf_bytes = max_pdf_bytes if max_pdf_bytes is not None else max_upload_bytes
        self.gate = gate

    def check_upload(self, filename: str) -> str:
        """FR-002: return the lower-case extension, or raise if it is not supported."""
        extension = PurePath(filename).suffix.lower()
        if extension not in _TYPES:
            raise UnsupportedFileType(extension)
        return extension

    def size_limit(self, extension: str) -> int:
        """FR-003: PDFs have their own, lower limit; every other type shares the upload limit."""
        return self._max_pdf_bytes if extension == ".pdf" else self._max_bytes

    def too_large(self, extension: str) -> FileTooLarge:
        limit_mb = self.size_limit(extension) // (1024 * 1024)
        if extension == ".pdf":
            return FileTooLarge(limit_mb, what="PDF", setting="DOCBOT_MAX_PDF_MB")
        return FileTooLarge(limit_mb)

    async def ingest(self, filename: str, data: bytes) -> tuple[Document, bool]:
        """Index one file. Returns the document and whether it was already indexed."""
        extension = self.check_upload(filename)
        if len(data) > self.size_limit(extension):
            raise self.too_large(extension)

        sha256 = hashlib.sha256(data).hexdigest()
        existing = await self._repo.get_by_sha256(sha256)
        if existing:
            return existing, True

        doc_type, mime_type = _TYPES[extension]
        extractor = self._extractors[doc_type]
        pages = await anyio.to_thread.run_sync(extractor.extract, data, extension)
        if not any(p.text.strip() for p in pages):
            raise NoTextExtracted()

        document_id = str(uuid.uuid4())
        drafts = chunk_pages(pages, self._chunk_size, self._chunk_overlap)
        chunks = [
            Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                page=d.page,
                ordinal=i,
                source=d.source,
                text=d.text,
            )
            for i, d in enumerate(drafts)
        ]
        embeddings = None
        if self.embedder:
            embeddings = await anyio.to_thread.run_sync(
                self.embedder.embed, [c.text for c in chunks]
            )

        stored_name = await self._files.save(data, extension)
        document = Document(
            id=document_id,
            filename=filename,
            stored_name=stored_name,
            doc_type=doc_type,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=sha256,
            page_count=len(pages),
            ocr_page_count=sum(1 for p in pages if p.source == "ocr"),
            chunk_count=len(chunks),
            status="indexed",
            created_at=datetime.now(UTC),
        )
        try:
            await self._repo.add(
                document, chunks, embeddings, self.embedder.model_name if self.embedder else None
            )
        except Exception:
            await self._files.delete(stored_name)
            raced = await self._repo.get_by_sha256(sha256)  # same bytes uploaded concurrently
            if raced:
                return raced, True
            raise
        await self.refresh_retriever()
        return document, False

    async def delete(self, document_id: str) -> Document:
        """FR-022: remove one document; its chunks and embeddings go in the same transaction."""
        document = await self._repo.delete(document_id)
        if document is None:
            raise DocumentNotFound(document_id)
        await self._files.delete(document.stored_name)
        await self.refresh_retriever()
        return document

    async def reembed_stale(self) -> int:
        """Embed chunks that have no embedding, or one from a different model. Returns the count."""
        if not self.embedder:
            return 0
        model = self.embedder.model_name
        stale = [c for c in await self._repo.indexed_chunks() if c.embed_model != model]
        if stale:
            vectors = await anyio.to_thread.run_sync(
                self.embedder.embed, [c.chunk.text for c in stale]
            )
            await self._repo.set_embeddings(
                {c.chunk.id: v for c, v in zip(stale, vectors, strict=True)}, model
            )
        return len(stale)

    async def refresh_retriever(self) -> None:
        """Rebuild the retriever's index and the answerability statistics from the database."""
        chunks = await self._repo.indexed_chunks()
        if self.retriever:
            await anyio.to_thread.run_sync(self.retriever.refresh, chunks)
        if self.gate:
            await anyio.to_thread.run_sync(self.gate.refresh, [c.chunk.text for c in chunks])


class QAService:
    """FR-010…FR-018: retrieve, gate, generate, validate citations (plan §7.2)."""

    def __init__(
        self,
        repository: DocumentRepository,
        retriever: Retriever,
        generator: Generator,
        gate: AnswerabilityGate,
        min_coverage: float,
        fallback: Generator | None = None,
        rewriter: QuestionRewriter | None = None,
    ) -> None:
        self._repo = repository
        self.retriever = retriever
        self.generator = generator
        self.rewriter = rewriter
        self._gate = gate
        self._min_coverage = min_coverage
        self._fallback = fallback

    async def ask(
        self, question: str, top_k: int, history: list[ChatTurn] | None = None
    ) -> AskResponse:
        start = time.perf_counter()

        def respond(
            text: str,
            citations: list[CitationOut] | None = None,
            generator_used: str = NO_GENERATOR,
            fallback_reason: str | None = None,
            small_talk: bool = False,
        ) -> AskResponse:
            rewritten = standalone if standalone != question else None
            return AskResponse(
                answer=text,
                grounded=bool(citations),
                citations=citations or [],
                retriever=self.retriever.name,
                generator_used=generator_used,
                fallback_reason=fallback_reason,
                latency_ms=round((time.perf_counter() - start) * 1000, 1),
                small_talk=small_talk,
                standalone_question=rewritten,
            )

        standalone = question
        kind = small_talk_kind(question)
        if kind:  # FR-071: no retrieval, no LLM
            return respond(small_talk_reply(kind), small_talk=True)
        if history:  # FR-070: everything below works on the standalone question
            standalone = await self._standalone(question, history)

        _documents, chunk_count = await self._repo.counts()
        if chunk_count == 0:
            return respond(EMPTY_LIBRARY)

        retrieved = await self.retrieve(standalone, top_k)
        if not retrieved or retrieved[0].score < self.retriever.min_score:
            return respond(REFUSAL)
        coverage = self._gate.coverage(standalone, [r.chunk.text for r in retrieved])
        if coverage < self._min_coverage:
            return respond(REFUSAL)

        answer = await self.generator.generate(standalone, retrieved)
        text, citations = _cite(answer, retrieved)
        fallback_reason = answer.fallback_reason
        if not citations and self._fallback and answer.generator_used != self._fallback.name:
            fallback_reason = f"{answer.generator_used} answer had no valid citations"
            answer = await self._fallback.generate(standalone, retrieved)
            text, citations = _cite(answer, retrieved)
        if not citations:
            return respond(REFUSAL, generator_used=answer.generator_used)
        return respond(text, citations, answer.generator_used, fallback_reason)


    async def _standalone(self, question: str, history: list[ChatTurn]) -> str:
        if self.rewriter:
            rewritten = await self.rewriter.rewrite(question, history)
            if rewritten:
                return rewritten
        return local_standalone(question, history) or question

    async def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        return await anyio.to_thread.run_sync(self.retriever.search, question, top_k)


class EvaluationService:
    """FR-040, FR-041: run the golden set through the same QA pipeline users get."""

    def __init__(self, repository: DocumentRepository, qa: QAService) -> None:
        self._repo = repository
        self._qa = qa

    async def run(self, cases: list[GoldenCase], top_k: int) -> EvalRunResponse:
        _documents, chunk_count = await self._repo.counts()
        if chunk_count == 0:
            raise NoDocuments()
        results = [await self._run_case(case, top_k) for case in cases]
        answerable = [r for r in results if not r.expect_refusal]
        refusals = [r for r in results if r.expect_refusal]
        summary = EvalSummary(
            cases=len(results),
            hit_rate_at_k=_percent(sum(r.hit for r in answerable), len(answerable)),
            answer_accuracy=_percent(sum(r.fact_found for r in answerable), len(answerable)),
            refusal_accuracy=_percent(sum(r.refusal_correct for r in refusals), len(refusals)),
            retriever=self._qa.retriever.name,
            generator=self._qa.generator.name,
            top_k=top_k,
        )
        return EvalRunResponse(summary=summary, results=results)

    async def _run_case(self, case: GoldenCase, top_k: int) -> EvalCaseResult:
        retrieved = await self._qa.retrieve(case.question, top_k)
        files = list(dict.fromkeys(r.filename for r in retrieved))
        answer = await self._qa.ask(case.question, top_k)
        refused = not answer.grounded
        text = answer.answer.lower()
        answerable = not case.expect_refusal
        return EvalCaseResult(
            question=case.question,
            expected_file=case.expected_file,
            expected_page=case.expected_page,
            retrieved_files=files,
            hit=answerable and case.expected_file in files,
            fact_found=answerable
            and not refused
            and all(k.lower() in text for k in case.expected_keywords),
            expect_refusal=case.expect_refusal,
            refused=refused,
            refusal_correct=refused == case.expect_refusal,
        )


def _percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _cite(
    answer: GeneratedAnswer, retrieved: list[RetrievedChunk]
) -> tuple[str, list[CitationOut]]:
    """FR-015: keep only citations to supplied chunks; renumber them by first use (FR-014)."""
    if not answer.grounded:
        return answer.text, []
    valid = set(range(1, len(retrieved) + 1))
    in_text = [int(m) for m in _MARKER.findall(answer.text)]
    order: list[int] = []
    for n in in_text + answer.cited:
        if n in valid and n not in order:
            order.append(n)
    new_number = {old: i for i, old in enumerate(order, start=1)}

    def renumber(match: re.Match[str]) -> str:
        old = int(match.group(1))
        return f" [{new_number[old]}]" if old in new_number else ""

    text = _MARKER.sub(renumber, answer.text).strip()
    citations = [
        CitationOut(
            n=new_number[old],
            chunk_id=retrieved[old - 1].chunk.id,
            document_id=retrieved[old - 1].chunk.document_id,
            filename=retrieved[old - 1].filename,
            page=retrieved[old - 1].chunk.page,
            score=retrieved[old - 1].score,
            passage=retrieved[old - 1].chunk.text,
        )
        for old in order
    ]
    return text, citations
