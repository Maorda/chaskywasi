from unittest.mock import MagicMock, patch

import pytest
import requests

from chaskiwasi.classification.strategies.base_strategy import ClassificationContext
from chaskiwasi.classification.strategies.llm_router_strategy import LLMRouterStrategy
from chaskiwasi.config.taxonomy_registry import Taxonomy
from chaskiwasi.plugins.contracts import PluginContext


@pytest.fixture
def mock_label_mapping():
    return {
        "PARTES": "SECTION_PARTES",
        "GRAVAMEN": "SECTION_GRAVAMEN",
        "RESOLUCION": "SECTION_RESOLUCION",
        "ENCABEZADO": "SECTION_ENCABEZADO",
    }


@pytest.fixture
def router_instance(mock_label_mapping):
    return LLMRouterStrategy(
        system_prompt="Clasifica este fragmento.",
        label_mapping=mock_label_mapping,
        endpoint="http://localhost:11434/api/generate",
    )


@pytest.fixture
def classification_context(mock_source_enum, mock_section_enum):
    taxonomy = Taxonomy("llm_test", mock_source_enum, mock_section_enum)
    return ClassificationContext(
        plugin=PluginContext("llm_test", taxonomy),
        current_source=mock_source_enum.REMAJU,
    )


def test_init_custom_parameters(mock_label_mapping):
    strategy = LLMRouterStrategy(
        system_prompt="Prompt test",
        label_mapping=mock_label_mapping,
        endpoint="http://127.0.0.1:11434/api/generate",
        model_name="llama3.2:1b",
        timeout=5,
    )

    assert strategy.system_prompt == "Prompt test"
    assert strategy.label_mapping == {key.lower(): value for key, value in mock_label_mapping.items()}
    assert strategy.endpoint == "http://127.0.0.1:11434/api/generate"
    assert strategy.model_name == "llama3.2:1b"
    assert strategy.timeout == 5


def test_classify_empty_or_whitespace_text_returns_none(router_instance, classification_context):
    result = router_instance.classify("", classification_context)
    assert result.section is None

    result_spaces = router_instance.classify("   \n\t  ", classification_context)
    assert result_spaces.section is None


@patch("requests.post")
def test_classify_success(mock_post, router_instance, classification_context, mock_source_enum):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "PARTES"}
    mock_post.return_value = mock_response

    result = router_instance.classify("Ejecutante vs Demandado", classification_context)

    assert result.source is mock_source_enum.REMAJU
    assert result.section == "SECTION_PARTES"
    mock_post.assert_called_once()


@patch("requests.post")
def test_classify_desconocido_returns_none(mock_post, router_instance, classification_context):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "DESCONOCIDO"}
    mock_post.return_value = mock_response

    result = router_instance.classify("Texto no identificable", classification_context)

    assert result.section is None


@patch("requests.post")
def test_classify_unmapped_label_returns_none(mock_post, router_instance, classification_context):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "CATEGORIA_INEXISTENTE"}
    mock_post.return_value = mock_response

    result = router_instance.classify("Texto arbitrario", classification_context)

    assert result.section is None


@patch("requests.post")
def test_classify_handles_network_exception_gracefully(mock_post, router_instance, classification_context):
    mock_post.side_effect = requests.RequestException("Fallo de red al conectar con Ollama")

    result = router_instance.classify("Texto de prueba", classification_context)

    assert result.section is None
