"""
RAG POC — Streamlit UI

Displays every step of the RAG pipeline transparently:
  1. Retrieved chunks with similarity scores
  2. The full augmented prompt sent to the LLM
  3. The streamed answer from the LLM
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from rag.ingestion import clear_collection, ingest_file, list_ingested_files
from rag.pipeline import rag_stream
from rag.retriever import TOP_K

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RAG POC",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Session state ─────────────────────────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state.history = []  # list of {query, chunks, prompt, answer}

if "top_k" not in st.session_state:
    st.session_state.top_k = TOP_K

# ─── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📚 Knowledge Base")

    # ── Upload files ──
    st.subheader("Upload Documents")
    uploaded_files = st.file_uploader(
        "Drop PDF / TXT / MD files here",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        help="Files are chunked, embedded via Ollama, and stored in ChromaDB.",
    )

    if uploaded_files:
        for uf in uploaded_files:
            suffix = Path(uf.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uf.read())
                tmp_path = tmp.name

            with st.spinner(f"Ingesting {uf.name}…"):
                try:
                    result = ingest_file(tmp_path)
                    # Rename for display since tmp file has a random name
                    from rag.ingestion import _get_chroma_collection

                    col = _get_chroma_collection()
                    # Update metadata source to original filename
                    existing = col.get(
                        where={"source": Path(tmp_path).name}, include=["metadatas", "documents", "embeddings"]
                    )
                    if existing["ids"]:
                        col.delete(ids=existing["ids"])
                        new_metadatas = [
                            {**m, "source": uf.name, "file_path": uf.name}
                            for m in existing["metadatas"]
                        ]
                        col.add(
                            ids=[f"{uf.name}_{i}" for i in range(len(existing["ids"]))],
                            embeddings=existing["embeddings"],
                            documents=existing["documents"],
                            metadatas=new_metadatas,
                        )
                    st.success(f"✓ {uf.name} — {result['chunks']} chunks ({result['status']})")
                except Exception as e:
                    st.error(f"✗ {uf.name}: {e}")

    st.divider()

    # ── Knowledge base status ──
    st.subheader("Ingested Documents")
    ingested = list_ingested_files()
    if ingested:
        for item in ingested:
            st.markdown(f"- **{item['file']}** — `{item['chunks']}` chunks")
    else:
        st.caption("No documents ingested yet. Upload files above or run `python ingest.py`.")

    st.divider()

    # ── Settings ──
    st.subheader("⚙️ Settings")
    st.session_state.top_k = st.slider(
        "Top-K chunks to retrieve",
        min_value=1,
        max_value=10,
        value=st.session_state.top_k,
        help="How many document chunks are retrieved per query.",
    )

    st.divider()

    if st.button("🗑️ Clear Knowledge Base", type="secondary", use_container_width=True):
        clear_collection()
        st.success("Knowledge base cleared.")
        st.rerun()

    if st.button("🧹 Clear Chat History", type="secondary", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ─── Main panel ────────────────────────────────────────────────────────────────

st.title("🔍 RAG POC — Retrieval-Augmented Generation")
st.caption(
    "Ask a question. The system retrieves relevant chunks from your documents, "
    "builds an augmented prompt, and generates a grounded answer using Ollama."
)

# ── How it works explainer (collapsible) ──
with st.expander("ℹ️ How RAG works (click to expand)", expanded=False):
    st.markdown(
        """
**Retrieval-Augmented Generation (RAG)** in 3 steps:

1. **Retrieve** — your question is embedded and compared against document chunks in ChromaDB using cosine similarity. The top-K most relevant chunks are returned.
2. **Augment** — those chunks are injected into the LLM prompt as context.
3. **Generate** — the LLM (Ollama `llama3.2`) reads the augmented prompt and produces a grounded answer.

This means the LLM can only answer from your documents, not its training data.
        """
    )

st.divider()

# ── Query input ──
with st.form("query_form", clear_on_submit=True):
    query = st.text_input(
        "Ask a question about your documents",
        placeholder="e.g. What are the main topics covered in the documents?",
    )
    submitted = st.form_submit_button("Ask", type="primary", use_container_width=True)

# ── Process query ──
if submitted and query.strip():
    ingested = list_ingested_files()
    if not ingested:
        st.warning("No documents in the knowledge base. Upload files in the sidebar or run `python ingest.py`.")
    else:
        with st.spinner("Retrieving relevant chunks…"):
            pipeline_result = rag_stream(query.strip(), top_k=st.session_state.top_k)

        chunks = pipeline_result["chunks"]
        augmented_prompt = pipeline_result["augmented_prompt"]
        answer_stream = pipeline_result["stream"]

        # ── Step 1: Retrieved chunks ──
        st.subheader("Step 1 — Retrieved Chunks")
        if chunks:
            cols = st.columns(min(len(chunks), 2))
            for i, chunk in enumerate(chunks):
                with cols[i % 2]:
                    similarity_color = (
                        "🟢" if chunk["similarity"] >= 70 else "🟡" if chunk["similarity"] >= 40 else "🔴"
                    )
                    with st.container(border=True):
                        st.markdown(
                            f"{similarity_color} **{chunk['source']}** "
                            f"· page {chunk['page']} · chunk #{chunk['chunk_index']}"
                        )
                        st.progress(chunk["similarity"] / 100, text=f"Similarity: {chunk['similarity']}%")
                        st.caption(chunk["text"])
        else:
            st.info("No chunks retrieved — the knowledge base may be empty.")

        st.divider()

        # ── Step 2: Augmented prompt ──
        st.subheader("Step 2 — Augmented Prompt Sent to LLM")
        with st.expander("View full prompt", expanded=False):
            st.code(augmented_prompt, language="markdown")

        st.divider()

        # ── Step 3: Streamed answer ──
        st.subheader("Step 3 — LLM Answer (streaming)")
        answer_placeholder = st.empty()
        full_answer = ""
        for token in answer_stream:
            full_answer += token
            answer_placeholder.markdown(full_answer + "▌")
        answer_placeholder.markdown(full_answer)

        # Save to history
        st.session_state.history.append(
            {
                "query": query.strip(),
                "chunks": chunks,
                "augmented_prompt": augmented_prompt,
                "answer": full_answer,
            }
        )

# ── Query history ──
if st.session_state.history:
    st.divider()
    st.subheader("📜 Session History")
    for i, entry in enumerate(reversed(st.session_state.history[:-1] if submitted and query.strip() else st.session_state.history), 1):
        with st.expander(f"Q{len(st.session_state.history) - i + 1}: {entry['query']}", expanded=False):
            tabs = st.tabs(["Answer", "Retrieved Chunks", "Augmented Prompt"])

            with tabs[0]:
                st.markdown(entry["answer"])

            with tabs[1]:
                for j, chunk in enumerate(entry["chunks"], 1):
                    st.markdown(
                        f"**{j}. {chunk['source']}** · page {chunk['page']} · similarity {chunk['similarity']}%"
                    )
                    st.caption(chunk["text"])
                    if j < len(entry["chunks"]):
                        st.markdown("---")

            with tabs[2]:
                st.code(entry["augmented_prompt"], language="markdown")
