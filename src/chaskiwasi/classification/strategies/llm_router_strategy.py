import logging
from typing import Any, Dict, Optional, Tuple

import requests

from chaskiwasi.classification.strategies.base_strategy import BaseStrategy
from chaskiwasi.config.settings import settings

logger = logging.getLogger(__name__)


class LLMRouterStrategy(BaseStrategy):
    """Estrategia agnóstica de clasificación de respaldo mediante Ollama local."""

    def __init__(
        self,
        system_prompt: str,
        label_mapping: Dict[str, Any],
        endpoint: str = "http://localhost:11434/api/generate",
        model_name: Optional[str] = None,
        keep_alive: Optional[int] = None,
        timeout: int = 10,
    ) -> None:
        self.system_prompt = system_prompt
        self.label_mapping = label_mapping
        self.endpoint = endpoint
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.keep_alive = keep_alive if keep_alive is not None else settings.OLLAMA_KEEP_ALIVE
        self.timeout = timeout

    def classify(
        self,
        chunk_text: str,
        current_source: Optional[Any] = None,
    ) -> Tuple[Optional[Any], Optional[Any]]:
        """Clasifica el fragmento mediante el modelo local de Ollama."""
        if not isinstance(chunk_text, str) or not chunk_text.strip():
            return None, None

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": f"{self.system_prompt}\n\n{chunk_text}",
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": 10,
            },
        }

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_data: Dict[str, Any] = response.json()
        except (requests.RequestException, ValueError, TypeError) as err:
            logger.error("Error en inferencia remota con Ollama: %s", err)
            return None, None

        raw_result = str(response_data.get("response", "")).strip().upper()

        if "DESCONOCIDO" in raw_result or not raw_result:
            return None, None

        for label_key, mapped_enum in self.label_mapping.items():
            if label_key.upper() in raw_result:
                return None, mapped_enum

        return None, None