# RAG POC — Retrieval-Augmented Generation with Ollama

A fully local RAG proof-of-concept. No cloud APIs. Everything runs on your machine via Ollama.

---

## What is RAG?

**Retrieval-Augmented Generation** lets an LLM answer questions *from your documents* rather than just its training data:

```
Your Question
     │
     ▼
[Embed question]  ──►  ChromaDB similarity search  ──►  Top-K relevant chunks
                                                              │
                                                              ▼
                                                   [Augmented Prompt = chunks + question]
                                                              │
                                                              ▼
                                                     Ollama LLM (llama3.2)
                                                              │
                                                              ▼
                                                         Grounded Answer
```

---

## Tech Stack

| Component      | Tool                         |
|----------------|------------------------------|
| LLM            | `llama3.2:latest` via Ollama |
| Embeddings     | `nomic-embed-text` via Ollama|
| Vector Store   | ChromaDB (local, persistent) |
| Chunking       | LangChain RecursiveTextSplitter |
| UI             | Streamlit                    |
| Doc loaders    | LangChain (PDF, TXT, MD)     |

---

## Setup

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running

### 2. Pull the embedding model

```bash
ollama pull nomic-embed-text
```

### 3. Create a virtual environment and install dependencies

```bash
# Create venv using Python 3.12 (Homebrew)
/opt/homebrew/bin/python3.12 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Step 1 — Add your documents

Drop any `.pdf`, `.txt`, or `.md` files into the `data/` folder.
You can use subdirectories — the ingestion script scans recursively.

```
data/
├── report.pdf
├── notes.txt
└── subfolder/
    └── manual.pdf
```

### Step 2 — Ingest the documents

```bash
# Make sure your venv is active: source .venv/bin/activate
python ingest.py
```

Output example:
```
RAG Document Ingestion
Found 3 file(s) in ./data

  File          Status      Chunks
  report.pdf    ✓ added     42
  notes.txt     ✓ added     11
  manual.pdf    – skipped   88   ← already up-to-date

Done. 2 added  0 updated  1 skipped  0 errors  │  141 total chunks in knowledge base
```

> Re-run `python ingest.py` any time you add, change, or remove files.
> Unchanged files are detected by hash and skipped automatically.

**Options:**
```bash
python ingest.py --clear          # Wipe the KB first, then re-ingest everything
python ingest.py --data-dir /path/to/other/folder  # Use a custom folder
```

### Step 3 — Start the app

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

Then open http://localhost:8501 in your browser.

---

## Project Structure

```
RAG-POC/
├── app.py           # Streamlit UI
├── ingest.py        # CLI ingestion script
├── rag/
│   ├── ingestion.py # File loading, chunking, embedding, ChromaDB storage
│   ├── retriever.py # Similarity search
│   ├── generator.py # Prompt building + Ollama LLM call
│   └── pipeline.py  # Combines retriever + generator
├── data/            # ← Put your PDFs / TXTs / MDs here
├── chroma_db/       # Auto-created vector store (persisted)
└── requirements.txt
```

---

## UI Features

- **Upload documents** directly in the sidebar (one-off files)
- **Ask questions** with a live streaming answer
- **See every pipeline step** transparently:
  - Retrieved chunks with similarity scores and source filenames
  - The full augmented prompt sent to the LLM
  - Streamed LLM response token-by-token
- **Session history** — all queries in the current session, each with answer, chunks, and prompt
- **Adjust Top-K** — control how many chunks are retrieved per query
- **Clear knowledge base** or **chat history** with one click
