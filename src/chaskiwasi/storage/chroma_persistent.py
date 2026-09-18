# dantesito/chasky/storage/chroma_persistent.py

from pathlib import Path
from typing import List, Optional, Tuple

import chromadb
from chromadb.api.models.Collection import Collection

from chaskiwasi.config.settings import Settings
from chaskiwasi.config.taxonomy_registry import SectionEnum, SourceEnum


class ChromaPersistentManager:
    """Gestiona el almacenamiento persistente de fragmentos en ChromaDB."""

    def __init__(
        self,
        persistence_path: Optional[str] = None,
    ) -> None:
        path: str = (
            persistence_path
            if persistence_path is not None
            else Settings.CHROMA_PERSISTENT_PATH
        )

        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=path)

    def get_or_create_collection(self, collection_name: str) -> Collection:
        """Obtiene o crea una colección usando la configuración nativa de ChromaDB."""
        return self._client.get_or_create_collection(
            name=collection_name,
        )

    def add_chunks(
        self,
        collection_name: str,
        doc_id: str,
        source: SourceEnum,
        chunks: List[Tuple[SectionEnum, str]],
    ) -> None:
        """Agrega fragmentos y su taxonomía estricta a una colección."""
        if not chunks:
            return

        collection: Collection = self.get_or_create_collection(collection_name)

        documents: List[str] = []
        metadatas: List[dict[str, str]] = []
        ids: List[str] = []

        for idx, (section, text) in enumerate(chunks):
            documents.append(text)
            metadatas.append(
                {
                    "id_documento": doc_id,
                    "fuente": source.value,
                    "tipo_seccion": section.value,
                }
            )
            ids.append(f"{doc_id}_{idx}")

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )