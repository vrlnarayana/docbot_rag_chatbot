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
