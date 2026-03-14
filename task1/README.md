# Task 1: Searchable PDF Q&A

## Overview
A Streamlit web app that indexes two AI research papers into a local vector database (ChromaDB) and answers natural language questions using RAG (Retrieval-Augmented Generation) with a free HuggingFace LLM.

## Papers Indexed
- **Paper 1:** [ArXiv 2506.02153](https://arxiv.org/pdf/2506.02153)
- **Paper 2:** [Anthropic Reasoning Models Paper](https://assets.anthropic.com/m/71876fabef0f0ed4/original/reasoning_models_paper.pdf)

## Tech Stack
| Tool | Purpose |
|---|---|
| LangChain | PDF loading, chunking, retrieval pipeline |
| ChromaDB | Local vector database |
| all-MiniLM-L6-v2 | Free HuggingFace embedding model |
| Llama-3.1-8B (HF router) | Free LLM for answer generation |
| Streamlit | Web UI |

## Project Structure
```
task1/
├── app.py              ← Streamlit web interface
├── ingest.py           ← Download PDFs, embed, store in ChromaDB
├── retriever.py        ← Load DB, search chunks, call LLM
├── requirements.txt    ← All dependencies
└── chroma_db/          ← Auto-created after running ingest.py
```

## Setup & Run

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Get a free HuggingFace token
1. Go to [huggingface.co](https://huggingface.co) → Sign up (free)
2. Profile → Settings → Access Tokens → New Token (Read)
3. Copy the token (starts with `hf_...`)

### Step 3 — Index the PDFs (run ONCE)
```bash
python ingest.py
```
This downloads both papers, splits them into 189 chunks, embeds them using MiniLM, and saves to `chroma_db/`. Takes 2–5 minutes on first run.

### Step 4 — Launch the app
```powershell
$env:HF_TOKEN = "your_hf_token_here"
streamlit run app.py
```
App opens at **http://localhost:8501**

## How It Works
```
PDFs (2 papers)
    ↓ PyPDFLoader
Page text extracted
    ↓ RecursiveCharacterTextSplitter (800 chars, 100 overlap)
189 chunks created
    ↓ HuggingFaceEmbeddings (all-MiniLM-L6-v2)
Vector embeddings
    ↓ ChromaDB (persisted locally)
Vector database ready

─── Query time ──────────────────────────────────

User question
    ↓ Embed with same MiniLM model
Question vector
    ↓ Cosine similarity search (top-5 chunks)
Relevant context
    ↓ Llama-3.1-8B via HuggingFace router
Final answer + source chunks + response time
```

## Features
- Natural language question input
- Suggested questions for quick testing
- AI-generated answers grounded in paper content
- Source chunks shown with page numbers and paper names
- Query response time displayed
- DB stats in sidebar (189 chunks indexed)
