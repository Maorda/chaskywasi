"""Tokenización de Markdown estructural para el RAG de Chaskiwasi."""

from __future__ import annotations

from typing import List

import tiktoken

from chaskiwasi.config.settings import settings


class ChunkTokenizer:
    """Divide Markdown estructural mediante ventanas de tokens con solapamiento."""

    def __init__(self, encoding_name: str | None = None, chunk_size: int | None = None, overlap: int | None = None) -> None:
        self._encoding = tiktoken.get_encoding(encoding_name or settings.TIKTOKEN_ENCODING)
        self._chunk_size = settings.CHUNK_SIZE if chunk_size is None else chunk_size
        self._overlap = settings.CHUNK_OVERLAP if overlap is None else overlap
        if self._chunk_size <= 0:
            raise ValueError("chunk_size debe ser mayor que cero.")
        if self._overlap < 0 or self._overlap >= self._chunk_size:
            raise ValueError("overlap debe ser >= 0 y menor que chunk_size.")

    def split_text(self, text: str) -> List[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        tokens = self._encoding.encode(text)
        if not tokens:
            return []

        step = self._chunk_size - self._overlap
        chunks: List[str] = []
        start = 0

        while start < len(tokens):
            end = min(start + self._chunk_size, len(tokens))
            chunks.append(self._encoding.decode(tokens[start:end]))
            if end >= len(tokens):
                break
            start += step

        return chunks
