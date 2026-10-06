from typing import List

import pytest
import tiktoken

from chaskiwasi.chunking.chunk_tokenizer import ChunkTokenizer
from chaskiwasi.config.settings import settings


@pytest.fixture
def tokenizer() -> ChunkTokenizer:
    return ChunkTokenizer()


@pytest.fixture
def encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(settings.TIKTOKEN_ENCODING)


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
        assert len(encoding.encode(chunk)) <= settings.CHUNK_SIZE


def test_split_text_preserves_exact_token_overlap(
    tokenizer: ChunkTokenizer,
    encoding: tiktoken.Encoding,
) -> None:
    text: str = _build_long_markdown()
    chunks: List[str] = tokenizer.split_text(text)

    assert len(chunks) >= 2
    first_tokens = encoding.encode(chunks[0])
    second_tokens = encoding.encode(chunks[1])
    overlap = settings.CHUNK_OVERLAP

    assert len(first_tokens) == settings.CHUNK_SIZE
    assert len(second_tokens) >= overlap
    assert first_tokens[-overlap:] == second_tokens[:overlap]


@pytest.mark.parametrize(
    "invalid_input",
    ["", None, 123, 3.14, [], {}, object()],
)
def test_split_text_handles_empty_and_invalid_input_safely(
    tokenizer: ChunkTokenizer,
    invalid_input: object,
) -> None:
    assert tokenizer.split_text(invalid_input) == []  # type: ignore[arg-type]


def test_zero_chunk_size_is_rejected():
    with pytest.raises(ValueError, match="chunk_size debe ser mayor que cero"):
        ChunkTokenizer(chunk_size=0)


def test_zero_overlap_is_valid():
    tokenizer = ChunkTokenizer(chunk_size=8, overlap=0)
    assert tokenizer.split_text("texto corto")
