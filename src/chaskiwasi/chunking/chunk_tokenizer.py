# dantesito/chasky/chunking/chunk_tokenizer.py

from typing import List

import tiktoken

from chaskiwasi.config.settings import Settings


class ChunkTokenizer:
    """Divide textos en fragmentos mediante ventanas de tokens de tiktoken."""

    def __init__(self) -> None:
        self._encoding = tiktoken.get_encoding(Settings.TIKTOKEN_ENCODING)

    def split_text(self, text: str) -> List[str]:
        """Divide el texto en chunks determinados exclusivamente por tokens."""
        if not isinstance(text, str) or not text:
            return []

        tokens: List[int] = self._encoding.encode(text)

        if not tokens:
            return []

        chunk_size: int = Settings.CHUNK_SIZE
        step: int = Settings.CHUNK_SIZE - Settings.CHUNK_OVERLAP

        chunks: List[str] = []
        start: int = 0
        total_tokens: int = len(tokens)

        while start < total_tokens:
            end: int = min(start + chunk_size, total_tokens)
            chunk_tokens: List[int] = tokens[start:end]
            chunks.append(self._encoding.decode(chunk_tokens))

            if end >= total_tokens:
                break

            start += step

        return chunks