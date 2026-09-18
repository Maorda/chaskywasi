# dantesito/chasky/config/settings.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """
    Configuración global inmutable para el motor dantesito-chasky.
    Diseñada con restricciones estrictas de bajo consumo en memoria RAM.
    """
    CHUNK_SIZE: int = 256
    CHUNK_OVERLAP: int = 60
    TIKTOKEN_ENCODING: str = "cl100k_base"
    LLM_MODEL_NAME: str = "llama3.2:1b"
    OLLAMA_KEEP_ALIVE: int = 0
    CHROMA_PERSISTENT_PATH: str = "./data/chroma_db"


settings = Settings()