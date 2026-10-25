"""Status page: what the API is running with, and how to change it (FR-060, FR-051, FR-054)."""

import streamlit as st
from api_client import ApiUnavailable, api_down_banner, client

st.set_page_config(page_title="DocBot · Status", page_icon="🩺", layout="wide")
st.title("🩺 Status")

try:
    status = client().status()
except ApiUnavailable as exc:
    api_down_banner(exc)
    st.stop()

for fallback in status["fallbacks"]:
    st.warning(fallback, icon="⚠️")
for notice in status["notices"]:
    st.warning(notice, icon="☁️")

retriever, generator, documents, chunks = st.columns(4)
retriever.metric("Retriever", status["retriever"])
generator.metric("Generator", status["generator"])
documents.metric("Documents", status["documents"])
chunks.metric("Chunks", status["chunks"])
st.markdown(f"**Embedding model:** {status['embed_model'] or 'not used (keyword retriever)'}")

st.subheader("Change the configuration")
st.markdown(
    "Set these in the `.env` file next to `pyproject.toml`, then restart the API "
    "(`uvicorn app.api.main:app --port 8000`)."
)
st.code(
    "DOCBOT_RETRIEVER=vector        # or keyword (no model download)\n"
    "DOCBOT_GENERATOR=extractive    # or ollama, openai, anthropic\n"
    "DOCBOT_OLLAMA_MODEL=llama3.2:3b\n"
    "DOCBOT_OPENAI_API_KEY=sk-...   # only for DOCBOT_GENERATOR=openai\n"
    "DOCBOT_ANTHROPIC_API_KEY=...   # only for DOCBOT_GENERATOR=anthropic\n"
    "DOCBOT_TOP_K=4\n"
    "DOCBOT_MIN_COVERAGE=0.55       # raise it if out-of-scope questions get answered",
    language="bash",
)
st.caption(
    "openai and anthropic send each question and its retrieved passages to that provider. "
    "Every other setting keeps your documents on this machine."
)
