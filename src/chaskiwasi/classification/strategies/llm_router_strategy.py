"""Estrategia LLM de último recurso mediante Ollama local."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from chaskiwasi.classification.strategies.base_strategy import (
    BaseStrategy,
    ClassificationContext,
    ClassificationResult,
)
from chaskiwasi.config.settings import settings

logger = logging.getLogger(__name__)


class LLMRouterStrategy(BaseStrategy):
    """Usa un modelo local solo cuando las estrategias deterministas no clasificaron."""

    def __init__(
        self,
        system_prompt: str,
        label_mapping: Dict[str, Any],
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        keep_alive: Optional[int] = None,
        timeout: int = 10,
        max_output_tokens: int = 8,
    ) -> None:
        self.system_prompt = system_prompt
        self.label_mapping = {str(key).strip().lower(): value for key, value in label_mapping.items()}
        self.endpoint = endpoint or settings.OLLAMA_ENDPOINT
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.keep_alive = keep_alive if keep_alive is not None else settings.OLLAMA_KEEP_ALIVE
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens

    def classify(self, chunk: str, context: ClassificationContext) -> ClassificationResult:
        if not isinstance(chunk, str) or not chunk.strip():
            return ClassificationResult.no_match("chunk vacío")

        prompt = f"{self.system_prompt}\n\nDevuelve únicamente una etiqueta válida.\n\n{chunk}"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"num_predict": self.max_output_tokens},
        }

        try:
            response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.warning("Ollama no pudo clasificar el chunk: %s", exc)
            return ClassificationResult.no_match("fallo_ollama")

        raw = str(data.get("response", "")).strip().lower()
        if not raw or raw == "desconocido":
            return ClassificationResult.no_match("llm_sin_resultado")

        label = next((key for key in self.label_mapping if key == raw), None)
        if label is None:
            # Aceptamos una única etiqueta incrustada en la respuesta, sin enviar otro request.
            label = next((key for key in self.label_mapping if key in raw), None)

        if label is None:
            return ClassificationResult.no_match("llm_etiqueta_fuera_taxonomia")

        return ClassificationResult(
            source=context.current_source,
            section=self.label_mapping[label],
            matched=True,
            reason="llm_local",
        )
