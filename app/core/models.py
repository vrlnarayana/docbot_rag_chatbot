"""Domain models and API contract models (plan §5, §6).

Models that carry data from a request, a file or an LLM are strict and forbid extra fields
(Constitution II, III.2).
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field

DocType = Literal["pdf", "image", "text"]
Source = Literal["text", "ocr"]


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Domain -------------------------------------------------------------------------------


class Page(_Strict):
    number: int = Field(ge=1)
    text: str
    source: Source


class Document(_Strict):
    id: str
    filename: str
    stored_name: str
    doc_type: DocType
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: int
    ocr_page_count: int
    chunk_count: int
    status: Literal["indexed"]
    created_at: datetime


class Chunk(_Strict):
    id: str
    document_id: str
    page: int
    ordinal: int
    source: Source
    text: str


class IndexedChunk(_Strict):
    """A chunk as the retrievers see it: with its file name and optional embedding."""

    chunk: Chunk
    filename: str
    embedding: list[float] | None = None
    embed_model: str | None = None


class RetrievedChunk(_Strict):
    chunk: Chunk
    filename: str
    score: float


class GeneratedAnswer(_Strict):
    """Generator output. `cited` holds 1-based positions in the list of supplied chunks."""

    text: str
    cited: list[int]
    grounded: bool
    generator_used: str
    fallback_reason: str | None = None


class GoldenCase(_Strict):
    question: str
    expected_file: str | None = None
    expected_page: int | None = None
    expected_keywords: list[str] = Field(default_factory=list)
    expect_refusal: bool = False


# --- API contract -------------------------------------------------------------------------


class ErrorResponse(_Out):
    code: str
    message: str


class HealthResponse(_Out):
    status: Literal["ok"] = "ok"


class StatusResponse(_Out):
    retriever: str
    generator: str
    embed_model: str | None
    documents: int
    chunks: int
    fallbacks: list[str]


class DocumentOut(_Out):
    id: str
    filename: str
    doc_type: DocType
    size_bytes: int
    page_count: int
    ocr_page_count: int
    chunk_count: int
    status: str
    created_at: datetime

    @classmethod
    def from_document(cls, doc: Document) -> Self:
        return cls(
            id=doc.id,
            filename=doc.filename,
            doc_type=doc.doc_type,
            size_bytes=doc.size_bytes,
            page_count=doc.page_count,
            ocr_page_count=doc.ocr_page_count,
            chunk_count=doc.chunk_count,
            status=doc.status,
            created_at=doc.created_at,
        )


class UploadResponse(_Out):
    document: DocumentOut
    duplicate: bool


class ChunkOut(_Out):
    id: str
    page: int
    ordinal: int
    source: Source
    text: str

    @classmethod
    def from_chunk(cls, chunk: Chunk) -> Self:
        return cls(
            id=chunk.id,
            page=chunk.page,
            ordinal=chunk.ordinal,
            source=chunk.source,
            text=chunk.text,
        )


class DeleteResponse(_Out):
    deleted_id: str


class AskRequest(_Strict):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class CitationOut(_Out):
    n: int
    chunk_id: str
    document_id: str
    filename: str
    page: int
    score: float
    passage: str


class AskResponse(_Out):
    answer: str
    grounded: bool
    citations: list[CitationOut]
    retriever: str
    generator_used: str
    fallback_reason: str | None = None
    latency_ms: float


class SamplesResponse(_Out):
    files: list[str]


class FailedFile(_Out):
    filename: str
    reason: str


class LoadSamplesResponse(_Out):
    indexed: int
    duplicates: int
    failed: list[FailedFile]


class EvalRequest(_Strict):
    top_k: int = Field(default=4, ge=1, le=10)


class EvalCaseResult(_Out):
    question: str
    expected_file: str | None
    expected_page: int | None
    retrieved_files: list[str]
    hit: bool
    fact_found: bool
    expect_refusal: bool
    refused: bool
    refusal_correct: bool


class EvalSummary(_Out):
    cases: int
    hit_rate_at_k: float
    answer_accuracy: float
    refusal_accuracy: float
    retriever: str
    generator: str
    top_k: int


class EvalRunResponse(_Out):
    summary: EvalSummary
    results: list[EvalCaseResult]
