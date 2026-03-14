# ============================================================
# app.py
# STEP 3 of Task 1: The Streamlit web interface
#
# Run with:  streamlit run app.py
# (Make sure you ran `python ingest.py` first!)
# ============================================================

import os
import streamlit as st

from retriever import load_vectorstore, answer_question

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG — must be the FIRST streamlit call
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "PDF Q&A — Task 1",
    page_icon  = "📄",
    layout     = "wide",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS — makes it look cleaner
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { max-width: 900px; margin: 0 auto; }
    # REPLACE with this
.answer-box {
    background: #1e2a4a;
    border-left: 4px solid #4a6cf7;
    padding: 1rem 1.2rem;
    border-radius: 0 8px 8px 0;
    margin: 1rem 0;
    color: #e8eaf6 !important;
    font-size: 1rem;
    line-height: 1.6;
}
.answer-box p {
    color: #e8eaf6 !important;
}
    .time-badge {
        display: inline-block;
        background: #e8f5e9;
        color: #2e7d32;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 8px;
    }
    # REPLACE with this
.chunk-card {
    background: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    color: #e2e8f0 !important;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
st.title("📄 Searchable PDF Q&A")
st.markdown("""
Ask questions about the two research papers:
- **Paper 1:** arxiv.org/pdf/2506.02153
- **Paper 2:** Anthropic Reasoning Models paper
""")

# Check if API key is set — show warning if not
if not os.getenv("HF_TOKEN"):
    st.warning(
        "⚠️  **No HF_TOKEN found.** "
        "Retrieval works, but answers will show raw chunks instead of AI-generated responses. "
        "Set HF_TOKEN env var to enable AI answers.",
        icon="⚠️",
    )


# ─────────────────────────────────────────────────────────────
# LOAD VECTORSTORE — cached so it only loads once per session
# ─────────────────────────────────────────────────────────────
CHROMA_DIR = "./chroma_db"

@st.cache_resource(show_spinner="Loading vector database...")
def get_vectorstore():
    """
    @st.cache_resource means this runs ONCE and the result is
    reused across all reruns (i.e., every time the user types
    or clicks something). Without this, it would reload the DB
    on every interaction — very slow.
    """
    if not os.path.exists(CHROMA_DIR):
        return None
    return load_vectorstore()

vectorstore = get_vectorstore()

# Show error if ingest hasn't been run yet
if vectorstore is None:
    st.error(
        "❌ ChromaDB not found. Please run `python ingest.py` first to index the PDFs.",
        icon="❌",
    )
    st.stop()   # Stop rendering — nothing else will work without the DB

st.success("✅ Vector database loaded and ready!", icon="✅")
st.divider()


# ─────────────────────────────────────────────────────────────
# QUESTION INPUT
# ─────────────────────────────────────────────────────────────
st.subheader("💬 Ask a Question")

# Suggested questions to help the user get started
SUGGESTIONS = [
    "What are the main findings about reasoning models?",
    "How does chain-of-thought improve model performance?",
    "What datasets were used in the experiments?",
    "What are the key limitations mentioned in the papers?",
]

col1, col2 = st.columns([3, 1])

with col1:
    question = st.text_input(
        label       = "Your question:",
        placeholder = "e.g. What are the key findings about reasoning models?",
        label_visibility = "collapsed",
    )

with col2:
    search_btn = st.button("🔍 Search", use_container_width=True, type="primary")

# Clickable suggestion pills
st.markdown("**Try these:**")
cols = st.columns(len(SUGGESTIONS))
for i, suggestion in enumerate(SUGGESTIONS):
    with cols[i]:
        if st.button(suggestion, key=f"sug_{i}", use_container_width=True):
            question = suggestion   # Override the text input
            search_btn = True       # Trigger search automatically


# ─────────────────────────────────────────────────────────────
# SEARCH + DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────
if search_btn and question.strip():
    st.divider()

    with st.spinner("🔎 Searching and generating answer..."):
        result = answer_question(vectorstore, question)

    # ── ANSWER ────────────────────────────────────────────
    st.subheader("🧠 Answer")

    if result["used_llm"]:
        st.markdown(
            f'<div class="answer-box">{result["answer"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        # Raw chunks fallback
        st.info(result["answer"])

    # Response time badge
    elapsed = result["elapsed"]
    st.markdown(
        f'<div class="time-badge">⏱ Response time: {elapsed:.2f}s</div>',
        unsafe_allow_html=True,
    )

    # ── SOURCE CHUNKS ──────────────────────────────────────
    st.divider()
    st.subheader(f"📚 Context Used ({len(result['source_docs'])} chunks retrieved)")
    st.caption("These are the exact passages from the papers that were used to generate the answer.")

    for i, doc in enumerate(result["source_docs"], 1):
        page   = doc.metadata.get("page", "?")
        source = doc.metadata.get("source", "Unknown paper")

        with st.expander(f"Chunk {i} — Page {page}  |  {os.path.basename(str(source))}"):
            st.markdown(
                f'<div class="chunk-card">{doc.page_content}</div>',
                unsafe_allow_html=True,
            )

elif search_btn and not question.strip():
    st.warning("Please enter a question before searching.")


# ─────────────────────────────────────────────────────────────
# SIDEBAR — info panel
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("ℹ️ How it works")
    st.markdown("""
    **Indexing (run once):**
    1. PDFs are downloaded from URLs
    2. Text is extracted page by page
    3. Pages are split into 800-char chunks
    4. Each chunk is converted to a vector embedding
    5. Embeddings are stored in ChromaDB

    **Query (per question):**
    1. Your question is embedded
    2. Top-5 similar chunks are retrieved
    3. Chunks are passed to Claude as context
    4. Claude generates a grounded answer

    ---
    **Tech stack:**
    - 🔗 LangChain
    - 🗄️ ChromaDB
    - 🤗 MiniLM embeddings
    - 🤖 Claude Haiku (LLM)
    - 🖥️ Streamlit
    """)

    st.divider()
    st.header("📊 DB Stats")
    try:
        count = vectorstore._collection.count()
        st.metric("Total chunks indexed", count)
    except Exception:
        st.write("Stats unavailable")