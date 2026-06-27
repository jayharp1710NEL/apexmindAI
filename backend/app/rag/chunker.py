"""Very small word-based chunker.

Token counts are approximated by whitespace words (good enough for MVP retrieval).
Chunks overlap so a fact spanning a boundary is still retrievable.
"""

from __future__ import annotations


def chunk_text(
    text: str, *, size_tokens: int = 512, overlap_tokens: int = 64
) -> list[str]:
    words = text.split()
    if not words:
        return []
    if overlap_tokens >= size_tokens:
        overlap_tokens = size_tokens // 4
    step = size_tokens - overlap_tokens
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + size_tokens]
        if window:
            chunks.append(" ".join(window))
        if start + size_tokens >= len(words):
            break
    return chunks
