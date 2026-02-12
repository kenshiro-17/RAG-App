from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import tiktoken


@dataclass
class TextChunk:
    content: str
    chunk_index: int


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text_with_tiktoken(
    text: str,
    chunk_tokens: int = 450,
    overlap_tokens: int = 80,
    encoding_name: str = "cl100k_base",
) -> list[TextChunk]:
    if chunk_tokens <= 0:
        raise ValueError("chunk_tokens must be > 0")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be >= 0")
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be smaller than chunk_tokens")

    cleaned = clean_text(text)
    if not cleaned:
        return []

    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(cleaned)
    if not tokens:
        return []

    step = chunk_tokens - overlap_tokens
    chunks: list[TextChunk] = []
    chunk_index = 0
    for start in range(0, len(tokens), step):
        end = min(start + chunk_tokens, len(tokens))
        decoded = encoding.decode(tokens[start:end]).strip()
        if decoded:
            chunks.append(TextChunk(content=decoded, chunk_index=chunk_index))
            chunk_index += 1
        if end >= len(tokens):
            break

    return chunks


def content_hash(text: str) -> str:
    normalized = clean_text(text).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()
