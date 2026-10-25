"""Documents page: upload, load the samples, inspect chunks, delete (FR-060, FR-063)."""

import streamlit as st
from api_client import ApiError, ApiUnavailable, api_down_banner, client
from markdown_safe import inline

st.set_page_config(page_title="DocBot · Documents", page_icon="📄", layout="wide")
st.title("📄 Documents")

api = client()
flash = st.session_state.pop("flash", None)
if flash:
    kind, text = flash
    getattr(st, kind)(text)

try:
    with st.container(border=True):
        st.markdown("**Add documents**")
        files = st.file_uploader(
            "PDF, PNG, JPG, TXT or MD files",
            type=["pdf", "png", "jpg", "jpeg", "txt", "md"],
            accept_multiple_files=True,
        )
        left, right = st.columns(2)
        if left.button("Upload and index", disabled=not files, type="primary"):
            for f in files or []:
                try:
                    with st.spinner(f"Indexing {f.name}…"):
                        result = api.upload(f.name, f.getvalue())
                except ApiError as exc:
                    st.error(f"{inline(f.name)}: {exc.message}")
                else:
                    if result["duplicate"]:
                        st.info(f"{inline(f.name)}: already in the library.")
                    else:
                        doc = result["document"]
                        st.success(f"{inline(f.name)}: indexed ({doc['chunk_count']} chunks).")
        if right.button("Generate & load sample documents"):
            with st.spinner("Generating and indexing the sample set…"):
                loaded = api.load_samples()
            st.success(
                f"Sample set: {loaded['indexed']} indexed, "
                f"{loaded['duplicates']} already in the library."
            )
            for failed in loaded["failed"]:
                st.warning(f"{inline(failed['filename'])}: {failed['reason']}")

    documents = api.documents()
except ApiUnavailable as exc:
    api_down_banner(exc)
    st.stop()

if not documents:
    st.info("No documents yet. Upload files above, or load the sample set.")
    st.stop()

st.dataframe(
    [
        {
            "File": d["filename"],
            "Type": d["doc_type"],
            "Pages": d["page_count"],
            "OCR pages": d["ocr_page_count"],
            "Chunks": d["chunk_count"],
            "Size (KB)": round(d["size_bytes"] / 1024, 1),
            "Uploaded": d["created_at"][:19].replace("T", " "),
        }
        for d in documents
    ],
    hide_index=True,
    width="stretch",
)

st.subheader("Inspect a document")
by_id = {d["id"]: d for d in documents}
selected = st.selectbox(
    "Document", options=list(by_id), format_func=lambda doc_id: by_id[doc_id]["filename"]
)
document = by_id[selected]

if st.session_state.get("pending_delete") == selected:
    st.warning(f"Delete **{inline(document['filename'])}** and its chunks? This cannot be undone.")
    yes, no = st.columns(2)
    if yes.button("Yes, delete", type="primary"):
        try:
            api.delete(selected)
        except (ApiError, ApiUnavailable) as exc:
            st.session_state.flash = ("error", str(exc))
        else:
            st.session_state.flash = ("success", f"Deleted {inline(document['filename'])}.")
        st.session_state.pop("pending_delete", None)
        st.rerun()
    if no.button("Cancel"):
        st.session_state.pop("pending_delete", None)
        st.rerun()
elif st.button("Delete this document"):
    st.session_state.pending_delete = selected  # FR-063: confirm before calling the API
    st.rerun()

try:
    chunks = api.chunks(selected)
except (ApiError, ApiUnavailable) as exc:
    st.error(str(exc))
    st.stop()

st.caption(f"{len(chunks)} chunks, in page order")
for chunk in chunks:
    st.markdown(f"**p. {chunk['page']}** · {chunk['source']} · chunk {chunk['ordinal'] + 1}")
    st.code(chunk["text"], language=None, wrap_lines=True)
