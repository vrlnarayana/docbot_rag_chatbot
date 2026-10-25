from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import UploadFile

from app.api.deps import Container, get_container
from app.core.errors import FileTooLarge, LengthRequired
from app.core.models import DocumentOut, ErrorResponse, UploadResponse

router = APIRouter(tags=["documents"])

_MULTIPART_OVERHEAD = 64 * 1024
_READ_BLOCK = 1024 * 1024
_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (411, 413, 415, 422)
}
_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}


async def _read_limited(upload: UploadFile, limit_bytes: int) -> bytes | None:
    """Read the file, or return None as soon as it goes over the limit."""
    data = bytearray()
    while block := await upload.read(_READ_BLOCK):
        data.extend(block)
        if len(data) > limit_bytes:
            return None
    return bytes(data)


@router.post(
    "/documents",
    response_model=UploadResponse,
    status_code=201,
    responses={200: {"model": UploadResponse, "description": "Already indexed"}, **_ERRORS},
    openapi_extra=_UPLOAD_BODY,
)
async def upload_document(
    request: Request,
    response: Response,
    container: Annotated[Container, Depends(get_container)],
) -> UploadResponse:
    """FR-001…FR-009. The size limit is checked before the body is parsed or read.

    A declared Content-Length is required: without it (chunked transfer) the multipart parser
    would spool an unbounded body to disk before the per-file limit could apply.
    """
    settings = container.settings
    declared = request.headers.get("content-length")
    if not declared or not declared.isdigit():
        raise LengthRequired()
    if int(declared) > settings.max_upload_bytes + _MULTIPART_OVERHEAD:
        raise FileTooLarge(settings.max_upload_mb)

    async with request.form(max_files=1, max_fields=1) as form:
        upload = form.get("file")
        if not isinstance(upload, UploadFile) or not upload.filename:
            raise RequestValidationError(
                [{"loc": ("body", "file"), "msg": "a file is required", "type": "missing"}]
            )
        ingestion = container.ingestion
        extension = ingestion.check_upload(upload.filename)
        data = await _read_limited(upload, ingestion.size_limit(extension))
        if data is None:
            raise ingestion.too_large(extension)
        document, duplicate = await container.ingestion.ingest(upload.filename, data)

    response.status_code = 200 if duplicate else 201
    return UploadResponse(document=DocumentOut.from_document(document), duplicate=duplicate)
