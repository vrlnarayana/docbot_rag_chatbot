from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import Container, get_container
from app.core.models import AskRequest, AskResponse, ErrorResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse, responses={422: {"model": ErrorResponse}})
async def ask(
    body: AskRequest, container: Annotated[Container, Depends(get_container)]
) -> AskResponse:
    """FR-010…FR-018: answer from the indexed documents, with citations, or refuse."""
    return await container.qa.ask(body.question, body.top_k)
