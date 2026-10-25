from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.models import (
    AskRequest,
    ChunkOut,
    CitationOut,
    Document,
    DocumentOut,
    UploadResponse,
)


def make_document() -> Document:
    return Document(
        id="d1",
        filename="brake.pdf",
        stored_name="0f.pdf",
        doc_type="pdf",
        mime_type="application/pdf",
        size_bytes=10,
        sha256="ab" * 32,
        page_count=3,
        ocr_page_count=0,
        chunk_count=4,
        status="indexed",
        created_at=datetime(2026, 10, 25, tzinfo=UTC),
    )


def test_fr_020_document_out_has_listing_fields_and_no_internal_ones() -> None:
    out = DocumentOut.from_document(make_document())
    data = out.model_dump()
    assert set(data) == {
        "id", "filename", "doc_type", "size_bytes", "page_count",
        "ocr_page_count", "chunk_count", "status", "created_at",
    }
    assert "stored_name" not in data and "sha256" not in data


def test_fr_021_chunk_out_fields() -> None:
    assert set(ChunkOut.model_fields) == {"id", "page", "ordinal", "source", "text"}


def test_fr_014_citation_out_fields() -> None:
    assert set(CitationOut.model_fields) == {
        "n", "chunk_id", "document_id", "filename", "page", "score", "passage",
    }


@pytest.mark.parametrize("question", ["hi", "x" * 1001])
def test_fr_010_ask_request_rejects_bad_question_length(question: str) -> None:
    with pytest.raises(ValidationError):
        AskRequest(question=question)


@pytest.mark.parametrize("top_k", [0, 11])
def test_fr_010_ask_request_top_k_bounds(top_k: int) -> None:
    with pytest.raises(ValidationError):
        AskRequest(question="What is it?", top_k=top_k)


def test_fr_010_ask_request_defaults_and_forbids_extra() -> None:
    assert AskRequest(question="What is it?").top_k == 4
    with pytest.raises(ValidationError):
        AskRequest.model_validate({"question": "What is it?", "history": []})


def test_fr_008_upload_response_reports_duplicate() -> None:
    resp = UploadResponse(document=DocumentOut.from_document(make_document()), duplicate=True)
    assert resp.duplicate is True
