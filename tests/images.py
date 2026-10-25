"""Test helpers that draw text into images (no files on disk)."""

import io

from PIL import Image, ImageDraw, ImageFont


def text_image(lines: list[str], fmt: str = "PNG", size: tuple[int, int] = (1000, 400)) -> bytes:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=40)
    for i, line in enumerate(lines):
        draw.text((40, 40 + i * 80), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def squash(text: str) -> str:
    return "".join(text.lower().split())


def text_pdf(pages: list[list[str]]) -> bytes:
    """A PDF with a real text layer, one list of lines per page."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    for lines in pages:
        for i, line in enumerate(lines):
            c.drawString(72, 760 - i * 20, line)
        c.showPage()
    c.save()
    return buf.getvalue()


def table_pdf(rows: list[list[str]]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, invariant=1).build([Table(rows)])
    return buf.getvalue()


def mixed_pdf(text_lines: list[str], scanned_lines: list[str]) -> bytes:
    """Page 1 has a text layer; page 2 is only an image of text (like a scan)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    for i, line in enumerate(text_lines):
        c.drawString(72, 760 - i * 20, line)
    c.showPage()
    image = ImageReader(io.BytesIO(text_image(scanned_lines, size=(1200, 300))))
    c.drawImage(image, 36, 500, width=520, height=130)
    c.showPage()
    c.save()
    return buf.getvalue()
