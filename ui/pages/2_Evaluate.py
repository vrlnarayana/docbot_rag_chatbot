"""Evaluate page: run the golden question set and show the scores (FR-060, FR-040, FR-041)."""

import streamlit as st
from api_client import ApiError, ApiUnavailable, api_down_banner, client

st.set_page_config(page_title="DocBot · Evaluate", page_icon="📊", layout="wide")
st.title("📊 Evaluate")
st.caption(
    "Asks every question in eval/golden.yaml and checks whether the right document was "
    "retrieved, the answer contains the expected fact, and out-of-scope questions are refused."
)


def mark(flag: bool, applies: bool = True) -> str:
    return ("✅" if flag else "❌") if applies else "—"


top_k = st.slider("Passages to retrieve (top k)", min_value=1, max_value=10, value=4)
if st.button("Run evaluation", type="primary"):
    try:
        with st.spinner("Asking the golden questions…"):
            st.session_state.eval_run = client().run_eval(top_k)
    except ApiUnavailable as exc:
        api_down_banner(exc)
    except ApiError as exc:
        st.warning(exc.message)

run = st.session_state.get("eval_run")
if run:
    s = run["summary"]
    hit, accuracy, refusal = st.columns(3)
    hit.metric(f"Hit rate @ {s['top_k']}", f"{s['hit_rate_at_k']:.1f}%")
    accuracy.metric("Answer accuracy", f"{s['answer_accuracy']:.1f}%")
    refusal.metric("Refusal accuracy", f"{s['refusal_accuracy']:.1f}%")
    st.caption(
        f"{s['cases']} questions · {s['retriever']} retriever · {s['generator']} generator. "
        "Switch DOCBOT_RETRIEVER in .env and run again to compare."
    )
    st.dataframe(
        [
            {
                "Question": r["question"],
                "Expected": r["expected_file"] or "(refusal)",
                "Retrieved": ", ".join(r["retrieved_files"]),
                "Hit": mark(r["hit"], not r["expect_refusal"]),
                "Fact found": mark(r["fact_found"], not r["expect_refusal"]),
                "Refusal correct": mark(r["refusal_correct"]),
            }
            for r in run["results"]
        ],
        hide_index=True,
        width="stretch",
    )
