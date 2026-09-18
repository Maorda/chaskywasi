# tests/test_chroma_persistent.py

from pathlib import Path
from typing import List, Tuple

import pytest

from chaskiwasi.config.taxonomy_registry import SectionEnum, SourceEnum
from chaskiwasi.storage.chroma_persistent import ChromaPersistentManager


def test_chroma_persistent_manager_stores_chunks_and_taxonomy(
    tmp_path: Path,
) -> None:
    persistence_path: Path = tmp_path / "chroma_db"

    manager = ChromaPersistentManager(
        persistence_path=str(persistence_path),
    )

    collection_name: str = "test_collection"
    doc_id: str = "documento_test_001"

    chunks: List[Tuple[SectionEnum, str]] = [
        (SectionEnum.ENCABEZADO, "Información del remate judicial."),
        (SectionEnum.RESOLUCION, "Resolución judicial del remate."),
        (SectionEnum.PARTES, "Demandante y demandado."),
        (SectionEnum.GRAVAMEN, "Gravámenes registrados."),
    ]

    manager.add_chunks(
        collection_name=collection_name,
        doc_id=doc_id,
        source=SourceEnum.SUNARP,
        chunks=chunks,
    )

    collection = manager.get_or_create_collection(collection_name)
    result = collection.get()

    assert result["ids"] == [
        f"{doc_id}_0",
        f"{doc_id}_1",
        f"{doc_id}_2",
        f"{doc_id}_3",
    ]

    assert result["documents"] == [
        "Información del remate judicial.",
        "Resolución judicial del remate.",
        "Demandante y demandado.",
        "Gravámenes registrados.",
    ]

    assert result["metadatas"] == [
        {
            "id_documento": doc_id,
            "fuente": SourceEnum.SUNARP.value,
            "tipo_seccion": SectionEnum.ENCABEZADO.value,
        },
        {
            "id_documento": doc_id,
            "fuente": SourceEnum.SUNARP.value,
            "tipo_seccion": SectionEnum.RESOLUCION.value,
        },
        {
            "id_documento": doc_id,
            "fuente": SourceEnum.SUNARP.value,
            "tipo_seccion": SectionEnum.PARTES.value,
        },
        {
            "id_documento": doc_id,
            "fuente": SourceEnum.SUNARP.value,
            "tipo_seccion": SectionEnum.GRAVAMEN.value,
        },
    ]

    assert persistence_path.exists()
    assert any(persistence_path.iterdir())


def test_add_chunks_with_empty_list_does_not_write_data(
    tmp_path: Path,
) -> None:
    manager = ChromaPersistentManager(
        persistence_path=str(tmp_path / "chroma_db"),
    )

    manager.add_chunks(
        collection_name="empty_collection",
        doc_id="documento_vacio",
        source=SourceEnum.REMAJU,
        chunks=[],
    )

    collection = manager.get_or_create_collection("empty_collection")
    result = collection.get()

    assert result["ids"] == []
    assert result["documents"] == []
    assert result["metadatas"] == []