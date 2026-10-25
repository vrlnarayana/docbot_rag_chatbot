import httpx
import pytest
from fastapi import FastAPI

from app.core.errors import DocumentNotFound
from app.core.models import ErrorResponse, HealthResponse, StatusResponse


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert HealthResponse.model_validate(resp.json()).status == "ok"


async def test_fr_051_status_reports_configuration_and_counts(client: httpx.AsyncClient) -> None:
    resp = await client.get("/status")
    assert resp.status_code == 200
    status = StatusResponse.model_validate(resp.json())
    assert status.retriever == "keyword"
    assert status.generator == "extractive"
    assert (status.documents, status.chunks) == (0, 0)
    assert status.fallbacks == []


def test_fr_052_startup_fails_with_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.main import create_app

    monkeypatch.setenv("DOCBOT_GENERATOR", "azure_openai")
    with pytest.raises(SystemExit) as exc:
        create_app()
    msg = str(exc.value)
    assert "Unknown generator 'azure_openai'" in msg
    assert "Valid options: extractive, ollama" in msg
    assert "Traceback" not in msg


async def test_domain_errors_become_error_response(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    @app.get("/_boom")
    async def boom() -> None:  # test-only route
        raise DocumentNotFound("x")

    resp = await client.get("/_boom")
    assert resp.status_code == 404
    err = ErrorResponse.model_validate(resp.json())
    assert err.code == "not_found"


async def test_nfr_006_unexpected_errors_hide_details(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    @app.get("/_crash")
    async def crash() -> None:  # test-only route
        raise RuntimeError("/secret/path/docbot.db exploded")

    resp = await client.get("/_crash")
    assert resp.status_code == 500
    body = resp.text
    assert "/secret/path" not in body and "Traceback" not in body
    assert ErrorResponse.model_validate(resp.json()).code == "internal_error"


async def test_validation_errors_use_error_shape(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    from pydantic import BaseModel

    class Body(BaseModel):
        n: int

    @app.post("/_validate")
    async def validate(body: Body) -> None:  # test-only route
        return None

    resp = await client.post("/_validate", json={"n": "nope"})
    assert resp.status_code == 422
    assert ErrorResponse.model_validate(resp.json()).code == "validation_error"
