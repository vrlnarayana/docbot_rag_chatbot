from types import ModuleType

from streamlit.testing.v1 import AppTest

from tests.ui.conftest import page
from tests.ui_fakes import STATUS, FakeApi, down_transport


def run_status(api_client_module: ModuleType, api: FakeApi) -> AppTest:
    api_client_module.TRANSPORT = api.transport()
    return AppTest.from_file(page("pages/3_Status.py"), default_timeout=30).run()


def text_of(at: AppTest) -> str:
    elements = [*at.markdown, *at.caption, *at.warning, *at.info, *at.code]
    return "\n".join(str(e.value) for e in elements) + "\n".join(
        f"{m.label}={m.value}" for m in at.metric)


def test_fr_051_shows_active_configuration_and_counts(api_client_module: ModuleType) -> None:
    at = run_status(api_client_module, FakeApi())
    assert not at.exception
    text = text_of(at)
    assert "Retriever=vector" in text and "Generator=extractive" in text
    assert "Documents=1" in text and "Chunks=3" in text
    assert "BAAI/bge-small-en-v1.5" in text
    assert "DOCBOT_RETRIEVER" in text and "DOCBOT_GENERATOR" in text  # how to switch


def test_fr_054_fallbacks_and_cloud_notices_are_highlighted(
    api_client_module: ModuleType,
) -> None:
    api = FakeApi()
    api.routes[("GET", "/status")] = (200, {
        **STATUS, "retriever": "keyword", "generator": "anthropic", "embed_model": None,
        "fallbacks": ["Embedding model could not be loaded; using the keyword retriever."],
        "notices": ["Cloud generator active: questions are sent to Anthropic."]})
    at = run_status(api_client_module, api)
    assert any("keyword retriever" in str(w.value) for w in at.warning)
    assert any("Anthropic" in str(w.value) for w in at.warning)


def test_fr_064_api_down(api_client_module: ModuleType) -> None:
    api_client_module.TRANSPORT = down_transport()
    at = AppTest.from_file(page("pages/3_Status.py"), default_timeout=30).run()
    assert not at.exception and any("not reachable" in str(e.value) for e in at.error)
