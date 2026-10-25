"""Image decoding is limited to PNG/JPEG and to a bounded pixel size."""

import io

import pytest
from PIL import Image

from app.adapters.extractors import MAX_IMAGE_SIDE, ImageExtractor, OcrEngine, PdfExtractor
from app.core.errors import ExtractionFailed


def encoded(fmt: str, size: tuple[int, int] = (50, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["BMP", "GIF", "TIFF"])
def test_other_image_formats_are_not_decoded(fmt: str) -> None:
    with pytest.raises(ExtractionFailed):
        ImageExtractor(OcrEngine()).extract(encoded(fmt), ".png")


def test_oversized_image_is_rejected_before_ocr() -> None:
    data = encoded("PNG", (MAX_IMAGE_SIDE + 1, 10))
    with pytest.raises(ExtractionFailed, match="too large"):
        ImageExtractor(OcrEngine()).extract(data, ".png")


def test_pdf_render_is_capped_for_huge_pages() -> None:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(14400, 14400), invariant=1)  # 200 in square page
    c.showPage()
    c.save()
    image = PdfExtractor._render(buf.getvalue(), 0)
    assert max(image.size) <= MAX_IMAGE_SIDE
