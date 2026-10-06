"""Configuración inmutable y agnóstica del motor Chaskiwasi."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    CHUNK_SIZE: int = 256
    CHUNK_OVERLAP: int = 60
    TIKTOKEN_ENCODING: str = "cl100k_base"

    # LLM local: último recurso de clasificación.
    LLM_MODEL_NAME: str = "llama3.2:1b"
    OLLAMA_ENDPOINT: str = "http://localhost:11434/api/generate"
    OLLAMA_KEEP_ALIVE: int = 0

    # Gemini: fallback remoto opcional, con salida deliberadamente mínima.
    GEMINI_MODEL_NAME: str = "gemini-3.5-flash-lite"
    GEMINI_API_KEY_ENV: str = "GEMINI_API_KEY"
    GEMINI_MAX_OUTPUT_TOKENS: int = 8

    CHROMA_PERSISTENT_PATH: str = "./data/chroma_db"

    def __post_init__(self) -> None:
        if self.CHUNK_SIZE <= 0:
            raise ValueError("CHUNK_SIZE debe ser mayor que cero.")
        if self.CHUNK_OVERLAP < 0 or self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError("CHUNK_OVERLAP debe ser >= 0 y menor que CHUNK_SIZE.")
        if self.GEMINI_MAX_OUTPUT_TOKENS <= 0:
            raise ValueError("GEMINI_MAX_OUTPUT_TOKENS debe ser mayor que cero.")


settings = Settings()
