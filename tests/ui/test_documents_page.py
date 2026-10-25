from types import ModuleType

from streamlit.testing.v1 import AppTest

from tests.ui.conftest import page
from tests.ui_fakes import DOC, FakeApi, down_transport


def run_docs(api_client_module: ModuleType, api: FakeApi) -> AppTest:
    api_client_module.TRANSPORT = api.transport()
    return AppTest.from_file(page("pages/1_Documents.py"), default_timeout=30).run()


def button(at: AppTest, label: str):  # type: ignore[no-untyped-def]
    return next(b for b in at.button if b.label == label)


def test_fr_020_table_lists_documents(api_client_module: ModuleType) -> None:
    at = run_docs(api_client_module, FakeApi())
    assert not at.exception
    table = at.dataframe[0].value
    assert list(table["File"]) == [DOC["filename"]]
    assert {"Type", "Pages", "OCR pages", "Chunks", "Size (KB)", "Uploaded"} <= set(table.columns)


def test_fr_031_load_samples_button(api_client_module: ModuleType) -> None:
    api = FakeApi()
    at = run_docs(api_client_module, api)
    button(at, "Generate & load sample documents").click().run()
    assert api.calls("POST", "/samples/load") == 1
    assert any("8 indexed" in str(s.value) for s in at.success)


def test_fr_021_view_chunks_shows_page_source_and_text(api_client_module: ModuleType) -> None:
    at = run_docs(api_client_module, FakeApi())
    labels = "\n".join(str(m.value) for m in at.markdown)
    assert "p. 2" in labels and "text" in labels
    assert any("Front | 276 mm | 3.5 mm" in str(c.value) for c in at.code)


def test_fr_063_delete_asks_for_confirmation_first(api_client_module: ModuleType) -> None:
    api = FakeApi()
    at = run_docs(api_client_module, api)
    button(at, "Delete this document").click().run()
    assert api.calls("DELETE", "/documents/d1") == 0
    assert any("cannot be undone" in str(w.value) for w in at.warning)

    button(at, "Cancel").click().run()
    assert api.calls("DELETE", "/documents/d1") == 0

    button(at, "Delete this document").click().run()
    button(at, "Yes, delete").click().run()
    assert api.calls("DELETE", "/documents/d1") == 1


def test_empty_library_suggests_samples(api_client_module: ModuleType) -> None:
    api = FakeApi()
    api.routes[("GET", "/documents")] = (200, [])
    at = run_docs(api_client_module, api)
    assert any("sample" in str(i.value).lower() for i in at.info)


def test_fr_064_api_down(api_client_module: ModuleType) -> None:
    api_client_module.TRANSPORT = down_transport()
    at = AppTest.from_file(page("pages/1_Documents.py"), default_timeout=30).run()
    assert not at.exception and any("not reachable" in str(e.value) for e in at.error)
