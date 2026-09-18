# tests/test_ollama_streamer.py

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import requests

from chaskiwasi.config.settings import Settings
from chaskiwasi.query_engine.ollama_streamer import OllamaStreamer


def test_stream_response_yields_each_fragment_sequentially() -> None:
    streamer = OllamaStreamer()

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(
        [
            b'{"response": "Hola"}',
            b'{"response": " mundo"}',
            b'{"response": " desde"}',
            b'{"response": " Ollama"}',
        ]
    )
    mock_response.raise_for_status.return_value = None

    with patch(
        "chaskiwasi.query_engine.ollama_streamer.requests.post",
        return_value=mock_response,
    ) as mock_post:
        result: List[str] = list(
            streamer.stream_response(
                prompt="Consulta con chunks recuperados.",
                system_prompt="Responde de forma precisa.",
            )
        )

    assert result == [
        "Hola",
        " mundo",
        " desde",
        " Ollama",
    ]

    mock_post.assert_called_once()

    call_args: Any = mock_post.call_args
    payload: Dict[str, Any] = call_args.kwargs["json"]

    assert call_args.args[0] == "http://localhost:11434/api/generate"
    assert call_args.kwargs["stream"] is True

    assert payload == {
        "model": Settings.LLM_MODEL_NAME,
        "prompt": "Consulta con chunks recuperados.",
        "system": "Responde de forma precisa.",
        "stream": True,
        "keep_alive": Settings.OLLAMA_KEEP_ALIVE,
    }


def test_stream_response_uses_required_hardware_constraints() -> None:
    streamer = OllamaStreamer()

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(
        [b'{"response": "OK"}']
    )
    mock_response.raise_for_status.return_value = None

    with patch(
        "chaskiwasi.query_engine.ollama_streamer.requests.post",
        return_value=mock_response,
    ) as mock_post:
        result: List[str] = list(
            streamer.stream_response("Consulta")
        )

    assert result == ["OK"]

    payload: Dict[str, Any] = mock_post.call_args.kwargs["json"]

    assert payload["model"] == Settings.LLM_MODEL_NAME
    assert payload["stream"] is True
    assert payload["keep_alive"] == Settings.OLLAMA_KEEP_ALIVE
    assert "system" not in payload


def test_stream_response_ignores_empty_and_invalid_lines() -> None:
    streamer = OllamaStreamer()

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(
        [
            b"",
            b"not-json",
            b'{"invalid": "field"}',
            b'{"response": "valido"}',
            b"",
        ]
    )
    mock_response.raise_for_status.return_value = None

    with patch(
        "chaskiwasi.query_engine.ollama_streamer.requests.post",
        return_value=mock_response,
    ):
        result: List[str] = list(
            streamer.stream_response("Consulta")
        )

    assert result == ["valido"]


def test_stream_response_handles_connection_error_cleanly() -> None:
    streamer = OllamaStreamer()

    with patch(
        "chaskiwasi.query_engine.ollama_streamer.requests.post",
        side_effect=requests.exceptions.ConnectionError,
    ) as mock_post:
        result: List[str] = list(
            streamer.stream_response("Consulta")
        )

    assert result == ["[ERROR] No se pudo conectar con Ollama."]
    mock_post.assert_called_once()


def test_stream_response_preserves_network_fragment_order() -> None:
    streamer = OllamaStreamer()

    fragments: List[str] = [
        "El ",
        "inmueble ",
        "tiene ",
        "una ",
        "hipoteca.",
    ]

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(
        [
            json.dumps({"response": fragment}).encode("utf-8")
            for fragment in fragments
        ]
    )
    mock_response.raise_for_status.return_value = None

    with patch(
        "chaskiwasi.query_engine.ollama_streamer.requests.post",
        return_value=mock_response,
    ):
        result: List[str] = list(
            streamer.stream_response("Consulta")
        )

    assert result == fragments
    assert "".join(result) == "El inmueble tiene una hipoteca."