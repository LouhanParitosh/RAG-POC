"""
Generator module: build an augmented prompt from retrieved chunks and stream
the LLM response via Ollama.
"""

from typing import Generator, List

import ollama

LLM_MODEL = "llama3.2:latest"

SYSTEM_PROMPT = """You are a helpful assistant that answers questions strictly based on the provided context.

Rules:
- Only use information from the context below to answer.
- If the context does not contain enough information, say "I don't have enough information in the provided documents to answer this."
- Be concise and accurate.
- Cite the source document name when relevant (e.g. "According to report.pdf...").
"""


def build_prompt(query: str, chunks: List[dict]) -> str:
    """Construct the full augmented prompt shown to the LLM."""
    context_blocks = []
    for i, chunk in enumerate(chunks, 1):
        header = f"[Source {i}: {chunk['source']}, page {chunk['page']}, similarity {chunk['similarity']}%]"
        context_blocks.append(f"{header}\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_blocks)
    return f"Context:\n{context}\n\nQuestion: {query}"


def generate_stream(query: str, chunks: List[dict]) -> Generator[str, None, None]:
    """
    Stream the LLM answer token by token.
    Yields string tokens as they arrive.
    """
    augmented_prompt = build_prompt(query, chunks)

    stream = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": augmented_prompt},
        ],
        stream=True,
    )

    for chunk in stream:
        token = chunk["message"]["content"]
        if token:
            yield token


def generate(query: str, chunks: List[dict]) -> str:
    """Non-streaming version — returns the full answer at once."""
    return "".join(generate_stream(query, chunks))
