import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chaskiwasi.consolidation.consolidator import ChaskyConsolidator


@pytest.fixture
def mock_cascade_factory():
    factory = MagicMock()
    factory.process_chunks_batch.return_value = [
        ("SUNARP", "ENCABEZADO"),
        ("SUNARP", "PARTES"),
    ]
    factory.plugin_context = None
    return factory


@pytest.fixture
def mock_converter():
    converter = MagicMock()
    doc_result = MagicMock()
    doc_result.document.export_to_markdown.return_value = (
        "# Encabezado Registral\n\nTexto de las partes involucradas."
    )
    converter.convert.return_value = doc_result
    return converter


@pytest.fixture
def mock_rag_manager():
    return MagicMock()


@pytest.fixture
def consolidator(mock_cascade_factory, mock_converter, mock_rag_manager):
    return ChaskyConsolidator(
        cascade_factory=mock_cascade_factory,
        converter=mock_converter,
        rag_manager=mock_rag_manager,
    )


def test_init_keeps_cascade_factory_lazy():
    with patch("chaskiwasi.consolidation.consolidator.DocumentConverter") as mock_dc, patch(
        "chaskiwasi.consolidation.consolidator.ChunkTokenizer"
    ) as mock_tokenizer, patch(
        "chaskiwasi.consolidation.consolidator.ChromaPersistentManager"
    ) as mock_rag:
        instance = ChaskyConsolidator()

    assert instance._cascade_factory is None
    assert instance._converter is mock_dc.return_value
    assert instance._tokenizer is mock_tokenizer.return_value
    assert instance._rag_manager is mock_rag.return_value


def test_extract_markdown_from_bytes(consolidator, mock_converter):
    pdf_bytes = b"%PDF-1.4 Fake PDF Content"

    markdown = consolidator._extract_markdown(pdf_bytes)

    assert markdown == "# Encabezado Registral\n\nTexto de las partes involucradas."
    mock_converter.convert.assert_called_once()


def test_extract_markdown_from_path_requires_existing_file(
    consolidator, mock_converter, tmp_path: Path
):
    pdf_path = tmp_path / "documento.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 Fake PDF Content")

    markdown = consolidator._extract_markdown(pdf_path)

    assert markdown.startswith("# Encabezado Registral")
    mock_converter.convert.assert_called_once_with(str(pdf_path))


def test_extract_markdown_propagates_conversion_exception(consolidator, mock_converter):
    mock_converter.convert.side_effect = RuntimeError("Fallo al procesar PDF")

    with pytest.raises(RuntimeError, match="Fallo al procesar PDF"):
        consolidator._extract_markdown(b"%PDF-1.4 Fake PDF Content")


@patch("ijson.items")
def test_ingest_json_generic_from_bytes(mock_ijson_items, consolidator):
    mock_ijson_items.return_value = iter([{"id": 1}, {"id": 2}])

    result = consolidator._ingest_json_generic(b'[{"id": 1}, {"id": 2}]')

    assert result == {
        "file": "stream_ram.json",
        "records": [{"id": 1}, {"id": 2}],
    }


@patch("ijson.items")
def test_ingest_json_generic_from_file(mock_ijson_items, consolidator, tmp_path: Path):
    mock_ijson_items.return_value = iter([{"id": 10}])
    json_path = tmp_path / "datos.json"
    json_path.write_bytes(b'[{"id": 10}]')

    result = consolidator._ingest_json_generic(json_path)

    assert result == {"file": "datos.json", "records": [{"id": 10}]}


def test_ingest_json_generic_file_not_found(consolidator, tmp_path: Path):
    missing_path = tmp_path / "archivo_inexistente.json"

    with pytest.raises(FileNotFoundError, match="El archivo JSON no existe"):
        consolidator._ingest_json_generic(missing_path)


def test_ingest_document_batch(consolidator, mock_cascade_factory, tmp_path: Path):
    pdf_path = tmp_path / "expediente.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 Fake PDF Content")

    with patch.object(
        consolidator._tokenizer,
        "split_text",
        return_value=["chunk 1", "chunk 2"],
    ):
        result = consolidator._ingest_document_batch(
            pdf_path,
            "SUNARP",
            mock_cascade_factory,
            None,
            "EXP-001",
        )

    assert result["file"] == "expediente.pdf"
    assert len(result["sections"]) == 2
    assert result["sections"][0]["source"] == "SUNARP"
    assert result["sections"][0]["section"] == "ENCABEZADO"
    mock_cascade_factory.process_chunks_batch.assert_called_once_with(
        ["chunk 1", "chunk 2"],
        current_source="SUNARP",
    )
    consolidator._rag_manager.add_classified_chunks.assert_called_once()


@patch("ijson.items")
def test_build_master_expediente_e2e(
    mock_ijson_items,
    consolidator,
    mock_cascade_factory,
    tmp_path: Path,
):
    mock_ijson_items.return_value = iter([{"record": 1}])
    output_file = tmp_path / "resultado_consolidado.json"
    pdf_path = tmp_path / "sunarp_document.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 Fake PDF Content")
    data_sources = {
        "canal_json": b'[{"record": 1}]',
        "canal_sunarp": pdf_path,
    }

    with patch.object(
        consolidator._tokenizer,
        "split_text",
        return_value=["chunk 1", "chunk 2"],
    ):
        consolidator.build_master_expediente(
            global_id="EXP-2026-001",
            data_sources=data_sources,
            output_json_path=output_file,
        )

    assert output_file.exists()
    master_data = json.loads(output_file.read_text(encoding="utf-8"))

    assert master_data["global_id"] == "EXP-2026-001"
    assert master_data["metadatos_proceso"]["total_fuentes"] == 2
    assert "canal_json" in master_data
    assert "canal_sunarp" in master_data
    assert len(master_data["canal_sunarp"]["sections"]) == 2
