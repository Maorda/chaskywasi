from enum import Enum
from pathlib import Path

from chaskiwasi.storage.chroma_persistent import ChromaPersistentManager


class Source(Enum):
    DOCUMENT = "document"


class Section(Enum):
    TITLE = "title"
    BODY = "body"


def test_chroma_persistent_manager_stores_classified_chunks(tmp_path: Path) -> None:
    manager = ChromaPersistentManager(persistence_path=str(tmp_path / "chroma_db"))

    manager.add_classified_chunks(
        collection_name="test_collection",
        doc_id="DOC-001",
        classified_chunks=[
            (Source.DOCUMENT, Section.TITLE, "Título del documento."),
            (Source.DOCUMENT, Section.BODY, "Contenido del documento."),
        ],
        plugin_name="demo",
    )

    collection = manager.get_or_create_collection("test_collection")
    result = collection.get()

    assert result["ids"] == ["demo_DOC-001_0", "demo_DOC-001_1"]
    assert result["metadatas"] == [
        {
            "id_documento": "DOC-001",
            "fuente": "document",
            "tipo_seccion": "title",
            "plugin": "demo",
        },
        {
            "id_documento": "DOC-001",
            "fuente": "document",
            "tipo_seccion": "body",
            "plugin": "demo",
        },
    ]


def test_add_classified_chunks_is_idempotent(tmp_path: Path) -> None:
    manager = ChromaPersistentManager(persistence_path=str(tmp_path / "chroma_db"))
    rows = [(Source.DOCUMENT, Section.BODY, "Contenido.")]

    manager.add_classified_chunks("test_collection", "DOC-001", rows, "demo")
    manager.add_classified_chunks("test_collection", "DOC-001", rows, "demo")

    result = manager.get_or_create_collection("test_collection").get()
    assert result["ids"] == ["demo_DOC-001_0"]
