import io

import pytest
from pypdf import PdfReader, PdfWriter

from app.adapters.extractors import OcrEngine, PdfExtractor
from app.core.errors import ExtractionFailed
from tests.images import mixed_pdf, squash, table_pdf, text_pdf


@pytest.fixture(scope="module")
def extractor() -> PdfExtractor:
    return PdfExtractor(OcrEngine())


def test_fr_001_text_pdf_pages(extractor: PdfExtractor) -> None:
    data = text_pdf(
        [["Scope and purpose of the standard."], ["Brake fluid DOT 4, replace every 2 years."]]
    )
    pages = extractor.extract(data, ".pdf")
    assert [(p.number, p.source) for p in pages] == [(1, "text"), (2, "text")]
    assert "DOT 4" in pages[1].text


def test_fr_001_table_rows_stay_on_one_line(extractor: PdfExtractor) -> None:
    data = table_pdf([["Position", "Disc diameter", "Minimum thickness"],
                      ["Front", "276 mm", "3.5 mm"], ["Rear", "220 mm", "4.0 mm"]])
    text = extractor.extract(data, ".pdf")[0].text
    assert "Front | 276 mm | 3.5 mm" in text.splitlines()


def test_fr_004_page_without_text_layer_is_ocrd(extractor: PdfExtractor) -> None:
    data = mixed_pdf(["Certificate cover page with enough text."], ["Tensile strength 240 MPa"])
    pages = extractor.extract(data, ".pdf")
    assert [(p.number, p.source) for p in pages] == [(1, "text"), (2, "ocr")]
    assert "240mpa" in squash(pages[1].text)


def test_encrypted_pdf_is_rejected(extractor: PdfExtractor) -> None:
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(text_pdf([["secret"]]))).pages:
        writer.add_page(page)
    writer.encrypt("pw")
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ExtractionFailed, match="encrypted"):
        extractor.extract(buf.getvalue(), ".pdf")


def test_corrupt_pdf_is_rejected(extractor: PdfExtractor) -> None:
    with pytest.raises(ExtractionFailed):
        extractor.extract(b"%PDF-1.4 garbage", ".pdf")
