from app.adapters.extractors import TextFileExtractor


def test_fr_006_utf8_text_is_page_one() -> None:
    pages = TextFileExtractor().extract("Sprocket 42T → 43T\nline 2".encode(), ".txt")
    assert len(pages) == 1
    assert pages[0].number == 1 and pages[0].source == "text"
    assert pages[0].text == "Sprocket 42T → 43T\nline 2"


def test_fr_006_falls_back_to_latin1() -> None:
    pages = TextFileExtractor().extract("Température 25 °C".encode("latin-1"), ".md")
    assert pages[0].text == "Température 25 °C"


def test_fr_006_strips_utf8_bom() -> None:
    pages = TextFileExtractor().extract("﻿# Manual".encode(), ".md")
    assert pages[0].text == "# Manual"
