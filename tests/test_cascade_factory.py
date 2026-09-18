from unittest.mock import MagicMock

import pytest

from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.config.taxonomy_registry import SectionEnum, SourceEnum


@pytest.fixture
def mock_strategy_1() -> MagicMock:
    """Simula la primera estrategia de la cascada (ej. Regex)."""
    strategy = MagicMock()
    strategy.classify.return_value = (None, None)
    return strategy


@pytest.fixture
def mock_strategy_2() -> MagicMock:
    """Simula la segunda estrategia de la cascada (ej. LLM o Contexto)."""
    strategy = MagicMock()
    strategy.classify.return_value = (None, None)
    return strategy


@pytest.fixture
def generic_factory(
    mock_strategy_1: MagicMock, mock_strategy_2: MagicMock
) -> CascadeFactory:
    """Fábrica agnóstica para probar el comportamiento puro de la cascada en el core."""
    return CascadeFactory(
        strategies=[mock_strategy_1, mock_strategy_2],
        default_source=SourceEnum.REMAJU,
        default_section=SectionEnum.RESOLUCION,
    )


def test_cascade_factory_initialization(generic_factory: CascadeFactory) -> None:
    """Verifica que la fábrica se instancie correctamente con sus estrategias y valores por defecto."""
    assert len(generic_factory._strategies) == 2
    assert generic_factory.default_source == SourceEnum.REMAJU
    assert generic_factory.default_section == SectionEnum.RESOLUCION


def test_cascade_factory_first_strategy_success(
    generic_factory: CascadeFactory,
    mock_strategy_1: MagicMock,
    mock_strategy_2: MagicMock,
) -> None:
    """Verifica el atajo: si la primera estrategia clasifica el texto, detiene la cascada y no invoca la segunda."""
    mock_strategy_1.classify.return_value = (SourceEnum.SUNARP, SectionEnum.ENCABEZADO)

    source, section = generic_factory.process_chunk(
        "texto de prueba de encabezado", current_source=SourceEnum.SUNARP
    )

    mock_strategy_1.classify.assert_called_once_with(
        "texto de prueba de encabezado", current_source=SourceEnum.SUNARP
    )
    mock_strategy_2.classify.assert_not_called()
    assert source == SourceEnum.SUNARP
    assert section == SectionEnum.ENCABEZADO


def test_cascade_factory_fallback_success(
    generic_factory: CascadeFactory,
    mock_strategy_1: MagicMock,
    mock_strategy_2: MagicMock,
) -> None:
    """Verifica el fallback: avanza a la siguiente estrategia si la anterior retorna (None, None)."""
    mock_strategy_2.classify.return_value = (None, SectionEnum.GRAVAMEN)

    source, section = generic_factory.process_chunk(
        "texto con embargo registrado", current_source=SourceEnum.SUNARP
    )

    mock_strategy_1.classify.assert_called_once_with(
        "texto con embargo registrado", current_source=SourceEnum.SUNARP
    )
    mock_strategy_2.classify.assert_called_once_with(
        "texto con embargo registrado", current_source=SourceEnum.SUNARP
    )
    assert source == SourceEnum.SUNARP
    assert section == SectionEnum.GRAVAMEN


def test_cascade_factory_empty_text_returns_default(
    generic_factory: CascadeFactory,
) -> None:
    """Verifica que textos nulos o vacíos retornen los valores por defecto sin invocar las estrategias."""
    source_empty, section_empty = generic_factory.process_chunk(
        "", current_source=SourceEnum.REMAJU
    )
    assert source_empty == SourceEnum.REMAJU
    assert section_empty == SectionEnum.RESOLUCION

    source_none, section_none = generic_factory.process_chunk(
        None, current_source=SourceEnum.SUNARP
    )
    assert source_none == SourceEnum.SUNARP
    assert section_none == SectionEnum.RESOLUCION


def test_cascade_factory_full_fallback_returns_default(
    generic_factory: CascadeFactory,
    mock_strategy_1: MagicMock,
    mock_strategy_2: MagicMock,
) -> None:
    """Verifica que se asignen la fuente y sección por defecto si todas las estrategias fallan."""
    source, section = generic_factory.process_chunk(
        "texto no reconocido por ningún patrón", current_source=SourceEnum.REMAJU
    )

    assert source == SourceEnum.REMAJU
    assert section == SectionEnum.RESOLUCION
    assert mock_strategy_1.classify.called
    assert mock_strategy_2.classify.called


def test_cascade_factory_handles_strategy_exception(
    generic_factory: CascadeFactory,
    mock_strategy_1: MagicMock,
    mock_strategy_2: MagicMock,
) -> None:
    """Verifica la resiliencia de la cascada si una estrategia lanza un fallo de ejecución o de red."""
    mock_strategy_1.classify.side_effect = RuntimeError("Fallo en el servicio externo")

    source, section = generic_factory.process_chunk(
        "fragmento de texto riesgoso", current_source=SourceEnum.SUNARP
    )

    # Debe haber atrapado la excepción de la primera y haber continuado con la segunda
    mock_strategy_2.classify.assert_called_once()
    assert source == SourceEnum.SUNARP
    assert section == SectionEnum.RESOLUCION