"""Persistencia RAG de Chaskiwasi en ChromaDB."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

import chromadb
from chromadb.api.models.Collection import Collection

from chaskiwasi.config.settings import settings


class ChromaPersistentManager:
    """Gestiona documentos y chunks sin depender de una taxonomía global."""

    def __init__(self, persistence_path: Optional[str] = None) -> None:
        path = persistence_path or settings.CHROMA_PERSISTENT_PATH
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=path)

    def get_or_create_collection(self, collection_name: str) -> Collection:
        return self._client.get_or_create_collection(name=collection_name)

    def add_chunks(
        self,
        collection_name: str,
        doc_id: str,
        source: Any,
        chunks: Iterable[Tuple[Any, str]],
        plugin_name: Optional[str] = None,
    ) -> None:
        chunk_list = list(chunks)
        if not chunk_list:
            return

        collection = self.get_or_create_collection(collection_name)
        documents: List[str] = []
        metadatas: List[dict[str, str]] = []
        ids: List[str] = []

        for index, (section, text) in enumerate(chunk_list):
            metadata = {
                "id_documento": doc_id,
                "fuente": self._enum_value(source),
                "tipo_seccion": self._enum_value(section),
            }
            if plugin_name:
                metadata["plugin"] = plugin_name
            documents.append(text)
            metadatas.append(metadata)
            ids.append(f"{plugin_name or 'core'}_{doc_id}_{index}")

        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    def add_classified_chunks(
        self,
        collection_name: str,
        doc_id: str,
        classified_chunks: Iterable[Tuple[Any, Any, str]],
        plugin_name: Optional[str] = None,
    ) -> None:
        """Persiste chunks conservando la fuente y sección de cada chunk."""
        rows = list(classified_chunks)
        if not rows:
            return

        collection = self.get_or_create_collection(collection_name)
        documents: List[str] = []
        metadatas: List[dict[str, str]] = []
        ids: List[str] = []

        for index, (source, section, text) in enumerate(rows):
            metadata = {
                "id_documento": doc_id,
                "fuente": self._enum_value(source),
                "tipo_seccion": self._enum_value(section),
            }
            if plugin_name:
                metadata["plugin"] = plugin_name
            documents.append(text)
            metadatas.append(metadata)
            ids.append(f"{plugin_name or 'core'}_{doc_id}_{index}")

        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    @staticmethod
    def _enum_value(value: Any) -> str:
        return str(getattr(value, "value", value))
