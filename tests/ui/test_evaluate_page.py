from types import ModuleType

from streamlit.testing.v1 import AppTest

from tests.ui.conftest import page
from tests.ui_fakes import FakeApi, down_transport


def run_eval_page(api_client_module: ModuleType, api: FakeApi) -> AppTest:
    api_client_module.TRANSPORT = api.transport()
    return AppTest.from_file(page("pages/2_Evaluate.py"), default_timeout=30).run()


def test_fr_041_run_shows_metrics_and_per_case_table(api_client_module: ModuleType) -> None:
    api = FakeApi()
    at = run_eval_page(api_client_module, api)
    at.slider[0].set_value(5).run()
    at.button[0].click().run()
    assert not at.exception
    assert b'"top_k":5' in api.requests[-1].read()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics == {"Hit rate @ 4": "100.0%", "Answer accuracy": "50.0%",
                       "Refusal accuracy": "100.0%"}
    table = at.dataframe[0].value
    assert list(table["Question"]) == ["What is the minimum thickness?", "What is the top speed?"]
    assert set(table["Hit"]) <= {"✅", "❌", "—"}
    assert list(table["Refusal correct"]) == ["✅", "✅"]
    assert any("vector" in str(c.value) and "extractive" in str(c.value) for c in at.caption)


def test_fr_040_empty_library_message(api_client_module: ModuleType) -> None:
    api = FakeApi()
    api.routes[("POST", "/eval/run")] = (409, {
        "code": "no_documents", "message": "No documents are indexed yet. Load the sample set."})
    at = run_eval_page(api_client_module, api)
    at.button[0].click().run()
    assert any("Load the sample set" in str(w.value) for w in at.warning)


def test_fr_064_api_down(api_client_module: ModuleType) -> None:
    api_client_module.TRANSPORT = down_transport()
    at = AppTest.from_file(page("pages/2_Evaluate.py"), default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception and any("not reachable" in str(e.value) for e in at.error)
