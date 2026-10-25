from typing import Annotated

import anyio
from fastapi import APIRouter, Depends

from app.adapters import samples
from app.api.deps import Container, get_container
from app.core.errors import DocBotError
from app.core.models import FailedFile, LoadSamplesResponse, SamplesResponse
from app.settings import Settings

router = APIRouter(prefix="/samples", tags=["samples"])


async def _generate(settings: Settings) -> list[str]:
    paths = await anyio.to_thread.run_sync(
        samples.generate, settings.sample_dir, settings.golden_path
    )
    return [p.name for p in paths]


@router.post("/generate", response_model=SamplesResponse)
async def generate(container: Annotated[Container, Depends(get_container)]) -> SamplesResponse:
    """FR-030: write the 8 sample documents and eval/golden.yaml."""
    return SamplesResponse(files=await _generate(container.settings))


@router.post("/load", response_model=LoadSamplesResponse)
async def load(container: Annotated[Container, Depends(get_container)]) -> LoadSamplesResponse:
    """FR-031: ingest every file in the sample folder, generating the samples first if missing."""
    settings = container.settings
    folder = anyio.Path(settings.sample_dir)
    present = {p.name async for p in folder.iterdir()} if await folder.exists() else set()
    if not set(samples.source_text_by_file()) <= present:
        await _generate(settings)

    indexed, duplicates, failed = 0, 0, []
    for path in sorted([p async for p in folder.iterdir() if await p.is_file()]):
        try:
            _document, duplicate = await container.ingestion.ingest(
                path.name, await path.read_bytes()
            )
        except DocBotError as exc:
            failed.append(FailedFile(filename=path.name, reason=exc.message))
            continue
        duplicates += duplicate
        indexed += not duplicate
    return LoadSamplesResponse(indexed=indexed, duplicates=duplicates, failed=failed)
