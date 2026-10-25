from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.core.models import ErrorResponse, UploadResponse
from app.settings import Settings
from tests.images import mixed_pdf, table_pdf, text_image

FORBIDDEN = ("stored_name", "sha256", "/files/", "path")
TEXT = b"Rear sprocket on the Velo 125 changes from 42T to 43T, effective 1 November 2026."


async def upload(
    client: httpx.AsyncClient, name: str, data: bytes, mime: str = "application/octet-stream"
) -> httpx.Response:
    return await client.post("/documents", files={"file": (name, data, mime)})


def assert_safe(resp: httpx.Response) -> None:
    for word in FORBIDDEN:
        assert word not in resp.text, word


SAMPLES = {
    ".pdf": table_pdf([["Position", "Minimum thickness"], ["Front", "3.5 mm"]]),
    ".png": text_image(["High beam 13 W"]),
    ".jpg": text_image(["Part DM-BRK-2210"], fmt="JPEG"),
    ".jpeg": text_image(["Supplier code NWC"], fmt="JPEG"),
    ".txt": TEXT,
    ".md": b"# Owner manual\n\nRear tyre pressure 33 psi for a solo rider.",
}


@pytest.mark.parametrize("ext", list(SAMPLES))
async def test_fr_001_each_supported_type_is_indexed(client: httpx.AsyncClient, ext: str) -> None:
    resp = await upload(client, f"sample{ext}", SAMPLES[ext])
    assert resp.status_code == 201, resp.text
    body = UploadResponse.model_validate(resp.json())
    assert body.duplicate is False
    assert body.document.status == "indexed"
    assert body.document.chunk_count >= 1
    assert_safe(resp)


async def test_fr_005_image_is_ocr_page_one(client: httpx.AsyncClient) -> None:
    resp = await upload(client, "lamp.png", SAMPLES[".png"])
    doc = UploadResponse.model_validate(resp.json()).document
    assert (doc.doc_type, doc.page_count, doc.ocr_page_count) == ("image", 1, 1)


async def test_fr_004_scanned_pdf_page_is_ocrd(client: httpx.AsyncClient) -> None:
    data = mixed_pdf(["Certificate cover page with enough text."], ["Tensile strength 240 MPa"])
    resp = await upload(client, "cert.pdf", data)
    doc = UploadResponse.model_validate(resp.json()).document
    assert (doc.page_count, doc.ocr_page_count) == (2, 1)
    chunks = await client.get(f"/documents/{doc.id}/chunks")
    if chunks.status_code == 200:  # listing arrives in US-4; only check when present
        assert {c["source"] for c in chunks.json()} == {"text", "ocr"}


async def test_fr_008_duplicate_upload(client: httpx.AsyncClient) -> None:
    first = UploadResponse.model_validate((await upload(client, "a.txt", TEXT)).json())
    resp = await upload(client, "copy.txt", TEXT)
    assert resp.status_code == 200
    again = UploadResponse.model_validate(resp.json())
    assert again.duplicate is True
    assert again.document.id == first.document.id
    status = (await client.get("/status")).json()
    assert status["documents"] == 1


async def test_fr_002_unsupported_type_is_415(client: httpx.AsyncClient) -> None:
    resp = await upload(client, "spec.docx", b"PK\x03\x04")
    assert resp.status_code == 415
    err = ErrorResponse.model_validate(resp.json())
    assert ".pdf" in err.message and ".md" in err.message


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        retriever="keyword",
        max_upload_mb=1,
        _env_file=None,  # type: ignore[call-arg]
    )


async def test_fr_003_too_large_is_413_and_not_stored(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    resp = await upload(client, "big.txt", b"a" * (settings.max_upload_bytes + 1))
    assert resp.status_code == 413
    assert ErrorResponse.model_validate(resp.json()).code == "too_large"
    assert (await client.get("/status")).json()["documents"] == 0
    files = settings.files_dir
    assert not files.exists() or list(files.iterdir()) == []


async def test_fr_003_huge_content_length_rejected_before_reading(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.post(
        "/documents",
        content=b"x",
        headers={"content-type": "multipart/form-data; boundary=b", "content-length": "999999999"},
    )
    assert resp.status_code == 413


async def test_fr_009_empty_file_is_422(client: httpx.AsyncClient) -> None:
    resp = await upload(client, "empty.txt", b"")
    assert resp.status_code == 422
    assert ErrorResponse.model_validate(resp.json()).code == "no_text"
    assert (await client.get("/status")).json()["documents"] == 0


async def test_corrupt_pdf_is_422_and_service_keeps_running(client: httpx.AsyncClient) -> None:
    resp = await upload(client, "broken.pdf", b"%PDF-1.4 garbage")
    assert resp.status_code == 422
    assert ErrorResponse.model_validate(resp.json()).code == "extraction_failed"
    assert (await client.get("/health")).status_code == 200


async def test_missing_file_field_is_422(client: httpx.AsyncClient) -> None:
    resp = await client.post("/documents", data={"other": "x"})
    assert resp.status_code == 422
    assert ErrorResponse.model_validate(resp.json()).code == "validation_error"


async def test_unsafe_filename_kept_for_display_only(client: httpx.AsyncClient) -> None:
    resp = await upload(client, "../../etc/Ölfilter Notiz.txt", TEXT)
    assert resp.status_code == 201
    doc = UploadResponse.model_validate(resp.json()).document
    assert doc.filename == "../../etc/Ölfilter Notiz.txt"


async def test_fr_003_upload_without_content_length_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    async def chunked() -> AsyncIterator[bytes]:  # httpx sends no Content-Length for this
        yield b"--b\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.txt\"\r\n\r\n"
        yield b"x" * 1000
        yield b"\r\n--b--\r\n"

    resp = await client.post(
        "/documents",
        content=chunked(),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    assert resp.status_code == 411
    assert ErrorResponse.model_validate(resp.json()).code == "length_required"
    assert (await client.get("/status")).json()["documents"] == 0
