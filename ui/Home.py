"""DocBot chat page (FR-060, FR-062, FR-070 to FR-073). Run with `streamlit run ui/Home.py`."""

from typing import Any

import streamlit as st
from api_client import ApiError, ApiUnavailable, api_down_banner, client
from markdown_safe import inline, plain

st.set_page_config(page_title="DocBot · Chat", page_icon="💬", layout="wide")

MAX_TURNS = 6  # FR-073: the API keeps no conversation; we send the most recent turns
MAX_TURN_CHARS = 2000


def recent_turns(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    turns = []
    for message in messages:
        text = message["content"] if message["role"] == "user" else message["content"]["answer"]
        turns.append({"role": message["role"], "content": text[:MAX_TURN_CHARS]})
    return turns[-MAX_TURNS:]


def show_answer(reply: dict[str, Any]) -> None:
    if reply.get("small_talk"):
        st.markdown(plain(reply["answer"]))
        return
    if reply.get("standalone_question"):
        st.caption(f"🔎 Searched for: {plain(reply['standalone_question'])}")
    if not reply["grounded"]:
        st.info(reply["answer"], icon="🔎")
    else:
        st.markdown(plain(reply["answer"]))
    for c in reply["citations"]:
        with st.expander(f"[{c['n']}] {inline(c['filename'])} · p. {c['page']}"):
            st.code(c["passage"], language=None, wrap_lines=True)
            st.caption(f"Retrieval score {c['score']:.2f}")
    meta = f"{reply['generator_used']} generator · {reply['retriever']} retriever"
    st.caption(f"{meta} · {reply['latency_ms']:.0f} ms")
    if reply.get("fallback_reason"):
        st.caption(f"⚠️ Fell back to the extractive generator: {reply['fallback_reason']}")


st.title("💬 DocBot")
st.caption("Ask about your documents. Every answer cites the file and page it came from.")

api = client()
try:
    status = api.status()
except ApiUnavailable as exc:
    api_down_banner(exc)
    st.stop()

with st.sidebar:
    st.markdown(f"**Retriever:** {status['retriever']}")
    st.markdown(f"**Generator:** {status['generator']}")
    st.caption(f"{status['documents']} documents · {status['chunks']} chunks indexed")
    for notice in status["notices"]:
        st.warning(notice, icon="☁️")
    for fallback in status["fallbacks"]:
        st.info(fallback)
    top_k = st.slider("Passages to retrieve (top k)", min_value=1, max_value=10, value=4)
    if st.button("Clear chat"):
        st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(plain(message["content"]))
        else:
            show_answer(message["content"])

if question := st.chat_input("Ask a question about your documents…"):
    history = recent_turns(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(plain(question))
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the documents…"):
                reply = api.ask(question, top_k, history)
        except ApiUnavailable as exc:
            api_down_banner(exc)
        except ApiError as exc:
            st.error(exc.message)
        else:
            show_answer(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
