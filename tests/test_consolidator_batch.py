from unittest.mock import MagicMock
import pytest

from chaskiwasi.classification.cascade_factory import CascadeFactory


@pytest.fixture
def mock_strategies():
    """Estrategias simuladas para verificar la ejecución en lote y propagación de estado."""
    strat1 = MagicMock()
    strat2 = MagicMock()

    # Chunk 0: strat1 detecta SUNARP, ENCABEZADO
    # Chunk 1: strat1 no detecta nada, strat2 detecta PARTES
    # Chunk 2: ninguna detecta nada -> cae al fallback por defecto
    strat1.classify.side_effect = [
        ("SUNARP", "ENCABEZADO"),
        (None, None),
        (None, None),
    ]
    strat2.classify.side_effect = [
        (None, "PARTES"),
        (None, None),
    ]

    return [strat1, strat2]


def test_process_chunks_batch_success_and_context_propagation(mock_strategies):
    """Verifica que el procesamiento en lote ejecute secuencialmente y propague el contexto activo."""
    factory = CascadeFactory(
        strategies=mock_strategies,
        default_source="DEFAULT_SRC",
        default_section="DEFAULT_SEC",
    )

    chunks = [
        "Chunk 0: Encabezado registral SUNARP",
        "Chunk 1: Cláusula de comprador y vendedor",
        "Chunk 2: Texto sin coincidencia de reglas",
    ]

    results = factory.process_chunks_batch(chunks, current_source="INITIAL_SRC")

    assert len(results) == 3
    # Chunk 0: Clasificado explícitamente como SUNARP, ENCABEZADO
    assert results[0] == ("SUNARP", "ENCABEZADO")
    # Chunk 1: Mantiene SUNARP como contexto activo y clasifica PARTES
    assert results[1] == ("SUNARP", "PARTES")
    # Chunk 2: Ninguna estrategia clasifica, retorna el contexto activo acumulado y la sección por defecto
    assert results[2] == ("SUNARP", "DEFAULT_SEC")


def test_process_chunks_batch_empty_list():
    """Verifica que pasar una lista vacía retorne una lista vacía sin procesar estrategias."""
    factory = CascadeFactory(default_source="SRC", default_section="SEC")
    results = factory.process_chunks_batch([])
    assert results == []


def test_process_chunks_batch_with_blank_and_none_chunks():
    """Verifica que cadenas vacías o None dentro del lote devuelvan los valores por defecto."""
    factory = CascadeFactory(
        strategies=[],
        default_source="REMAJU",
        default_section="RESOLUCION",
    )

    chunks = ["", "   ", None]
    results = factory.process_chunks_batch(chunks, current_source="REMAJU")

    assert len(results) == 3
    assert all(res == ("REMAJU", "RESOLUCION") for res in results)