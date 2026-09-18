# tests/test_chunk_tokenizer.py

from typing import List

import pytest
import tiktoken

from chaskiwasi.chunking.chunk_tokenizer import ChunkTokenizer
from chaskiwasi.config.settings import Settings


@pytest.fixture
def tokenizer() -> ChunkTokenizer:
    return ChunkTokenizer()


@pytest.fixture
def encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(Settings.TIKTOKEN_ENCODING)


def _build_long_markdown() -> str:
    sections: List[str] = []

    for index in range(1, 80):
        sections.append(
            f"""## Sección {index}

Esta es una sección de contenido Markdown utilizada para validar el
procesamiento determinista de texto mediante ventanas de tokens. El
contenido contiene información suficientemente extensa para generar
múltiples fragmentos y comprobar matemáticamente el tamaño de cada uno.

- Elemento principal {index}
- Información adicional sobre el documento
- Procesamiento mediante tiktoken
- Segmentación con solapamiento controlado

El sistema debe preservar exactamente la secuencia de tokens durante
la segmentación y reconstruir cada ventana mediante la decodificación
del subconjunto correspondiente de identificadores.
"""
        )

    return "\n".join(sections)


def test_split_text_success_never_exceeds_chunk_size(
    tokenizer: ChunkTokenizer,
    encoding: tiktoken.Encoding,
) -> None:
    text: str = _build_long_markdown()

    chunks: List[str] = tokenizer.split_text(text)

    assert chunks

    for chunk in chunks:
        chunk_tokens: List[int] = encoding.encode(chunk)
        assert len(chunk_tokens) <= Settings.CHUNK_SIZE


def test_split_text_preserves_exact_token_overlap(
    tokenizer: ChunkTokenizer,
    encoding: tiktoken.Encoding,
) -> None:
    text: str = _build_long_markdown()

    chunks: List[str] = tokenizer.split_text(text)

    assert len(chunks) >= 2

    first_tokens: List[int] = encoding.encode(chunks[0])
    second_tokens: List[int] = encoding.encode(chunks[1])

    overlap: int = Settings.CHUNK_OVERLAP

    assert len(first_tokens) == Settings.CHUNK_SIZE
    assert len(second_tokens) >= overlap
    assert first_tokens[-overlap:] == second_tokens[:overlap]


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        None,
        123,
        3.14,
        [],
        {},
        object(),
    ],
)
def test_split_text_handles_empty_and_invalid_input_safely(
    tokenizer: ChunkTokenizer,
    invalid_input: object,
) -> None:
    assert tokenizer.split_text(invalid_input) == []  # type: ignore[arg-type]