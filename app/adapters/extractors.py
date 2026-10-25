"""Text extraction from text files, images (OCR) and PDFs (text layer or OCR).

All extractors are blocking; the ingestion service calls them in a worker thread.
"""

import io
import math
import re
import threading
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.core.chunking import MIN_CHUNK_CHARS
from app.core.errors import ExtractionFailed
from app.core.models import Page


class OcrEngine:
    """RapidOCR (ONNX models bundled with the package, works offline), loaded on first use."""

    def __init__(self) -> None:
        self._engine: Any = None
        self._lock = threading.Lock()

    def read(self, image: Image.Image) -> str:
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR

                self._engine = RapidOCR()
            result, _elapsed = self._engine(np.asarray(image.convert("RGB")))
        return _reading_order(result or [])


def _reading_order(result: list[Any]) -> str:
    """Join OCR boxes top-to-bottom, then left-to-right; boxes on one row form one line."""
    boxes = []
    for box, text, _score in result:
        ys = [p[1] for p in box]
        boxes.append((min(ys), max(ys), min(p[0] for p in box), str(text)))
    boxes.sort(key=lambda b: (b[0], b[2]))
    rows: list[list[tuple[float, float, float, str]]] = []
    for b in boxes:
        if rows:
            top, bottom = rows[-1][0][0], rows[-1][0][1]
            if (b[0] + b[1]) / 2 < bottom and (b[0] + b[1]) / 2 > top:
                rows[-1].append(b)
                continue
        rows.append([b])
    return "\n".join(" ".join(t for *_, t in sorted(row, key=lambda b: b[2])) for row in rows)


MAX_IMAGE_SIDE = 10_000
MAX_IMAGE_PIXELS = 40_000_000


def _open_image(data: bytes) -> Image.Image:
    """Decode PNG or JPEG only, and check the size before decoding the pixels."""
    try:
        image = Image.open(io.BytesIO(data), formats=["PNG", "JPEG"])
        width, height = image.size
        if max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
            raise ExtractionFailed(f"image is too large; the limit is {MAX_IMAGE_SIDE} px a side")
        image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ExtractionFailed("not a readable PNG or JPEG image") from exc
    return image


class TextFileExtractor:
    """FR-006: the whole file is page 1, decoded as UTF-8 with a Latin-1 fallback."""

    def extract(self, data: bytes, extension: str) -> list[Page]:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        return [Page(number=1, text=text, source="text")]


class ImageExtractor:
    """FR-005: OCR the whole image as page 1."""

    def __init__(self, ocr: OcrEngine) -> None:
        self._ocr = ocr

    def extract(self, data: bytes, extension: str) -> list[Page]:
        return [Page(number=1, text=self._ocr.read(_open_image(data)), source="ocr")]


_PDFIUM_LOCK = threading.Lock()  # pdfium is not thread-safe
_COLUMN_GAP = re.compile(r" {2,}")
_OCR_DPI = 200


def _tidy_layout_text(text: str) -> str:
    """Keep table rows on one line, with ' | ' between columns (plan §7.1)."""
    lines = [_COLUMN_GAP.sub(" | ", line.strip()) for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class PdfExtractor:
    """FR-001, FR-004: text layer per page; pages with almost no text are rendered and OCR'd."""

    def __init__(self, ocr: OcrEngine) -> None:
        self._ocr = ocr

    def extract(self, data: bytes, extension: str) -> list[Page]:
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ExtractionFailed("the PDF is encrypted")
            texts = [
                _tidy_layout_text(p.extract_text(extraction_mode="layout")) for p in reader.pages
            ]
        except ExtractionFailed:
            raise
        except Exception as exc:  # pypdf raises many types for damaged files
            raise ExtractionFailed("not a valid PDF") from exc

        pages: list[Page] = []
        for number, text in enumerate(texts, start=1):
            if len(text) >= MIN_CHUNK_CHARS:
                pages.append(Page(number=number, text=text, source="text"))
            else:
                ocr_text = self._ocr.read(self._render(data, number - 1))
                pages.append(Page(number=number, text=ocr_text, source="ocr"))
        return pages

    @staticmethod
    def _render(data: bytes, index: int) -> Image.Image:
        import pypdfium2 as pdfium

        with _PDFIUM_LOCK:
            pdf = pdfium.PdfDocument(data)
            try:
                page = pdf[index]
                width_pt, height_pt = page.get_size()
                if width_pt <= 0 or height_pt <= 0:
                    raise ExtractionFailed("a PDF page has no size")
                scale = min(
                    _OCR_DPI / 72,
                    MAX_IMAGE_SIDE / max(width_pt, height_pt),
                    math.sqrt(MAX_IMAGE_PIXELS / (width_pt * height_pt)),
                )
                image: Image.Image = page.render(scale=scale).to_pil()
            finally:
                pdf.close()
        return image
