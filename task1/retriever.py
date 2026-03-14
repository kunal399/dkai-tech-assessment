# ============================================================
# retriever.py
# Loads ChromaDB → retrieves relevant chunks →
# generates answer using HuggingFace router (OpenAI-compatible)
# ============================================================

import os
import time

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
CHROMA_DIR      = "./chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K           = 5

# Free model on HuggingFace router
HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct:cerebras"


# ─────────────────────────────────────────────────────────────
# Load vector store from disk
# ─────────────────────────────────────────────────────────────
def load_vectorstore():
    embeddings = HuggingFaceEmbeddings(
        model_name    = EMBEDDING_MODEL,
        model_kwargs  = {"device": "cpu"},
        encode_kwargs = {"normalize_embeddings": True},
    )
    vectorstore = Chroma(
        persist_directory  = CHROMA_DIR,
        embedding_function = embeddings,
    )
    return vectorstore


# ─────────────────────────────────────────────────────────────
# Core query function
# ─────────────────────────────────────────────────────────────
def answer_question(vectorstore, question: str) -> dict:
    start = time.perf_counter()

    # Retrieve top-5 relevant chunks
    retriever   = vectorstore.as_retriever(
        search_type   = "similarity",
        search_kwargs = {"k": TOP_K},
    )
    source_docs = retriever.invoke(question)

    # Generate answer
    hf_token = os.getenv("HF_TOKEN", "")

    if hf_token:
        answer, used_llm = _answer_with_hf(question, source_docs, hf_token)
    else:
        answer   = _chunks_as_answer(source_docs)
        used_llm = False

    elapsed = time.perf_counter() - start

    return {
        "answer"     : answer,
        "source_docs": source_docs,
        "elapsed"    : elapsed,
        "used_llm"   : used_llm,
    }


# ─────────────────────────────────────────────────────────────
# HuggingFace router via OpenAI-compatible client
# ─────────────────────────────────────────────────────────────
def _answer_with_hf(question: str, docs: list, hf_token: str):
    try:
        from openai import OpenAI

        # Build context from ALL 5 chunks with 600 chars each
        # More context = better and more accurate answers
        context_parts = []
        for d in docs[:5]:
            page   = d.metadata.get("page", "?")
            source = d.metadata.get("source", "")
            text   = d.page_content[:600].replace("\n", " ")
            context_parts.append(f"[Page {page} | {source}]: {text}")
        context = "\n\n".join(context_parts)

        # Use OpenAI client pointed at HuggingFace router
        client = OpenAI(
            base_url = "https://router.huggingface.co/v1",
            api_key  = hf_token,
        )

        response = client.chat.completions.create(
            model    = HF_MODEL,
            messages = [
                {
                    "role"   : "system",
                    "content": (
                        "You are a research assistant helping users understand "
                        "academic papers. Answer the question using the provided "
                        "context from the papers. Give a detailed and informative "
                        "answer. If the context does not contain enough information "
                        "to answer fully, use what is available and mention what "
                        "could not be found."
                    ),
                },
                {
                    "role"   : "user",
                    "content": f"CONTEXT FROM PAPERS:\n{context}\n\nQUESTION:\n{question}",
                },
            ],
            max_tokens  = 600,
            temperature = 0.3,
        )

        answer = response.choices[0].message.content.strip()
        return answer, True

    except Exception as e:
        error_msg = str(e)
        if "loading" in error_msg.lower() or "503" in error_msg:
            return (
                "⏳ Model is loading on HuggingFace servers. "
                "Please wait 20 seconds and try again.",
                False
            )
        return (
            f"❌ Error: {error_msg}\n\n"
            f"Showing retrieved chunks instead:\n\n{_chunks_as_answer(docs)}",
            False
        )


# ─────────────────────────────────────────────────────────────
# Fallback — show raw chunks when no LLM available
# ─────────────────────────────────────────────────────────────
def _chunks_as_answer(docs: list) -> str:
    lines = []
    for i, doc in enumerate(docs, 1):
        page   = doc.metadata.get("page", "?")
        source = doc.metadata.get("source", "")
        lines.append(
            f"**📄 Passage {i} — Page {page} | {source}:**\n\n{doc.page_content}\n"
        )
    return "\n---\n".join(lines)