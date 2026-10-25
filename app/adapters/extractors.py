"""Text extraction from text files, images (OCR) and PDFs (text layer or OCR).

All extractors are blocking; the ingestion service calls them in a worker thread.
"""

from app.core.models import Page


class TextFileExtractor:
    """FR-006: the whole file is page 1, decoded as UTF-8 with a Latin-1 fallback."""

    def extract(self, data: bytes, extension: str) -> list[Page]:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        return [Page(number=1, text=text, source="text")]
