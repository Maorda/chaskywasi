from unittest.mock import MagicMock, patch
import pytest
import requests

from chaskiwasi.classification.strategies.llm_router_strategy import LLMRouterStrategy


@pytest.fixture
def mock_label_mapping():
    """Mapping sintético para aislar las pruebas de la taxonomía real."""
    return {
        "PARTES": "SECTION_PARTES",
        "GRAVAMEN": "SECTION_GRAVAMEN",
        "RESOLUCION": "SECTION_RESOLUCION",
        "ENCABEZADO": "SECTION_ENCABEZADO",
    }


@pytest.fixture
def router_instance(mock_label_mapping):
    """Instancia limpia de LLMRouterStrategy para las pruebas."""
    return LLMRouterStrategy(
        system_prompt="Clasifica este fragmento.",
        label_mapping=mock_label_mapping,
        endpoint="http://localhost:11434/api/generate",
    )


# =====================================================================
# 1. PRUEBAS DE INICIALIZACIÓN
# =====================================================================

def test_init_custom_parameters(mock_label_mapping):
    """Verifica que los parámetros inyectados y por defecto se asignen correctamente."""
    strategy = LLMRouterStrategy(
        system_prompt="Prompt test",
        label_mapping=mock_label_mapping,
        endpoint="http://127.0.0.1:11434/api/generate",
        model_name="llama3.2:1b",
        timeout=5,
    )
    assert strategy.system_prompt == "Prompt test"
    assert strategy.label_mapping == mock_label_mapping
    assert strategy.endpoint == "http://127.0.0.1:11434/api/generate"
    assert strategy.model_name == "llama3.2:1b"
    assert strategy.timeout == 5


# =====================================================================
# 2. PRUEBAS DEL MÉTODO CLASSIFY
# =====================================================================

def test_classify_empty_or_whitespace_text_returns_none(router_instance):
    """Verifica que entradas vacías o nulas retornen (None, None) de inmediato."""
    source, section = router_instance.classify("")
    assert source is None
    assert section is None

    source_spaces, section_spaces = router_instance.classify("   \n\t  ")
    assert source_spaces is None
    assert section_spaces is None


@patch("requests.post")
def test_classify_success(mock_post, router_instance):
    """Verifica una respuesta exitosa de Ollama traduciendo la etiqueta correspondiente."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "PARTES"}
    mock_post.return_value = mock_response

    source, section = router_instance.classify("Ejecutante vs Demandado")

    assert source is None
    assert section == "SECTION_PARTES"
    mock_post.assert_called_once()


@patch("requests.post")
def test_classify_desconocido_returns_none(mock_post, router_instance):
    """Verifica que si la respuesta contiene 'DESCONOCIDO' retorne (None, None)."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "DESCONOCIDO"}
    mock_post.return_value = mock_response

    source, section = router_instance.classify("Texto no identificable")

    assert source is None
    assert section is None


@patch("requests.post")
def test_classify_unmapped_label_returns_none(mock_post, router_instance):
    """Verifica que respuestas no contempladas en el mapping devuelvan (None, None)."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "CATEGORIA_INEXISTENTE"}
    mock_post.return_value = mock_response

    source, section = router_instance.classify("Texto arbitrario")

    assert source is None
    assert section is None


@patch("requests.post")
def test_classify_handles_network_exception_gracefully(mock_post, router_instance):
    """Verifica resiliencia ante errores de conexión o timeouts de requests."""
    mock_post.side_effect = requests.RequestException("Fallo de red al conectar con Ollama")

    source, section = router_instance.classify("Texto de prueba")

    assert source is None
    assert section is None