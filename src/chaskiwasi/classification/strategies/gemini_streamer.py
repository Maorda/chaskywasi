import logging
import os
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import types

from chaskiwasi.classification.strategies.base_strategy import BaseStrategy

logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("google.genai._api_client").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class GeminiStreamer(BaseStrategy):
    """Estrategia de inferencia remota en la nube totalmente agnóstica al dominio."""

    def __init__(
        self,
        system_instruction: str,
        label_mapping: Dict[str, Any],
    ) -> None:
        self.system_instruction = system_instruction
        self.label_mapping = label_mapping
        
        api_key = ""
        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_key:
            api_key = env_key

        if not api_key:
            env_path = ".env"
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line.startswith("GEMINI_API_KEY"):
                            try:
                                parsed_tokens = clean_line.split("=", 1)
                                if len(parsed_tokens) == 2:
                                    parsed_key = parsed_tokens[1].strip().strip('"').strip("'")
                                    if parsed_key:
                                        api_key = parsed_key
                                        break
                            except Exception:
                                pass

        if not api_key or not (api_key.startswith("AIzaSy") or api_key.startswith("AQ.")):
            raise ValueError(
                "🚨 ERROR CRÍTICO DE CONFIGURACIÓN: La variable 'GEMINI_API_KEY' "
                "no está definida en el entorno ni en el archivo .env raíz."
            )

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3.5-flash-lite"

    def classify(
        self, chunk_text: str, current_source: Optional[Any] = None
    ) -> Tuple[Optional[Any], Optional[Any]]:
        if not chunk_text or not chunk_text.strip():
            return None, None

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=chunk_text,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.1,
                ),
            )

            if not response or not hasattr(response, "text") or not response.text:
                logger.warning("Respuesta vacía o no válida recibida de la API de Gemini.")
                return None, None

            label = response.text.strip().lower()

            if label == "desconocido":
                return None, None

            section_enum = self.label_mapping.get(label)
            if section_enum is None:
                logger.warning(
                    "Etiqueta desconocida o fuera de taxonomía devuelta por Gemini: '%s'", label
                )
                return None, None

            # Asumimos que Gemini por ahora solo devuelve la sección, manteniendo la firma original
            return None, section_enum

        except Exception as e:
            logger.error(
                "Error durante la inferencia remota con el cliente Google GenAI: %s",
                str(e),
                exc_info=True,
            )
            return None, None