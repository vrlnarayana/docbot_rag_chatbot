from app.core.errors import (
    SUPPORTED_EXTENSIONS,
    DocBotError,
    DocumentNotFound,
    ExtractionFailed,
    FileTooLarge,
    NoTextExtracted,
    UnsupportedFileType,
)


def test_fr_002_unsupported_type_message_lists_supported_types() -> None:
    err = UnsupportedFileType(".docx")
    assert err.code == "unsupported_type"
    for ext in (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"):
        assert ext in err.message
    assert ".docx" in err.message


def test_fr_001_supported_extensions() -> None:
    assert set(SUPPORTED_EXTENSIONS) == {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}


def test_errors_have_codes_and_actionable_messages() -> None:
    errors: list[DocBotError] = [
        FileTooLarge(20),
        NoTextExtracted(),
        ExtractionFailed("encrypted"),
        DocumentNotFound("abc"),
    ]
    codes = {e.code for e in errors}
    assert codes == {"too_large", "no_text", "extraction_failed", "not_found"}
    assert all(e.message for e in errors)
    assert "20 MB" in FileTooLarge(20).message
