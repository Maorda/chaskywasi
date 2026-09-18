import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from chaskiwasi.consolidation.consolidator import ChaskyConsolidator


@pytest.fixture
def mock_cascade_factory():
    """Simula el comportamiento de CascadeFactory."""
    factory = MagicMock()
    factory.process_chunks_batch.return_value = [
        ("SUNARP", "ENCABEZADO"),
        ("SUNARP", "PARTES"),
    ]
    return factory


@pytest.fixture
def mock_converter():
    """Simula el convertidor de Docling para evitar cargar modelos reales."""
    converter = MagicMock()
    doc_result = MagicMock()
    doc_result.document.export_to_markdown.return_value = (
        "# Encabezado Registral\n\nTexto de las partes involucradas."
    )
    converter.convert.return_value = doc_result
    return converter


@pytest.fixture
def consolidator(mock_cascade_factory, mock_converter):
    """Instancia limpia de ChaskyConsolidator con dependencias simuladas."""
    return ChaskyConsolidator(
        cascade_factory=mock_cascade_factory,
        converter=mock_converter,
    )


# =====================================================================
# 1. PRUEBAS DE INICIALIZACIÓN
# =====================================================================

def test_init_defaults():
    """Verifica que se instancien las dependencias por defecto si no se inyectan."""
    with patch("chaskiwasi.consolidation.consolidator.CascadeFactory") as mock_cf, patch(
        "chaskiwasi.consolidation.consolidator.DocumentConverter"
    ) as mock_dc:
        instance = ChaskyConsolidator()
        assert instance._cascade_factory is not None
        assert instance._converter is not None


# =====================================================================
# 2. PRUEBAS DE EXTRACCIÓN DE PDF (DOCLING)
# =====================================================================

def test_extract_pdf_chunks_from_bytes(consolidator, mock_converter):
    """Verifica la extracción de bloques Markdown desde bytes en RAM."""
    pdf_bytes = b"%PDF-1.4 Fake PDF Content"
    chunks = consolidator._extract_pdf_chunks(pdf_bytes)

    assert len(chunks) == 2
    assert chunks[0] == "# Encabezado Registral"
    assert chunks[1] == "Texto de las partes involucradas."
    mock_converter.convert.assert_called_once()


def test_extract_pdf_chunks_from_path(consolidator, mock_converter):
    """Verifica la extracción desde un archivo en disco."""
    chunks = consolidator._extract_pdf_chunks("documento.pdf")

    assert len(chunks) == 2
    mock_converter.convert.assert_called_with("documento.pdf")


def test_extract_pdf_chunks_exception_returns_empty_list(consolidator, mock_converter):
    """Verifica la resiliencia ante fallos del motor de conversión de Docling."""
    mock_converter.convert.side_effect = RuntimeError("Fallo al procesar PDF")
    chunks = consolidator._extract_pdf_chunks("corrupto.pdf")

    assert chunks == []


# =====================================================================
# 3. PRUEBAS DE INGESTIÓN JSON (IJSON)
# =====================================================================

@patch("ijson.items")
def test_ingest_json_generic_from_bytes(mock_ijson_items, consolidator):
    """Verifica el procesamiento de JSONs en bytes."""
    mock_ijson_items.return_value = iter([{"id": 1}, {"id": 2}])
    json_bytes = b'[{"id": 1}, {"id": 2}]'

    result = consolidator._ingest_json_generic(json_bytes)

    assert result["file"] == "stream_ram.json"
    assert len(result["records"]) == 2
    assert result["records"][0]["id"] == 1


@patch("ijson.items")
@patch("pathlib.Path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b'[{"id": 10}]')
def test_ingest_json_generic_from_file(mock_file, mock_exists, mock_ijson_items, consolidator):
    """Verifica el procesamiento de JSONs en disco."""
    mock_ijson_items.return_value = iter([{"id": 10}])

    result = consolidator._ingest_json_generic("datos.json")

    assert result["file"] == "datos.json"
    assert result["records"] == [{"id": 10}]


def test_ingest_json_generic_file_not_found(consolidator):
    """Verifica que un archivo inexistente retorne una estructura vacía sin lanzar excepción."""
    result = consolidator._ingest_json_generic("archivo_inexistente.json")

    assert result["file"] == "archivo_inexistente.json"
    assert result["records"] == []


# =====================================================================
# 4. PRUEBAS DE ORQUESTACIÓN Y GENERACIÓN DEL REPORTE MAESTRO
# =====================================================================

def test_ingest_document_batch(consolidator, mock_cascade_factory):
    """Verifica el procesamiento en lote y mapeo de secciones de un documento."""
    result = consolidator._ingest_document_batch("expediente.pdf", "SUNARP")

    assert result["file"] == "expediente.pdf"
    assert len(result["sections"]) == 2
    assert result["sections"][0]["source"] == "SUNARP"
    assert result["sections"][0]["section"] == "ENCABEZADO"
    mock_cascade_factory.process_chunks_batch.assert_called_once()


@patch("ijson.items")
def test_build_master_expediente_e2e(
    mock_ijson_items, consolidator, mock_cascade_factory, tmp_path: Path
):
    """Verifica la construcción y persistencia completa del expediente maestro en disco."""
    mock_ijson_items.return_value = iter([{"record": 1}])
    output_file = tmp_path / "resultado_consolidado.json"

    data_sources = {
        "canal_json": b'[{"record": 1}]',
        "canal_sunarp": "sunarp_document.pdf",
    }

    consolidator.build_master_expediente(
        global_id="EXP-2026-001",
        data_sources=data_sources,
        output_json_path=output_file,
    )

    assert output_file.exists()

    with open(output_file, "r", encoding="utf-8") as f:
        master_data = json.load(f)

    assert master_data["global_id"] == "EXP-2026-001"
    assert master_data["metadatos_proceso"]["total_fuentes"] == 2
    assert "canal_json" in master_data
    assert "canal_sunarp" in master_data
    assert len(master_data["canal_sunarp"]["sections"]) == 2