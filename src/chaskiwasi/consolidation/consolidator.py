import gc
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter

from chaskiwasi.classification.cascade_factory import CascadeFactory

logger = logging.getLogger(__name__)


class ChaskyConsolidator:
    """
    Motor core agnóstico de consolidación y clasificación de legajos RAG.
    
    No posee acoplamiento con taxonomías fijas. Procesa flujos dinámicos en RAM (bytes)
    o archivos en disco, delegando la estrategia de clasificación al `CascadeFactory` inyectado.
    """

    def __init__(
        self,
        cascade_factory: Optional[CascadeFactory] = None,
        converter: Optional[DocumentConverter] = None,
    ) -> None:
        self._cascade_factory = cascade_factory or CascadeFactory()
        self._converter = converter or DocumentConverter()

    def build_master_expediente(
        self,
        global_id: str,
        data_sources: Dict[str, Union[str, Path, bytes]],
        output_json_path: Union[str, Path],
    ) -> None:
        """
        Construye el reporte maestro consolidado procesando múltiples fuentes de datos.
        """
        logger.info(f"🚀 [CHASKY-CORE] Inicializando pipeline agnóstico para el lote: {global_id}")

        master_data: Dict[str, Any] = {
            "global_id": global_id,
            "metadatos_proceso": {"total_fuentes": len(data_sources)},
        }

        for key_fuente, source_data in data_sources.items():
            logger.info(f"[CHASKY-CORE] Procesando canal de información: '{key_fuente}'")

            is_json_bytes = isinstance(source_data, bytes) and source_data.lstrip().startswith((b"[", b"{"))

            if "json" in key_fuente.lower() or is_json_bytes:
                master_data[key_fuente] = self._ingest_json_generic(source_data)
            else:
                master_data[key_fuente] = self._ingest_document_batch(source_data, key_fuente)

        output_path = Path(output_json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(master_data, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 Reporte Maestro consolidado guardado con éxito en: {output_json_path}")

        del master_data
        gc.collect()

    def _ingest_json_generic(self, json_source: Union[str, Path, bytes]) -> Dict[str, Any]:
        """Procesa flujos JSON estructurados mediante streaming con ijson."""
        import ijson

        items = []
        file_name = "stream_ram.json" if isinstance(json_source, bytes) else Path(json_source).name

        try:
            if isinstance(json_source, bytes):
                with io.BytesIO(json_source) as stream:
                    parser = ijson.items(stream, "item")
                    for item in parser:
                        items.append(item)
                return {"file": file_name, "records": items}

            json_path = Path(json_source)
            if not json_path.exists():
                return {"file": json_path.name, "records": []}

            with open(json_path, "rb") as stream:
                parser = ijson.items(stream, "item")
                for item in parser:
                    items.append(item)
            return {"file": json_path.name, "records": items}

        except Exception as err:
            logger.error(f"Error en extracción genérica JSON para {file_name}: {err}")
            return {"file": file_name, "records": []}

    def _ingest_document_batch(
        self,
        doc_source: Union[str, Path, bytes],
        source_label: str,
    ) -> Dict[str, Any]:
        """Extrae y clasifica fragmentos de documentos por lotes (Batching)."""
        file_name = "stream_ram.pdf" if isinstance(doc_source, bytes) else Path(doc_source).name

        try:
            lista_completa_chunks = self._extract_pdf_chunks(doc_source)
            if not lista_completa_chunks:
                return {"file": file_name, "sections": []}

            sections_found: List[Dict[str, Any]] = []

            resultados_batch = self._cascade_factory.process_chunks_batch(
                lista_completa_chunks,
                current_source=source_label,
            )

            active_context = source_label
            for i, chunk in enumerate(lista_completa_chunks):
                detected_source, section = resultados_batch[i]

                if detected_source is not None:
                    active_context = getattr(detected_source, "value", str(detected_source))

                section_value = getattr(section, "value", str(section)) if section is not None else None

                sections_found.append({
                    "chunk": chunk,
                    "source": active_context,
                    "section": section_value,
                })

            return {"file": file_name, "sections": sections_found}

        except Exception as err:
            logger.error(f"Error en procesamiento masivo del documento {file_name}: {err}")
            return {"file": file_name, "sections": []}

    def _extract_pdf_chunks(self, doc_source: Union[str, Path, bytes]) -> List[str]:
        """Extrae texto plano Markdown utilizando Docling alimentándose de memoria o disco."""
        chunks: List[str] = []
        try:
            if isinstance(doc_source, bytes):
                with io.BytesIO(doc_source) as stream:
                    doc_stream = DocumentStream(name="stream_in_memory.pdf", stream=stream)
                    doc_result = self._converter.convert(doc_stream)
            else:
                doc_result = self._converter.convert(str(doc_source))

            markdown_text = doc_result.document.export_to_markdown()
            if markdown_text:
                chunks = [c.strip() for c in markdown_text.split("\n\n") if c.strip()]

            del doc_result
        except Exception as err:
            logger.warning(f"No se pudo extraer el contenido vía Docling: {err}")

        return chunks