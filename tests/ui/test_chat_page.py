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


def test_fr_073_follow_up_sends_recent_turns(api_client_module: ModuleType) -> None:
    import json

    api = FakeApi()
    at = run_chat(api_client_module, api.transport())
    for i in range(5):
        at.chat_input[0].set_value(f"question number {i}").run()
    asks = [json.loads(r.read()) for r in api.requests if r.url.path == "/ask"]
    sent = asks[-1]
    assert sent["question"] == "question number 4"
    history = sent["history"]
    assert len(history) == 6  # at most the last 6 turns
    assert history[-2] == {"role": "user", "content": "question number 3"}
    assert history[-1]["role"] == "assistant" and "3.5 mm" in history[-1]["content"]
    assert "history" not in asks[0]  # nothing to send with the first question


def test_fr_070_rewritten_follow_up_is_shown(api_client_module: ModuleType) -> None:
    from tests.ui_fakes import ANSWER

    api = FakeApi()
    api.routes[("POST", "/ask")] = (200, {**ANSWER, "standalone_question":
                                          "What is the minimum thickness of the rear brake disc?"})
    at = run_chat(api_client_module, api.transport())
    at.chat_input[0].set_value("and the rear one?").run()
    assert any("Searched for: What is the minimum thickness of the rear brake disc?"
               in str(c.value) for c in at.caption)


def test_fr_071_small_talk_is_a_normal_message(api_client_module: ModuleType) -> None:
    api = FakeApi()
    api.routes[("POST", "/ask")] = (200, {
        "answer": "Hi! I'm DocBot.", "grounded": False, "citations": [], "retriever": "vector",
        "generator_used": "none", "fallback_reason": None, "latency_ms": 0.1,
        "standalone_question": None, "small_talk": True})
    at = run_chat(api_client_module, api.transport())
    at.chat_input[0].set_value("hi").run()
    assert any("Hi! I'm DocBot." in str(m.value) for m in at.markdown)
    assert not any("Hi! I'm DocBot." in str(i.value) for i in at.info)
