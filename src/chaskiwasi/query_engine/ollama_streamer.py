# dantesito/chasky/query_engine/ollama_streamer.py

import json
from typing import Any, Dict, Iterator, Optional

import requests

from chaskiwasi.config.settings import Settings


class OllamaStreamer:
    """Cliente HTTP para consumir respuestas de Ollama mediante streaming."""

    _DEFAULT_ENDPOINT: str = "http://localhost:11434/api/generate"
    _CONNECTION_ERROR_MESSAGE: str = "[ERROR] No se pudo conectar con Ollama."

    def __init__(self, endpoint: str = _DEFAULT_ENDPOINT) -> None:
        self._endpoint: str = endpoint

    def stream_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Iterator[str]:
        """Genera incrementalmente la respuesta del LLM mediante streaming."""
        payload: Dict[str, Any] = {
            "model": Settings.LLM_MODEL_NAME,
            "prompt": prompt,
            "stream": True,
            "keep_alive": Settings.OLLAMA_KEEP_ALIVE,
        }

        if system_prompt is not None:
            payload["system"] = system_prompt

        try:
            response: requests.Response = requests.post(
                self._endpoint,
                json=payload,
                stream=True,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    decoded_line: str = (
                        line.decode("utf-8")
                        if isinstance(line, bytes)
                        else str(line)
                    )
                    data: Dict[str, Any] = json.loads(decoded_line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

                fragment: Any = data.get("response")

                if isinstance(fragment, str):
                    yield fragment

        except requests.exceptions.ConnectionError:
            yield self._CONNECTION_ERROR_MESSAGE