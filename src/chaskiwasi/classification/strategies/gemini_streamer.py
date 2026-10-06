"""Clasificación remota opcional mediante Gemini."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from google import genai
from google.genai import types

from chaskiwasi.classification.strategies.base_strategy import (
    BaseStrategy,
    ClassificationContext,
    ClassificationResult,
)
from chaskiwasi.config.settings import settings

logger = logging.getLogger(__name__)


class GeminiStreamer(BaseStrategy):
    """Fallback remoto opcional. No carga credenciales desde archivos por su cuenta."""

    def __init__(self, system_instruction: str, label_mapping: Dict[str, Any]) -> None:
        self.system_instruction = system_instruction
        self.label_mapping = {str(k).strip().lower(): v for k, v in label_mapping.items()}
        api_key = os.getenv(settings.GEMINI_API_KEY_ENV, "").strip()
        if not api_key:
            raise ValueError(
                f"No existe la variable de entorno '{settings.GEMINI_API_KEY_ENV}'."
            )
        self.client = genai.Client(api_key=api_key)
        self.model_name = settings.GEMINI_MODEL_NAME

    def classify(self, chunk: str, context: ClassificationContext) -> ClassificationResult:
        if not chunk or not chunk.strip():
            return ClassificationResult.no_match("chunk vacío")
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=chunk,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.0,
                    max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
                ),
            )
            raw = str(getattr(response, "text", "") or "").strip().lower()
        except Exception as exc:
            logger.warning("Gemini no pudo clasificar el chunk: %s", exc)
            return ClassificationResult.no_match("fallo_gemini")

        if not raw or raw == "desconocido":
            return ClassificationResult.no_match("gemini_sin_resultado")

        label = next((key for key in self.label_mapping if key == raw), None)
        if label is None:
            label = next((key for key in self.label_mapping if key in raw), None)
        if label is None:
            return ClassificationResult.no_match("gemini_etiqueta_fuera_taxonomia")

        return ClassificationResult(
            source=context.current_source,
            section=self.label_mapping[label],
            matched=True,
            reason="gemini",
        )
