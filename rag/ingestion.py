"""
Ingestion module: load a file, chunk it, embed via Ollama, store in ChromaDB.

Supported file types: .pdf, .txt, .md
Already-ingested files are detected via a SHA-256 hash stored in metadata,
so re-running ingest.py on unchanged files is a no-op.
"""

import hashlib
import os
from pathlib import Path
from typing import List

import chromadb
import ollama
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_PATH = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "rag_documents"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100


def _get_chroma_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _file_hash(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _load_documents(file_path: str) -> List:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext in (".txt", ".md"):
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    return loader.load()


def _embed_texts(texts: List[str]) -> List[List[float]]:
    # ollama.embed() accepts a list of strings and returns all embeddings in one call
    response = ollama.embed(model=EMBED_MODEL, input=texts)
    return response.embeddings


def ingest_file(file_path: str) -> dict:
    """
    Ingest a single file into ChromaDB.

    Returns a dict with:
        - status: "added" | "skipped" | "updated"
        - chunks: number of chunks stored
        - file: filename
    """
    file_path = str(Path(file_path).resolve())
    filename = Path(file_path).name
    current_hash = _file_hash(file_path)

    collection = _get_chroma_collection()

    # Check if file was already ingested with the same hash
    existing = collection.get(where={"source": filename}, include=["metadatas"])
    if existing["ids"]:
        stored_hash = existing["metadatas"][0].get("file_hash", "")
        if stored_hash == current_hash:
            return {"status": "skipped", "chunks": len(existing["ids"]), "file": filename}
        # File changed — remove old chunks before re-ingesting
        collection.delete(where={"source": filename})

    # Load and split
    docs = _load_documents(file_path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    if not chunks:
        return {"status": "skipped", "chunks": 0, "file": filename}

    texts = [c.page_content for c in chunks]
    embeddings = _embed_texts(texts)

    ids = [f"{filename}_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source": filename,
            "file_path": file_path,
            "file_hash": current_hash,
            "chunk_index": i,
            "page": c.metadata.get("page", 0),
        }
        for i, c in enumerate(chunks)
    ]

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    status = "updated" if existing["ids"] else "added"
    return {"status": status, "chunks": len(chunks), "file": filename}


def list_ingested_files() -> List[dict]:
    """Return a list of all ingested files with their chunk counts."""
    collection = _get_chroma_collection()
    all_docs = collection.get(include=["metadatas"])
    files: dict = {}
    for meta in all_docs["metadatas"]:
        src = meta.get("source", "unknown")
        files[src] = files.get(src, 0) + 1
    return [{"file": k, "chunks": v} for k, v in sorted(files.items())]


def clear_collection():
    """Delete all documents from the ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    client.delete_collection(COLLECTION_NAME)
