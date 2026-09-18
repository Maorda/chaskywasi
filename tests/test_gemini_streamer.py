import os
from unittest.mock import MagicMock, patch

import pytest

from chaskiwasi.classification.strategies.gemini_streamer import GeminiStreamer


@pytest.fixture
def mock_label_mapping():
    """Mapping ficticio para evaluar la traduccion de etiquetas."""
    return {
        "encabezado": "SECTION_ENCABEZADO",
        "resolucion": "SECTION_RESOLUCION",
    }


@pytest.fixture
def mock_env_api_key():
    """Inyecta una API key sintácticamente válida en las variables de entorno."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyMockedValidKey_12345"}, clear=True):
        yield "AIzaSyMockedValidKey_12345"


@pytest.fixture
def streamer_instance(mock_env_api_key, mock_label_mapping):
    """Instancia limpia de GeminiStreamer con el cliente GenAI simulado."""
    with patch("google.genai.Client"):
        streamer = GeminiStreamer(
            system_instruction="Clasifica el texto.",
            label_mapping=mock_label_mapping,
        )
        return streamer


# =====================================================================
# 1. PRUEBAS DE INICIALIZACIÓN Y CREDENCIALES
# =====================================================================

def test_init_raises_value_error_when_key_missing():
    """Verifica que se lance ValueError si no existe GEMINI_API_KEY ni .env."""
    with patch.dict(os.environ, {}, clear=True), patch("os.path.exists", return_value=False):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiStreamer(
                system_instruction="Prompt test",
                label_mapping={},
            )


@patch("google.genai.Client")
def test_init_success_with_env_key(mock_client, mock_env_api_key, mock_label_mapping):
    """Verifica la inicialización correcta cuando la key está presente en el entorno."""
    streamer = GeminiStreamer(
        system_instruction="Prompt test",
        label_mapping=mock_label_mapping,
    )
    assert streamer.system_instruction == "Prompt test"
    assert streamer.label_mapping == mock_label_mapping
    mock_client.assert_called_once_with(api_key=mock_env_api_key)


# =====================================================================
# 2. PRUEBAS DEL MÉTODO CLASSIFY
# =====================================================================

def test_classify_empty_or_whitespace_text_returns_none(streamer_instance):
    """Verifica que textos vacíos o de puros espacios retornen (None, None) sin llamar a la API."""
    source, section = streamer_instance.classify("")
    assert source is None
    assert section is None

    source_spaces, section_spaces = streamer_instance.classify("   \n\t  ")
    assert source_spaces is None
    assert section_spaces is None


def test_classify_success(streamer_instance):
    """Verifica una clasificación exitosa traduciendo la etiqueta devuelta por Gemini."""
    mock_response = MagicMock()
    mock_response.text = "  ENCABEZADO \n"  # Evalúa también la limpieza de espacios y minúsculas
    streamer_instance.client.models.generate_content.return_value = mock_response

    source, section = streamer_instance.classify("Texto legal de prueba")

    assert source is None
    assert section == "SECTION_ENCABEZADO"
    streamer_instance.client.models.generate_content.assert_called_once()


def test_classify_label_desconocido_returns_none(streamer_instance):
    """Verifica que si el modelo responde 'desconocido' se devuelva (None, None)."""
    mock_response = MagicMock()
    mock_response.text = "desconocido"
    streamer_instance.client.models.generate_content.return_value = mock_response

    source, section = streamer_instance.classify("Texto ambiguo")

    assert source is None
    assert section is None


def test_classify_unmapped_label_returns_none(streamer_instance):
    """Verifica que respuestas fuera del mapping registrado retornen (None, None)."""
    mock_response = MagicMock()
    mock_response.text = "etiqueta_inexistente"
    streamer_instance.client.models.generate_content.return_value = mock_response

    source, section = streamer_instance.classify("Texto legal de prueba")

    assert source is None
    assert section is None


def test_classify_handles_api_exception_gracefully(streamer_instance):
    """Verifica resiliencia ante errores de red o excepciones lanzadas por el SDK de Google."""
    streamer_instance.client.models.generate_content.side_effect = Exception("Error de conexión con la API")

    source, section = streamer_instance.classify("Texto legal de prueba")

    assert source is None
    assert section is None