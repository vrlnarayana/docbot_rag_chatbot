from pathlib import Path

import pytest
import yaml
from pypdf import PdfReader

from app.adapters import samples
from app.adapters.extractors import ImageExtractor, OcrEngine, PdfExtractor
from app.core.models import GoldenCase
from app.core.text import tokenize

FILES = [
    "DM-STD-BRK-001_Brake_System_Design_Standard.pdf",
    "TR-2026-014_Handlebar_Vibration_Test_Report.pdf",
    "SC-889_Supplier_Certificate_Northwind_Castings.pdf",
    "DM-SPEC-LMP-12_Headlamp_Spec_Sheet.png",
    "Label_DM-BRK-2210_Front_Caliper.jpg",
    "DM-ECN-0457_Engineering_Change_Note.txt",
    "Velo125_Owner_Manual_Extract.md",
    "DM-GATE-G3_Readiness_Checklist.md",
]


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("gen")
    samples.generate(root / "sample_data", root / "eval" / "golden.yaml")
    return root / "sample_data", root / "eval" / "golden.yaml"


def test_fr_030_generates_the_eight_files_and_golden_set(generated: tuple[Path, Path]) -> None:
    sample_dir, golden = generated
    assert sorted(p.name for p in sample_dir.iterdir()) == sorted(FILES)
    cases = [GoldenCase.model_validate(c) for c in yaml.safe_load(golden.read_text())]
    assert len(cases) == 12
    assert sum(c.expect_refusal for c in cases) == 3
    assert {c.expected_file for c in cases if not c.expect_refusal} <= set(FILES)


def test_fr_030_output_is_deterministic(
    generated: tuple[Path, Path], tmp_path: Path
) -> None:
    sample_dir, golden = generated
    samples.generate(tmp_path / "again", tmp_path / "golden.yaml")
    for name in FILES:
        assert (tmp_path / "again" / name).read_bytes() == (sample_dir / name).read_bytes(), name
    assert (tmp_path / "golden.yaml").read_bytes() == golden.read_bytes()


def test_pdfs_have_expected_pages_and_fit_the_pdf_limit(generated: tuple[Path, Path]) -> None:
    sample_dir, _ = generated
    pdfs = [name for name in FILES if name.endswith(".pdf")]
    pages = {name: len(PdfReader(sample_dir / name).pages) for name in pdfs}
    assert list(pages.values()) == [3, 2, 1]
    for name in pages:
        assert (sample_dir / name).stat().st_size < 1024 * 1024, name  # FR-003 PDF limit


def test_scanned_certificate_has_no_text_layer(generated: tuple[Path, Path]) -> None:
    sample_dir, _ = generated
    page = PdfReader(sample_dir / FILES[2]).pages[0]
    assert len(page.extract_text().strip()) < 20


def test_facts_are_where_the_golden_set_expects(generated: tuple[Path, Path]) -> None:
    sample_dir, _ = generated
    ocr = OcrEngine()
    brake = PdfExtractor(ocr).extract((sample_dir / FILES[0]).read_bytes(), ".pdf")
    assert "Front | 276 mm | 3.5 mm" in brake[1].text
    assert "DOT 4" in brake[2].text
    report = PdfExtractor(ocr).extract((sample_dir / FILES[1]).read_bytes(), ".pdf")
    assert "18.2" in report[1].text
    cert = PdfExtractor(ocr).extract((sample_dir / FILES[2]).read_bytes(), ".pdf")
    # OCR text is compared case-insensitively, as the evaluation does (FR-040).
    assert cert[0].source == "ocr" and "240 mpa" in cert[0].text.lower()
    assert "northwind castings" in cert[0].text.lower()
    lamp = ImageExtractor(ocr).extract((sample_dir / FILES[3]).read_bytes(), ".png")
    assert "13 w" in lamp[0].text.lower() and "led headlamp" in lamp[0].text.lower()
    label = ImageExtractor(ocr).extract((sample_dir / FILES[4]).read_bytes(), ".jpg")
    assert "dm-brk-2210" in label[0].text.lower()
    assert "front brake caliper" in label[0].text.lower()
    assert "43T" in (sample_dir / FILES[5]).read_text()
    assert "33 psi" in (sample_dir / FILES[6]).read_text()
    assert "95%" in (sample_dir / FILES[7]).read_text()


def test_fr_032_content_is_fictional_and_avoids_the_refusal_topics() -> None:
    text = " ".join(samples.all_source_text()).lower()
    assert "demo motors" in text and "velo 125" in text
    words = set(tokenize(text))
    for forbidden in ("speed", "ceo", "battery", "warranty"):
        assert forbidden not in words, forbidden


def test_golden_questions_use_words_from_their_documents() -> None:
    # Plan §8: each fact is worded with its question's key terms.
    by_file = samples.source_text_by_file()
    for case in samples.GOLDEN:
        if case.expect_refusal:
            continue
        doc_words = set(tokenize(" ".join(by_file[case.expected_file or ""])))
        missing = set(tokenize(case.question)) - doc_words
        assert not missing, (case.question, missing)
