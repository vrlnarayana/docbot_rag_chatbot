"""Domain exceptions. The API maps each `code` to an HTTP status and an `ErrorResponse`."""

SUPPORTED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md")


class DocBotError(Exception):
    code = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileType(DocBotError):
    code = "unsupported_type"

    def __init__(self, extension: str) -> None:
        shown = extension or "(none)"
        super().__init__(
            f"File type '{shown}' is not supported. "
            f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}."
        )


class FileTooLarge(DocBotError):
    code = "too_large"

    def __init__(self, limit_mb: int) -> None:
        super().__init__(
            f"File is larger than the {limit_mb} MB limit. "
            "Upload a smaller file or raise DOCBOT_MAX_UPLOAD_MB."
        )


class NoTextExtracted(DocBotError):
    code = "no_text"

    def __init__(self) -> None:
        super().__init__(
            "No readable text was found in this file, even with OCR. Nothing was stored."
        )


class ExtractionFailed(DocBotError):
    code = "extraction_failed"

    def __init__(self, reason: str) -> None:
        super().__init__(f"The file could not be read ({reason}). Nothing was stored.")


class DocumentNotFound(DocBotError):
    code = "not_found"

    def __init__(self, document_id: str) -> None:
        super().__init__(f"No document with id '{document_id}'.")


class NoDocuments(DocBotError):
    code = "no_documents"

    def __init__(self) -> None:
        super().__init__("No documents are indexed yet. Load the sample set first.")
