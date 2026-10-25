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

    def __init__(self, limit_mb: int, what: str = "File", setting: str = "DOCBOT_MAX_UPLOAD_MB"):
        super().__init__(
            f"{what} is larger than the {limit_mb} MB limit. "
            f"Upload a smaller file or raise {setting}."
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


class GoldenSetMissing(DocBotError):
    code = "no_golden"

    def __init__(self) -> None:
        super().__init__(
            "The golden question set (eval/golden.yaml) was not found. Generate it with "
            "`python scripts/generate_samples.py` or the \"Generate & load sample documents\" "
            "button."
        )


class NoDocuments(DocBotError):
    code = "no_documents"

    def __init__(self) -> None:
        super().__init__("No documents are indexed yet. Load the sample set first.")


class LengthRequired(DocBotError):
    code = "length_required"

    def __init__(self) -> None:
        super().__init__(
            "Uploads must declare their size (Content-Length header) so the limit can be checked."
        )


class EmbeddingUnavailable(DocBotError):
    code = "embedding_unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"Embeddings are unavailable: {reason} Nothing was stored. "
            "Set DOCBOT_EMBEDDER=fastembed to use the local model instead."
        )
