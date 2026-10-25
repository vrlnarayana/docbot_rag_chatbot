from pathlib import Path
from typing import Annotated, Any

import anyio
import yaml
from fastapi import APIRouter, Depends

from app.api.deps import Container, get_container
from app.core.errors import GoldenSetMissing, NoDocuments
from app.core.models import ErrorResponse, EvalRequest, EvalRunResponse, GoldenCase

router = APIRouter(prefix="/eval", tags=["evaluate"])


def _load_golden(path: Path) -> list[GoldenCase]:
    if not path.exists():
        raise GoldenSetMissing()
    raw: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [GoldenCase.model_validate(case) for case in raw]


@router.post(
    "/run",
    response_model=EvalRunResponse,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def run_evaluation(
    body: EvalRequest, container: Annotated[Container, Depends(get_container)]
) -> EvalRunResponse:
    """FR-040, FR-041: ask every golden question and score retrieval, answers and refusals."""
    _documents, chunks = await container.repository.counts()
    if chunks == 0:  # report an empty library before a missing golden set
        raise NoDocuments()
    cases = await anyio.to_thread.run_sync(_load_golden, container.settings.golden_path)
    return await container.evaluation.run(cases, body.top_k)
