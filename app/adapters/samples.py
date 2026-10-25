"""Deterministic, fictional sample corpus and golden set (FR-030, FR-032, spec §8, plan §8).

Company "Demo Motors", model "Velo 125". Each fact is worded with the key terms of its golden
question, and the refusal topics (top speed, CEO, battery warranty) appear nowhere.
Running `generate` twice produces byte-identical files.
"""

import io
import random
import time
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

from app.core.models import GoldenCase

BRAKE = "DM-STD-BRK-001_Brake_System_Design_Standard.pdf"
REPORT = "TR-2026-014_Handlebar_Vibration_Test_Report.pdf"
CERT = "SC-889_Supplier_Certificate_Northwind_Castings.pdf"
LAMP = "DM-SPEC-LMP-12_Headlamp_Spec_Sheet.png"
LABEL = "Label_DM-BRK-2210_Front_Caliper.jpg"
ECN = "DM-ECN-0457_Engineering_Change_Note.txt"
MANUAL = "Velo125_Owner_Manual_Extract.md"
GATE = "DM-GATE-G3_Readiness_Checklist.md"

# --- Content ---------------------------------------------------------------------------------
# PDF pages: a list of blocks; a block is a paragraph (str) or a table (list of rows).
Block = str | list[list[str]]

BRAKE_PAGES: list[list[Block]] = [
    [
        "Brake System Design Standard DM-STD-BRK-001",
        "Demo Motors - Velo 125 - Revision C",
        "1. Scope and purpose",
        "This brake standard defines the design requirements for the front and rear disc "
        "brakes of the Demo Motors Velo 125. It applies to all brake components supplied for "
        "series production.",
    ],
    [
        "2. Brake disc specifications",
        [
            ["Position", "Disc diameter", "Minimum thickness"],
            ["Front", "276 mm", "3.5 mm"],
            ["Rear", "220 mm", "4.0 mm"],
        ],
        "Replace a disc that is worn below its minimum thickness.",
    ],
    [
        "3. Brake fluid",
        "Suppliers shall specify DOT 4 brake fluid, as required by this brake standard.",
        "Replace the brake fluid every 2 years or 20,000 km, whichever comes first.",
    ],
]

REPORT_PAGES: list[list[Block]] = [
    [
        "Handlebar Vibration Test Report TR-2026-014",
        "Demo Motors - Velo 125",
        "1. Test set-up",
        "A tri-axial accelerometer was fixed to the left handlebar grip. The engine was swept "
        "from idle to 9,000 rpm on a chassis dynamometer.",
    ],
    [
        "2. Result",
        "Peak handlebar vibration in the test: 18.2 m/s² at 6,500 rpm.",
        "Acceptance limit: 20 m/s² maximum.",
        "Verdict: PASS.",
    ],
]

# The certificate is an image-only PDF. The letterhead names the supplier, so the supplier and
# the tensile strength sit close together, as on a real certificate.
CERT_LINES = [
    "NORTHWIND CASTINGS",
    "Supplier Certificate SC-889",
    "Tensile strength: 240 MPa",
    "Material: AlSi10Mg",
    "Customer: Demo Motors, Velo 125",
    "Certificate valid until: 31 March 2027",
]

LAMP_LINES = [
    "LED HEADLAMP SPEC SHEET DM-SPEC-LMP-12",
    "High beam wattage: 13 W",
    "Low beam wattage: 9 W",
    "Supply voltage: 12 V",
    "Ingress rating: IP67",
    "Demo Motors - Velo 125",
]

LABEL_LINES = [
    "DEMO MOTORS",
    "Part no. DM-BRK-2210",
    "Front brake caliper",
    "2 pistons",
    "Supplier code: NWC",
]

ECN_TEXT = """Demo Motors - Engineering Change Note DM-ECN-0457
Product: Velo 125

Change: New rear sprocket size for the Velo 125: 43T (was 42T).
Effective date: 1 November 2026.
Reason: better low-end torque on hill climbs.
"""

MANUAL_TEXT = """# Velo 125 Owner Manual (extract)

Demo Motors

## Tyres

Recommended tyre pressure (solo rider): front 29 psi, rear 33 psi.

## Engine oil

Engine oil: SAE 10W-30, capacity 1.0 L.
"""

GATE_TEXT = """# Gate G3 Readiness Checklist (DM-GATE-G3)

Demo Motors - Velo 125 programme

## Exit criteria

- DVP&R completion required to exit Gate G3: ≥ 95%
- Open DFMEA items with RPN > 100: must be 0
- PPAP status: submitted for all critical parts
"""

GOLDEN = [
    GoldenCase(question="What is the minimum thickness of the front brake disc?",
               expected_file=BRAKE, expected_page=2, expected_keywords=["3.5 mm"]),
    GoldenCase(question="What brake fluid does the brake standard specify?",
               expected_file=BRAKE, expected_page=3, expected_keywords=["DOT 4"]),
    GoldenCase(question="What was the peak handlebar vibration in the test?",
               expected_file=REPORT, expected_page=2, expected_keywords=["18.2"]),
    GoldenCase(question="What is the tensile strength on the Northwind Castings certificate?",
               expected_file=CERT, expected_page=1, expected_keywords=["240 MPa"]),
    GoldenCase(question="What is the high beam wattage of the LED headlamp?",
               expected_file=LAMP, expected_page=1, expected_keywords=["13 W"]),
    GoldenCase(question="How many pistons does the front brake caliper have?",
               expected_file=LABEL, expected_page=1, expected_keywords=["2"]),
    GoldenCase(question="What is the new rear sprocket size for the Velo 125?",
               expected_file=ECN, expected_page=1, expected_keywords=["43T"]),
    GoldenCase(question="What is the recommended rear tyre pressure?",
               expected_file=MANUAL, expected_page=1, expected_keywords=["33 psi"]),
    GoldenCase(question="What DVP&R completion is required to exit Gate G3?",
               expected_file=GATE, expected_page=1, expected_keywords=["95%"]),
    GoldenCase(question="What is the top speed of the Velo 125?", expect_refusal=True),
    GoldenCase(question="Who is the CEO of Demo Motors?", expect_refusal=True),
    GoldenCase(question="What is the warranty period for the battery?", expect_refusal=True),
]


def _block_text(block: Block) -> list[str]:
    return [block] if isinstance(block, str) else [" ".join(row) for row in block]


def source_text_by_file() -> dict[str, list[str]]:
    """Every string written into each sample file (used by tests and for auditing content)."""

    def pages_text(pages: list[list[Block]]) -> list[str]:
        return [t for page in pages for block in page for t in _block_text(block)]

    return {
        BRAKE: pages_text(BRAKE_PAGES),
        REPORT: pages_text(REPORT_PAGES),
        CERT: CERT_LINES,
        LAMP: LAMP_LINES,
        LABEL: LABEL_LINES,
        ECN: [ECN_TEXT],
        MANUAL: [MANUAL_TEXT],
        GATE: [GATE_TEXT],
    }


def all_source_text() -> list[str]:
    return [t for texts in source_text_by_file().values() for t in texts]


# --- Rendering -------------------------------------------------------------------------------


def _text_pdf(pages: list[list[Block]]) -> bytes:
    styles = getSampleStyleSheet()
    story: list[object] = []
    for i, page in enumerate(pages):
        if i:
            story.append(PageBreak())
        for j, block in enumerate(page):
            if isinstance(block, str):
                style = styles["Title"] if (i == 0 and j == 0) else styles["BodyText"]
                story += [Paragraph(block, style), Spacer(1, 8)]
            else:
                story += [Table(block), Spacer(1, 8)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, invariant=1, title="Demo Motors sample").build(story)
    return buf.getvalue()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


WORD_GAP = 0.9  # in em; RapidOCR's bundled model drops normal-width spaces between words


def _draw_lines(
    image: Image.Image, lines: list[str], size: int, top: int, left: int, gap: int
) -> None:
    """Draw word by word with wide gaps, so OCR returns one box per word and keeps the spaces."""
    draw = ImageDraw.Draw(image)
    font = _font(size)
    ink = 0 if image.mode == "L" else "black"
    for i, line in enumerate(lines):
        x = float(left)
        for word in line.split(" "):
            draw.text((x, top + i * gap), word, fill=ink, font=font)
            x += draw.textlength(word, font=font) + size * WORD_GAP


def _scanned_pdf(lines: list[str]) -> bytes:
    """An A4 page at 200 DPI, drawn as an image with light specks, saved with no text layer."""
    page = Image.new("L", (1654, 2339), 255)
    _draw_lines(page, lines, size=56, top=240, left=160, gap=120)
    rng = random.Random(889)
    pixels = page.load()
    assert pixels is not None
    for _ in range(4000):
        pixels[rng.randrange(1654), rng.randrange(2339)] = rng.randrange(150, 230)
    buf = io.BytesIO()
    fixed = time.strptime("2026-10-25", "%Y-%m-%d")  # Pillow stamps the current time otherwise
    page.save(buf, "PDF", resolution=200, creationDate=fixed, modDate=fixed)
    return buf.getvalue()


def _spec_sheet_png(lines: list[str]) -> bytes:
    image = Image.new("RGB", (1700, 620), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 1680, 600), outline="black", width=3)
    draw.line((40, 120, 1660, 120), fill="black", width=2)
    _draw_lines(image, lines[:1], size=44, top=50, left=60, gap=0)
    _draw_lines(image, lines[1:], size=40, top=150, left=60, gap=85)
    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=False)
    return buf.getvalue()


def _label_jpg(lines: list[str]) -> bytes:
    image = Image.new("RGB", (1100, 520), (236, 236, 230))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((25, 25, 1075, 495), radius=24, outline=(40, 40, 40), width=6)
    _draw_lines(image, lines, size=38, top=60, left=70, gap=82)
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def generate(sample_dir: Path, golden_path: Path) -> list[Path]:
    """Write the 8 sample files and the golden set. Returns the sample file paths."""
    outputs: dict[str, bytes] = {
        BRAKE: _text_pdf(BRAKE_PAGES),
        REPORT: _text_pdf(REPORT_PAGES),
        CERT: _scanned_pdf(CERT_LINES),
        LAMP: _spec_sheet_png(LAMP_LINES),
        LABEL: _label_jpg(LABEL_LINES),
        ECN: ECN_TEXT.encode(),
        MANUAL: MANUAL_TEXT.encode(),
        GATE: GATE_TEXT.encode(),
    }
    sample_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, data in outputs.items():
        path = sample_dir / name
        path.write_bytes(data)
        paths.append(path)
    golden_path.parent.mkdir(parents=True, exist_ok=True)
    cases = [c.model_dump(exclude_defaults=True) for c in GOLDEN]
    golden_path.write_text(yaml.safe_dump(cases, sort_keys=False, allow_unicode=True))
    return paths
