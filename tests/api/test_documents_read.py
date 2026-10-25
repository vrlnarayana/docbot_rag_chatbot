import httpx

from app.core.models import ChunkOut, DocumentOut, ErrorResponse, UploadResponse
from tests.images import mixed_pdf

TEXT = b"Rear sprocket on the Velo 125 changes from 42T to 43T, effective 1 November 2026."
FORBIDDEN = ("stored_name", "sha256", "/files/")


async def upload(client: httpx.AsyncClient, name: str, data: bytes) -> DocumentOut:
    resp = await client.post("/documents", files={"file": (name, data)})
    return UploadResponse.model_validate(resp.json()).document


async def test_fr_020_lists_documents_with_all_fields(client: httpx.AsyncClient) -> None:
    a = await upload(client, "ecn.txt", TEXT)
    b = await upload(client, "cert.pdf", mixed_pdf(["Demo Motors certificate cover page."],
                                                    ["Tensile strength 240 MPa"]))
    resp = await client.get("/documents")
    assert resp.status_code == 200
    docs = [DocumentOut.model_validate(d) for d in resp.json()]
    assert [d.id for d in docs] == [a.id, b.id]
    cert = docs[1]
    assert (cert.filename, cert.doc_type, cert.page_count, cert.ocr_page_count) == (
        "cert.pdf", "pdf", 2, 1)
    assert cert.chunk_count >= 2 and cert.size_bytes > 0 and cert.status == "indexed"
    for word in FORBIDDEN:
        assert word not in resp.text


async def test_fr_020_empty_library_lists_nothing(client: httpx.AsyncClient) -> None:
    assert (await client.get("/documents")).json() == []


async def test_fr_020_get_one_document(client: httpx.AsyncClient) -> None:
    doc = await upload(client, "ecn.txt", TEXT)
    resp = await client.get(f"/documents/{doc.id}")
    assert resp.status_code == 200
    assert DocumentOut.model_validate(resp.json()) == doc


async def test_fr_021_chunks_in_page_order_with_source(client: httpx.AsyncClient) -> None:
    doc = await upload(client, "cert.pdf", mixed_pdf(["Demo Motors certificate cover page."],
                                                     ["Tensile strength 240 MPa"]))
    resp = await client.get(f"/documents/{doc.id}/chunks")
    assert resp.status_code == 200
    chunks = [ChunkOut.model_validate(c) for c in resp.json()]
    assert [(c.page, c.source) for c in chunks] == [(1, "text"), (2, "ocr")]
    assert "240" in chunks[1].text
    assert [c.ordinal for c in chunks] == sorted(c.ordinal for c in chunks)


async def test_unknown_document_is_404(client: httpx.AsyncClient) -> None:
    for path in ("/documents/nope", "/documents/nope/chunks"):
        resp = await client.get(path)
        assert resp.status_code == 404
        assert ErrorResponse.model_validate(resp.json()).code == "not_found"
