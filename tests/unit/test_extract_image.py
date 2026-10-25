import pytest

from app.adapters.extractors import ImageExtractor, OcrEngine
from app.core.errors import ExtractionFailed
from tests.images import squash, text_image


@pytest.fixture(scope="module")
def ocr() -> OcrEngine:
    return OcrEngine()


def test_fr_005_png_text_is_ocr_page_one(ocr: OcrEngine) -> None:
    pages = ImageExtractor(ocr).extract(text_image(["LED headlamp", "High beam 13 W"]), ".png")
    assert len(pages) == 1
    assert pages[0].number == 1 and pages[0].source == "ocr"
    assert "highbeam13w" in squash(pages[0].text)


def test_fr_005_jpg_supported(ocr: OcrEngine) -> None:
    pages = ImageExtractor(ocr).extract(text_image(["Part DM-BRK-2210"], fmt="JPEG"), ".jpg")
    assert "dm-brk-2210" in squash(pages[0].text)


def test_ocr_lines_in_reading_order(ocr: OcrEngine) -> None:
    pages = ImageExtractor(ocr).extract(text_image(["Alpha first", "Bravo second"]), ".png")
    text = squash(pages[0].text)
    assert text.index("alpha") < text.index("bravo")


def test_blank_image_gives_empty_text(ocr: OcrEngine) -> None:
    pages = ImageExtractor(ocr).extract(text_image([]), ".png")
    assert pages[0].text.strip() == ""


def test_corrupt_image_raises_extraction_failed(ocr: OcrEngine) -> None:
    with pytest.raises(ExtractionFailed):
        ImageExtractor(ocr).extract(b"not an image", ".png")
