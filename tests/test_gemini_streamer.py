import os
from unittest.mock import MagicMock, patch

import pytest

from chaskiwasi.classification.strategies.base_strategy import ClassificationContext
from chaskiwasi.classification.strategies.gemini_streamer import GeminiStreamer


def make_context(mock_source_enum, mock_section_enum):
    from chaskiwasi.config.taxonomy_registry import Taxonomy
    from chaskiwasi.plugins.contracts import PluginContext

    taxonomy = Taxonomy("gemini_test", mock_source_enum, mock_section_enum)
    return ClassificationContext(
        plugin=PluginContext("gemini_test", taxonomy),
        current_source=mock_source_enum.REMAJU,
    )


@pytest.fixture
def mock_label_mapping():
    return {
        "encabezado": "SECTION_ENCABEZADO",
        "resolucion": "SECTION_RESOLUCION",
    }


@pytest.fixture
def mock_env_api_key():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyMockedValidKey_12345"}, clear=True):
        yield "AIzaSyMockedValidKey_12345"


@pytest.fixture
def streamer_instance(mock_env_api_key, mock_label_mapping):
    with patch("google.genai.Client"):
        return GeminiStreamer(
            system_instruction="Clasifica el texto.",
            label_mapping=mock_label_mapping,
        )


def test_init_raises_value_error_when_key_missing():
    with patch.dict(os.environ, {}, clear=True), patch("os.path.exists", return_value=False):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiStreamer(system_instruction="Prompt test", label_mapping={})


@patch("google.genai.Client")
def test_init_success_with_env_key(mock_client, mock_env_api_key, mock_label_mapping):
    streamer = GeminiStreamer(
        system_instruction="Prompt test",
        label_mapping=mock_label_mapping,
    )

    assert streamer.system_instruction == "Prompt test"
    assert streamer.label_mapping == mock_label_mapping
    mock_client.assert_called_once_with(api_key=mock_env_api_key)


def test_classify_empty_or_whitespace_text_returns_none(streamer_instance, mock_source_enum, mock_section_enum):
    context = make_context(mock_source_enum, mock_section_enum)
    result = streamer_instance.classify("", context)
    assert result.source is None
    assert result.section is None

    result_spaces = streamer_instance.classify("   \n\t  ", context)
    assert result_spaces.source is None
    assert result_spaces.section is None


def test_classify_success(streamer_instance, mock_source_enum, mock_section_enum):
    mock_response = MagicMock()
    mock_response.text = "  ENCABEZADO \n"
    streamer_instance.client.models.generate_content.return_value = mock_response

    result = streamer_instance.classify("Texto legal de prueba", make_context(mock_source_enum, mock_section_enum))

    assert result.source is not None
    assert result.section == "SECTION_ENCABEZADO"
    assert result.matched is True
    streamer_instance.client.models.generate_content.assert_called_once()


def test_classify_label_desconocido_returns_none(streamer_instance, mock_source_enum, mock_section_enum):
    mock_response = MagicMock()
    mock_response.text = "desconocido"
    streamer_instance.client.models.generate_content.return_value = mock_response

    result = streamer_instance.classify("Texto ambiguo", make_context(mock_source_enum, mock_section_enum))

    assert result.section is None
    assert result.matched is False


def test_classify_unmapped_label_returns_none(streamer_instance, mock_source_enum, mock_section_enum):
    mock_response = MagicMock()
    mock_response.text = "etiqueta_inexistente"
    streamer_instance.client.models.generate_content.return_value = mock_response

    result = streamer_instance.classify("Texto legal de prueba", make_context(mock_source_enum, mock_section_enum))

    assert result.section is None
    assert result.matched is False


def test_classify_handles_api_exception_gracefully(streamer_instance, mock_source_enum, mock_section_enum):
    streamer_instance.client.models.generate_content.side_effect = Exception("Error de conexión con la API")

    result = streamer_instance.classify("Texto legal de prueba", make_context(mock_source_enum, mock_section_enum))

    assert result.section is None
    assert result.matched is False
