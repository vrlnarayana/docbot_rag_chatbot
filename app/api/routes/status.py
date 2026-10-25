from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import Container, get_container
from app.core.models import HealthResponse, StatusResponse

router = APIRouter(tags=["status"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/status", response_model=StatusResponse)
async def status(container: Annotated[Container, Depends(get_container)]) -> StatusResponse:
    settings = container.settings
    retriever = container.retriever.name
    documents, chunks = await container.repository.counts()
    return StatusResponse(
        retriever=retriever,
        generator=settings.generator,
        embed_model=settings.embed_model if retriever == "vector" else None,
        documents=documents,
        chunks=chunks,
        fallbacks=container.fallbacks,
        notices=container.notices,
    )
