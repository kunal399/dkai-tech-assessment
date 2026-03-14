# ============================================================
# ingest.py
# STEP 1 of Task 1: Download PDFs → Extract text → Chunk →
#                   Embed → Store in ChromaDB
#
# Run this ONCE before launching the Streamlit app.
# Usage: python ingest.py
# ============================================================

import os
import requests
import tempfile

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

# The two papers we need to index
PDF_URLS = [
    "https://arxiv.org/pdf/2506.02153",
    "https://assets.anthropic.com/m/71876fabef0f0ed4/original/reasoning_models_paper.pdf",
]

# ChromaDB will persist here (folder created automatically)
CHROMA_DIR = "./chroma_db"

# Free embedding model from HuggingFace — no API key needed
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunk settings:
#   chunk_size  = max characters per chunk
#   chunk_overlap = characters shared between adjacent chunks
#                   (helps preserve context at boundaries)
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100


# ─────────────────────────────────────────────────────────────
# STEP 1: Download each PDF and save to a temp file
# ─────────────────────────────────────────────────────────────
def download_pdf(url: str) -> str:
    """
    Downloads a PDF from a URL and saves it to a temp file.
    Returns the temp file path.
    """
    print(f"  Downloading: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}   # Some servers block plain requests
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()               # Crash loudly if download fails

    # Write bytes to a temp .pdf file
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(response.content)
    tmp.close()
    print(f"  Saved to:    {tmp.name}  ({len(response.content)//1024} KB)")
    return tmp.name


# ─────────────────────────────────────────────────────────────
# STEP 2: Extract text from each PDF page using PyPDFLoader
# ─────────────────────────────────────────────────────────────
def load_pdf(path: str, url: str = "") -> list:
    """
    Loads a PDF from disk and returns a list of Document objects.
    Each Document = one page, with page number in metadata.
    """
    loader = PyPDFLoader(path)
    pages = loader.load()
    paper_name = "Reasoning Models Paper" if "anthropic" in url else "ArXiv Paper 2506.02153"
    for page in pages:
        page.metadata["source"] = paper_name
    print(f"  Extracted {len(pages)} pages")
    return pages


# ─────────────────────────────────────────────────────────────
# STEP 3: Split pages into smaller chunks
# ─────────────────────────────────────────────────────────────
def split_documents(documents: list) -> list:
    """
    Splits large page-documents into smaller overlapping chunks.

    Why? Embedding models have a token limit (~512 tokens).
    Smaller chunks also improve retrieval precision — you get
    exactly the paragraph that answers the question, not the
    whole page.

    RecursiveCharacterTextSplitter tries to split on:
      1. Double newlines (paragraph breaks) — preferred
      2. Single newlines
      3. Periods
      4. Spaces
      5. Individual characters (last resort)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = CHUNK_SIZE,
        chunk_overlap = CHUNK_OVERLAP,
        separators    = ["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"  Created {len(chunks)} chunks from {len(documents)} pages")
    return chunks


# ─────────────────────────────────────────────────────────────
# STEP 4: Create embeddings and store in ChromaDB
# ─────────────────────────────────────────────────────────────
def build_vectorstore(chunks: list):
    """
    Converts each chunk into a vector embedding and stores it
    in a local ChromaDB database.

    What is an embedding?
    A list of ~384 numbers that represent the semantic meaning
    of the text. Chunks with similar meaning have embeddings
    that are "close" in vector space — this is what makes
    similarity search work.

    all-MiniLM-L6-v2:
    - Small model (80MB), runs on CPU in seconds
    - Good quality for English documents
    - No API key needed
    """
    print(f"\n[3/3] Embedding {len(chunks)} chunks with '{EMBEDDING_MODEL}'...")
    print("      (First run downloads the model ~80MB — wait a moment)")

    embeddings = HuggingFaceEmbeddings(
        model_name      = EMBEDDING_MODEL,
        model_kwargs    = {"device": "cpu"},   # use "cuda" if you have a GPU
        encode_kwargs   = {"normalize_embeddings": True},
    )

    # Chroma.from_documents():
    #   1. Calls embeddings.embed_documents() on all chunks
    #   2. Stores (chunk_text, embedding, metadata) in ChromaDB
    #   3. persist_directory saves it to disk so we don't re-index
    vectorstore = Chroma.from_documents(
        documents         = chunks,
        embedding         = embeddings,
        persist_directory = CHROMA_DIR,
    )
    
    print(f"  Vectorstore saved to '{CHROMA_DIR}/'")
    return vectorstore


# ─────────────────────────────────────────────────────────────
# MAIN — run everything in sequence
# ─────────────────────────────────────────────────────────────
def main():
    # Guard: skip if DB already exists
    if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        print(f"ChromaDB already exists at '{CHROMA_DIR}/'")
        print("Delete that folder and re-run if you want to re-index.")
        return

    all_documents = []

    print("=" * 55)
    print("TASK 1 — Ingestion Pipeline")
    print("=" * 55)

    for i, url in enumerate(PDF_URLS, 1):
        print(f"\n[PDF {i}/{len(PDF_URLS)}]")

        # Download
        print("[1/3] Downloading PDF...")
        tmp_path = download_pdf(url)

        # Extract
        print("[2/3] Extracting text...")
        pages = load_pdf(tmp_path, url)
        all_documents.extend(pages)

        # Clean up temp file
        os.unlink(tmp_path)

    # Split ALL pages together so the DB has both papers
    print(f"\n[Splitting] Total pages loaded: {len(all_documents)}")
    chunks = split_documents(all_documents)

    # Embed + store
    build_vectorstore(chunks)

    print("\n✅ Ingestion complete! Now run:  streamlit run app.py")


if __name__ == "__main__":
    main()