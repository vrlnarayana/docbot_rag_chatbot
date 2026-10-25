"""Text extraction from text files, images (OCR) and PDFs (text layer or OCR).

All extractors are blocking; the ingestion service calls them in a worker thread.
"""

import io
import threading
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

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


def _open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ExtractionFailed("not a readable image") from exc
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
