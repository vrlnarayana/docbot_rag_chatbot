import httpx
from fastapi import FastAPI

from app.adapters.generator_extractive import ExtractiveGenerator
from app.core.models import AskResponse, DeleteResponse, ErrorResponse, UploadResponse
from app.settings import Settings

MANUAL = (b"# Demo Motors Velo 125 owner manual\n\nRecommended tyre pressure, solo rider: "
          b"front 29 psi, rear 33 psi.")
ECN = b"Demo Motors change note: new rear sprocket size for the Velo 125 is 43T."
GATE = b"Demo Motors Gate G3 checklist: DVP&R completion required to exit Gate G3 is 95%."


async def upload(client: httpx.AsyncClient, name: str, data: bytes) -> str:
    resp = await client.post("/documents", files={"file": (name, data)})
    return UploadResponse.model_validate(resp.json()).document.id


async def test_fr_022_delete_removes_document_chunks_and_file(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    doc_id = await upload(client, "manual.md", MANUAL)
    await upload(client, "ecn.txt", ECN)
    assert len(list(settings.files_dir.iterdir())) == 2

    resp = await client.delete(f"/documents/{doc_id}")
    assert resp.status_code == 200
    assert DeleteResponse.model_validate(resp.json()).deleted_id == doc_id
    assert (await client.get(f"/documents/{doc_id}")).status_code == 404
    assert (await client.get(f"/documents/{doc_id}/chunks")).status_code == 404
    assert len(list(settings.files_dir.iterdir())) == 1
    status = (await client.get("/status")).json()
    assert (status["documents"], status["chunks"]) == (1, 1)


async def test_fr_022_deleted_document_is_never_cited(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    container = app.state.container
    container.qa.generator = ExtractiveGenerator(container.ingestion.gate)
    doc_id = await upload(client, "manual.md", MANUAL)
    await upload(client, "ecn.txt", ECN)
    await upload(client, "gate.md", GATE)  # BM25 needs 3+ documents for positive IDF
    q = {"question": "What is the recommended rear tyre pressure?"}
    before = AskResponse.model_validate((await client.post("/ask", json=q)).json())
    assert before.citations[0].document_id == doc_id

    await client.delete(f"/documents/{doc_id}")
    after = AskResponse.model_validate((await client.post("/ask", json=q)).json())
    assert all(c.document_id != doc_id for c in after.citations)
    assert after.grounded is False


async def test_fr_022_unknown_id_is_404(client: httpx.AsyncClient) -> None:
    resp = await client.delete("/documents/nope")
    assert resp.status_code == 404
    assert ErrorResponse.model_validate(resp.json()).code == "not_found"


async def test_fr_023_no_bulk_delete(app: FastAPI, client: httpx.AsyncClient) -> None:
    paths = app.openapi()["paths"]
    delete_paths = [path for path, methods in paths.items() if "delete" in methods]
    assert delete_paths == ["/documents/{document_id}"]
    assert (await client.delete("/documents")).status_code == 405
