# D:\libs\chaskywasi\src\chaskiwasi\ingestion\consolidator.py

"""Pipeline documental: Docling -> Markdown -> chunks -> clasificación -> JSON."""

from __future__ import annotations

import gc
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter

from chaskiwasi.chunking.chunk_tokenizer import ChunkTokenizer
from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.plugins.registry import PluginRegistry
from chaskiwasi.storage.chroma_persistent import ChromaPersistentManager


logger = logging.getLogger(__name__)


class ChaskyConsolidator:
    """Motor de ingestión y consolidación documental propiedad de Chaskiwasi."""

    def __init__(
        self,
        cascade_factory: Optional[CascadeFactory] = None,
        converter: Optional[DocumentConverter] = None,
        tokenizer: Optional[ChunkTokenizer] = None,
        rag_manager: Optional[ChromaPersistentManager] = None,
        rag_collection_name: str = "chaskiwasi",
    ) -> None:
        self._cascade_factory = cascade_factory
        self._converter = converter or DocumentConverter()
        self._tokenizer = tokenizer or ChunkTokenizer()
        self._rag_manager = rag_manager or ChromaPersistentManager()
        self._rag_collection_name = rag_collection_name

    def build_master_expediente(
        self,
        global_id: str,
        data_sources: Dict[str, Union[str, Path, bytes]],
        output_json_path: Union[str, Path],
        plugin_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Procesa documentos y devuelve el JSON consolidado; opcionalmente lo persiste."""

        factory = self._resolve_factory(plugin_name)

        master_data: Dict[str, Any] = {
            "global_id": global_id,
            "plugin": plugin_name,
            "metadatos_proceso": {
                "total_fuentes": len(data_sources),
            },
        }

        for source_label, source_data in data_sources.items():
            if self._is_json_source(source_label, source_data):
                master_data[source_label] = self._ingest_json_generic(
                    source_data
                )
            else:
                master_data[source_label] = self._ingest_document_batch(
                    source_data,
                    source_label,
                    factory,
                    plugin_name,
                    global_id,
                )

        if output_json_path:
            output_path = Path(output_json_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(
                    master_data,
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )

        gc.collect()

        return master_data

    def _resolve_factory(
        self,
        plugin_name: Optional[str],
    ) -> CascadeFactory:
        if self._cascade_factory is not None:
            return self._cascade_factory

        if not plugin_name:
            raise ValueError(
                "Se necesita plugin_name cuando no se inyecta un CascadeFactory."
            )

        return PluginRegistry.build_cascade_factory(plugin_name)

    @staticmethod
    def _is_json_source(
        source_label: str,
        source_data: Union[str, Path, bytes],
    ) -> bool:
        if "json" in source_label.lower():
            return True

        return (
            isinstance(source_data, bytes)
            and source_data.lstrip().startswith((b"[", b"{"))
        )

    def _ingest_json_generic(
        self,
        json_source: Union[str, Path, bytes],
    ) -> Dict[str, Any]:
        import ijson

        records: List[Any] = []

        file_name = (
            "stream_ram.json"
            if isinstance(json_source, bytes)
            else Path(json_source).name
        )

        if isinstance(json_source, bytes):
            with io.BytesIO(json_source) as stream:
                records.extend(
                    ijson.items(stream, "item")
                )
        else:
            path = Path(json_source)

            if not path.exists():
                raise FileNotFoundError(
                    f"El archivo JSON no existe: {path}"
                )

            with path.open("rb") as stream:
                records.extend(
                    ijson.items(stream, "item")
                )

        return {
            "file": file_name,
            "records": records,
        }

    def _ingest_document_batch(
        self,
        doc_source: Union[str, Path, bytes],
        source_label: str,
        cascade_factory: CascadeFactory,
        plugin_name: Optional[str],
        document_id: str,
    ) -> Dict[str, Any]:
        file_name = (
            "stream_ram.pdf"
            if isinstance(doc_source, bytes)
            else Path(doc_source).name
        )

        # ------------------------------------------------------------------
        # 1. Docling -> Markdown
        # ------------------------------------------------------------------
        markdown = self._extract_markdown(doc_source)

        # ------------------------------------------------------------------
        # 2. Markdown -> chunks
        # ------------------------------------------------------------------
        chunks = self._tokenizer.split_text(markdown)

        if not chunks:
            return {
                "file": file_name,
                "markdown": markdown,
                "sections": [],
                "extraccion": {
                    "remate": {
                        "demandantes": [],
                        "demandados": [],
                    },
                    "inmuebles": [
                        {
                            "direccion": "",
                            "requiere_cartel": False,
                        }
                    ],
                }
                if plugin_name
                and PluginRegistry.get(plugin_name).extractor is not None
                else None,
            }

        # ------------------------------------------------------------------
        # 3. Resolver source
        # ------------------------------------------------------------------
        source = self._resolve_source(
            cascade_factory,
            source_label,
        )

        # ------------------------------------------------------------------
        # 4. Clasificación
        # ------------------------------------------------------------------
        results = cascade_factory.process_chunks_batch(
            chunks,
            current_source=source,
        )

        # ------------------------------------------------------------------
        # 5. Conservar cada chunk con su clasificación
        # ------------------------------------------------------------------
        sections: List[Dict[str, Any]] = []
        classified_rows = []

        for chunk, classification in zip(chunks, results):
            detected_source, section = classification

            section_value = self._enum_value(section)
            source_value = self._enum_value(detected_source)

            row = {
                "chunk": chunk,
                "source": source_value,
                "section": section_value,
            }

            sections.append(row)

            if section is not None:
                classified_rows.append(
                    (
                        detected_source,
                        section,
                        chunk,
                    )
                )

        # ------------------------------------------------------------------
        # 6. Resultado base
        # ------------------------------------------------------------------
        result: Dict[str, Any] = {
            "file": file_name,
            "sections": sections,
        }

        # ------------------------------------------------------------------
        # 7. Persistencia RAG
        # ------------------------------------------------------------------
        self._rag_manager.add_classified_chunks(
            collection_name=self._rag_collection_name,
            doc_id=document_id,
            classified_chunks=classified_rows,
            plugin_name=plugin_name,
        )

        # ------------------------------------------------------------------
        # 8. Extracción del plugin
        #
        # IMPORTANTE:
        # `markdown` sigue siendo la fuente documental completa.
        #
        # No se sustituye por HEADER/BODY/FOOTER porque una clasificación
        # incorrecta de un chunk no debe destruir información necesaria para
        # la extracción jurídica.
        # ------------------------------------------------------------------
        if plugin_name:
            plugin = PluginRegistry.get(plugin_name)

            if plugin.extractor is not None:
                from chaskiwasi.plugins.contracts import ExtractionContext
                from chaskiwasi.plugins.registry import plugin_context

                grouped = self._group_sections(sections)

                extraction_metadata = {
                    "source_label": source_label,
                    "file_name": file_name,

                    # Fuente completa original producida por Docling.
                    "document_markdown": markdown,

                    # Información de clasificación.
                    "classified_chunk_count": len(sections),

                    # Facilita diagnóstico y extracción especializada.
                    "classified_sections": sections,

                    # Mantener compatibilidad con extractores existentes.
                    "source": self._enum_value(source),
                }

                extraction_context = ExtractionContext(
                    plugin=plugin_context(plugin),
                    document_id=document_id,
                    text=markdown,
                    sections=grouped,
                    metadata=extraction_metadata,
                )

                result["extraccion"] = plugin.extractor(
                    extraction_context
                )

        return result

    @staticmethod
    def _group_sections(
        sections: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Agrupa chunks por sección.

        El orden original de los chunks se conserva.
        """
        grouped: Dict[str, str] = {}

        for item in sections:
            key = str(
                item.get("section")
                or "desconocido"
            )

            chunk = str(
                item.get("chunk")
                or ""
            ).strip()

            if not chunk:
                continue

            if key not in grouped:
                grouped[key] = chunk
            else:
                grouped[key] = (
                    f"{grouped[key]}\n{chunk}"
                ).strip()

        return grouped

    def _extract_markdown(
        self,
        doc_source: Union[str, Path, bytes],
    ) -> str:
        """
        Convierte el documento mediante Docling y devuelve Markdown.

        Se mantiene el comportamiento original.
        """
        if isinstance(doc_source, bytes):
            with io.BytesIO(doc_source) as stream:
                doc_stream = DocumentStream(
                    name="stream_in_memory.pdf",
                    stream=stream,
                )

                result = self._converter.convert(
                    doc_stream
                )
        else:
            path = Path(doc_source)

            if not path.exists():
                raise FileNotFoundError(
                    f"El documento no existe: {path}"
                )

            result = self._converter.convert(
                str(path)
            )

        markdown = (
            result.document.export_to_markdown()
            or ""
        )

        del result

        return markdown

    @staticmethod
    def _resolve_source(
        factory: CascadeFactory,
        source_label: str,
    ) -> Any:
        if factory.plugin_context is None:
            return source_label

        enum_class = (
            factory.plugin_context
            .taxonomy
            .source_enum
        )

        try:
            return enum_class(source_label)
        except ValueError:
            for member in enum_class:
                if member.name.lower() == source_label.lower():
                    return member

        return source_label

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return getattr(
            value,
            "value",
            value,
        )