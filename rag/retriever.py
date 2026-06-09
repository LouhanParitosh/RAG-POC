"""
Retriever module: embed a query and find the most similar chunks in ChromaDB.
Returns chunks with their similarity scores and source metadata.
"""

from typing import List

import ollama

from .ingestion import EMBED_MODEL, _get_chroma_collection

TOP_K = 4


def retrieve(query: str, top_k: int = TOP_K) -> List[dict]:
    """
    Embed the query and return the top_k most relevant chunks.

    Each result dict contains:
        - text:       the chunk content
        - source:     filename the chunk came from
        - page:       page number (for PDFs)
        - chunk_index: position within the source document
        - score:      cosine distance (lower = more similar; 0 is perfect match)
        - similarity: 1 - score, easier to read as a percentage
    """
    response = ollama.embed(model=EMBED_MODEL, input=query)
    query_embedding = response.embeddings[0]

    collection = _get_chroma_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append(
            {
                "text": text,
                "source": meta.get("source", "unknown"),
                "page": meta.get("page", 0),
                "chunk_index": meta.get("chunk_index", 0),
                "score": round(dist, 4),
                "similarity": round((1 - dist) * 100, 1),
            }
        )

    # Sort by best similarity first
    chunks.sort(key=lambda x: x["score"])
    return chunks
