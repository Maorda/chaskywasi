"""Consulta semántica RAG propiedad de Chaskiwasi."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from chaskiwasi.query_engine.cross_filter import CrossQueryFilter

if TYPE_CHECKING:
    from chaskiwasi.storage.chroma_persistent import ChromaPersistentManager


class RagQueryEngine:
    """Ejecuta recuperación semántica sobre la colección persistente de Chroma."""

    def __init__(
        self,
        collection_name: str,
        manager: Optional[ChromaPersistentManager] = None,
        query_filter: Optional[CrossQueryFilter] = None,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name no puede estar vacío.")
        self.collection_name = collection_name
        if manager is None:
            from chaskiwasi.storage.chroma_persistent import ChromaPersistentManager

            manager = ChromaPersistentManager()
        self.manager = manager
        self.query_filter = query_filter or CrossQueryFilter()

    def search(
        self,
        query_text: str,
        *,
        doc_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
        n_results: int = 5,
    ) -> Dict[str, Any]:
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("query_text no puede estar vacío.")
        if n_results <= 0:
            raise ValueError("n_results debe ser mayor que cero.")

        collection = self.manager.get_or_create_collection(self.collection_name)
        where = self.query_filter.generate_where_clause(
            query_text=query_text,
            doc_id=doc_id,
            plugin_name=plugin_name,
        )

        kwargs: Dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        return collection.query(**kwargs)
