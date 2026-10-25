from types import ModuleType

from streamlit.testing.v1 import AppTest

from tests.ui.conftest import page
from tests.ui_fakes import STATUS, FakeApi, down_transport


def run_chat(api_client_module: ModuleType, transport: object) -> AppTest:
    api_client_module.TRANSPORT = transport
    at = AppTest.from_file(page("Home.py"), default_timeout=30)
    return at.run()


def all_text(at: AppTest) -> str:
    elements = [*at.markdown, *at.caption, *at.error, *at.warning, *at.info]
    parts = [e.value for e in elements] + [x.label for x in at.expander]
    return "\n".join(str(p) for p in parts)


def test_fr_062_answer_shows_numbered_citations_with_passage_and_score(
    api_client_module: ModuleType,
) -> None:
    api = FakeApi()
    at = run_chat(api_client_module, api.transport())
    at.chat_input[0].set_value("What is the minimum thickness of the front brake disc?").run()
    assert not at.exception
    text = all_text(at)
    assert "3.5 mm" in text
    labels = [x.label for x in at.expander]
    assert "[1] DM-STD-BRK-001_Brake_System_Design_Standard.pdf · p. 2" in labels
    first = at.expander[0]
    expander_text = "\n".join(str(m.value) for m in [*first.code, *first.caption])
    assert "Front | 276 mm | 3.5 mm" in expander_text and "0.88" in expander_text
    assert api.calls("POST", "/ask") == 1


def test_fr_060_sidebar_shows_retriever_generator_and_top_k(
    api_client_module: ModuleType,
) -> None:
    api = FakeApi()
    at = run_chat(api_client_module, api.transport())
    sidebar = "\n".join(str(m.value) for m in [*at.sidebar.markdown, *at.sidebar.caption])
    assert "vector" in sidebar and "extractive" in sidebar
    slider = at.sidebar.slider[0]
    assert (slider.value, slider.min, slider.max) == (4, 1, 10)
    slider.set_value(7).run()
    at.chat_input[0].set_value("What brake fluid?").run()
    assert b'"top_k":7' in api.requests[-1].read()


def test_fr_054_cloud_notice_is_shown(api_client_module: ModuleType) -> None:
    notice = "Cloud generator active: each question and its retrieved passages are sent to OpenAI"
    api = FakeApi()
    api.routes[("GET", "/status")] = (200, {**STATUS, "generator": "openai", "notices": [notice]})
    at = run_chat(api_client_module, api.transport())
    assert any(notice in str(w.value) for w in at.sidebar.warning)


def test_fr_064_api_down_shows_banner_with_url(api_client_module: ModuleType) -> None:
    at = run_chat(api_client_module, down_transport())
    assert not at.exception
    assert any("not reachable at http://localhost:8000" in str(e.value) for e in at.error)


def test_refusal_is_shown_without_citations(api_client_module: ModuleType) -> None:
    api = FakeApi()
    api.routes[("POST", "/ask")] = (200, {
        "answer": "I couldn't find this in the uploaded documents.", "grounded": False,
        "citations": [], "retriever": "vector", "generator_used": "none",
        "fallback_reason": None, "latency_ms": 3.0})
    at = run_chat(api_client_module, api.transport())
    at.chat_input[0].set_value("What is the top speed?").run()
    assert "I couldn't find this" in all_text(at)
    assert at.expander == [] or all(not x.label.startswith("[") for x in at.expander)
