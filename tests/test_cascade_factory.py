import os
from typing import Generator
from unittest.mock import patch

import pytest

from chaskiwasi.config.taxonomy_registry import SectionEnum, SourceEnum
from chaskiwasi.contrib import create_peru_cascade_factory


@pytest.fixture
def mock_env_api_key() -> Generator[None, None, None]:
    """Asegura la presencia de GEMINI_API_KEY para la inicialización limpia de GeminiStreamer."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyMockKey_Gemini_123"}, clear=True):
        yield


def test_cascade_factory_fallback_to_gemini(mock_env_api_key: None) -> None:
    """Verifica que la fábrica recurra a GeminiStreamer cuando las estrategias previas fallan."""
    sample_text = "Embargo en forma de inscripción sobre la finca registral N° 12345678."

    with patch(
        "chaskiwasi.classification.strategies.cpu_regex_strategy.CPURegexStrategy.classify",
        return_value=(None, None),
    ), patch(
        "chaskiwasi.classification.strategies.context_overlap_strategy.ContextOverlapStrategy.classify",
        return_value=(None, None),
    ), patch(
        "chaskiwasi.classification.strategies.gemini_streamer.GeminiStreamer.classify",
        return_value=(None, SectionEnum.GRAVAMEN),
    ) as mock_gemini_classify:

        factory = create_peru_cascade_factory()
        source, section = factory.process_chunk(sample_text, current_source=SourceEnum.SUNARP)

        mock_gemini_classify.assert_called_once_with(sample_text, current_source=SourceEnum.SUNARP)
        assert source == SourceEnum.SUNARP
        assert section == SectionEnum.GRAVAMEN


def test_cascade_factory_empty_text_returns_default(mock_env_api_key: None) -> None:
    """Verifica que textos nulos o vacíos retornen la sección por defecto sin invocar estrategias."""
    factory = create_peru_cascade_factory()

    source_empty, section_empty = factory.process_chunk("", current_source=SourceEnum.REMAJU)
    assert source_empty == SourceEnum.REMAJU
    assert section_empty == SectionEnum.RESOLUCION

    source_none, section_none = factory.process_chunk(None, current_source=SourceEnum.SUNARP)
    assert source_none == SourceEnum.SUNARP
    assert section_none == SectionEnum.RESOLUCION


def test_cascade_factory_full_fallback_returns_default(mock_env_api_key: None) -> None:
    """Verifica el comportamiento cuando ninguna estrategia categoriza el texto."""
    sample_text = "Texto indeterminado de una resolución registral."

    with patch(
        "chaskiwasi.classification.strategies.cpu_regex_strategy.CPURegexStrategy.classify",
        return_value=(None, None),
    ), patch(
        "chaskiwasi.classification.strategies.context_overlap_strategy.ContextOverlapStrategy.classify",
        return_value=(None, None),
    ), patch(
        "chaskiwasi.classification.strategies.gemini_streamer.GeminiStreamer.classify",
        return_value=(None, None),
    ):

        factory = create_peru_cascade_factory()
        source, section = factory.process_chunk(sample_text, current_source=SourceEnum.REMAJU)

        assert source == SourceEnum.REMAJU
        assert section == SectionEnum.RESOLUCION


def test_cascade_factory_handles_strategy_exception(mock_env_api_key: None) -> None:
    """Verifica la resiliencia de la fábrica cuando una estrategia lanza una excepción."""
    sample_text = "Se resuelve declarar procedente la solicitud presentante."

    with patch(
        "chaskiwasi.classification.strategies.cpu_regex_strategy.CPURegexStrategy.classify",
        return_value=(None, None),
    ), patch(
        "chaskiwasi.classification.strategies.context_overlap_strategy.ContextOverlapStrategy.classify",
        return_value=(None, None),
    ), patch(
        "chaskiwasi.classification.strategies.gemini_streamer.GeminiStreamer.classify",
        side_effect=RuntimeError("Fallo de conexión con Google AI Studio"),
    ):

        factory = create_peru_cascade_factory()
        source, section = factory.process_chunk(sample_text, current_source=SourceEnum.SUNARP)

        assert source == SourceEnum.SUNARP
        assert section == SectionEnum.RESOLUCION