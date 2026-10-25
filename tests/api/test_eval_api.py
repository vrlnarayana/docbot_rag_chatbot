import httpx
import pytest
from fastapi import FastAPI

from app.adapters.generator_extractive import ExtractiveGenerator
from app.core.models import ErrorResponse, EvalRunResponse
from app.settings import Settings


@pytest.fixture
def extractive(app: FastAPI) -> None:
    container = app.state.container
    container.qa.generator = ExtractiveGenerator(container.ingestion.gate)


async def test_fr_040_empty_library_is_409(client: httpx.AsyncClient) -> None:
    resp = await client.post("/eval/run", json={})
    assert resp.status_code == 409
    assert ErrorResponse.model_validate(resp.json()).code == "no_documents"


async def test_fr_040_missing_golden_set_is_409(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    await client.post("/documents", files={"file": ("a.txt", b"Demo Motors brake fluid DOT 4.")})
    resp = await client.post("/eval/run", json={})
    assert resp.status_code == 409
    err = ErrorResponse.model_validate(resp.json())
    assert err.code == "no_golden" and "generate" in err.message
    assert str(settings.golden_path.parent) not in resp.text  # NFR-006: no file-system paths


@pytest.mark.usefixtures("extractive")
async def test_fr_040_fr_041_sample_corpus_evaluation(client: httpx.AsyncClient) -> None:
    await client.post("/samples/load")
    resp = await client.post("/eval/run", json={"top_k": 4})
    assert resp.status_code == 200
    run = EvalRunResponse.model_validate(resp.json())
    assert len(run.results) == 12
    s = run.summary
    assert (s.retriever, s.generator, s.top_k, s.cases) == ("keyword", "extractive", 4, 12)
    assert s.hit_rate_at_k == 100.0       # SC-001 asks for >= 80 % (vector); keyword here
    assert s.answer_accuracy >= 80.0      # SC-002
    assert s.refusal_accuracy == 100.0    # SC-003
    assert all(r.refusal_correct for r in run.results if r.expect_refusal)


async def test_eval_top_k_is_validated(client: httpx.AsyncClient) -> None:
    resp = await client.post("/eval/run", json={"top_k": 11})
    assert resp.status_code == 422
