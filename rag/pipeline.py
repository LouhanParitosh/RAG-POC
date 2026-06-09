"""
Pipeline module: combines retriever + generator into a single RAG call.
Returns both the answer and all intermediate artifacts for display.
"""

from typing import Generator

from .generator import build_prompt, generate_stream
from .retriever import retrieve


def rag_stream(query: str, top_k: int = 4) -> dict:
    """
    Run the full RAG pipeline with streaming.

    Returns a dict with:
        - chunks:          list of retrieved chunk dicts (from retriever)
        - augmented_prompt: the full prompt sent to the LLM (string)
        - stream:          a generator that yields answer tokens
    """
    chunks = retrieve(query, top_k=top_k)
    augmented_prompt = build_prompt(query, chunks)
    stream: Generator[str, None, None] = generate_stream(query, chunks)

    return {
        "chunks": chunks,
        "augmented_prompt": augmented_prompt,
        "stream": stream,
    }


def rag(query: str, top_k: int = 4) -> dict:
    """
    Non-streaming version. Returns the same dict but with a full answer string
    instead of a stream.
    """
    result = rag_stream(query, top_k=top_k)
    result["answer"] = "".join(result.pop("stream"))
    return result
