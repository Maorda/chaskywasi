# tests/test_docling_parser.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from chaskiwasi.ingestion.docling_parser import DoclingParser


def test_parse_to_markdown_success(tmp_path: Path) -> None:
    """
    Verifica el flujo exitoso de conversión de un PDF a Markdown, comprobando la
    correcta simulación de Docling y la persistencia física en el disco duro.
    """
    fake_pdf = tmp_path / "documento_test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 mock content")

    output_md = tmp_path / "resultado.md"
    expected_markdown = "# Título Legal\n\nEste es un texto extraído."

    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = expected_markdown

    mock_converter = MagicMock()
    mock_converter.convert.return_value = mock_result

    parser = DoclingParser(converter=mock_converter)
    result_text = parser.parse_to_markdown(str(fake_pdf), str(output_md))

    mock_converter.convert.assert_called_once_with(str(fake_pdf))
    assert result_text == expected_markdown
    assert output_md.is_file()
    assert output_md.read_text(encoding="utf-8") == expected_markdown


def test_parse_to_markdown_file_not_found(tmp_path: Path) -> None:
    """
    Verifica que se lance FileNotFoundError cuando el PDF especificado no existe.
    """
    non_existent_pdf = tmp_path / "archivo_inexistente.pdf"
    output_md = tmp_path / "salida.md"

    parser = DoclingParser()

    with pytest.raises(FileNotFoundError) as exc_info:
        parser.parse_to_markdown(str(non_existent_pdf), str(output_md))

    assert f"El archivo PDF no existe en la ruta: {non_existent_pdf}" in str(
        exc_info.value
    )


def test_parse_to_markdown_invalid_extension(tmp_path: Path) -> None:
    """
    Verifica que se lance ValueError cuando el archivo de entrada no tiene extensión .pdf.
    """
    invalid_file = tmp_path / "documento.txt"
    invalid_file.write_text("contenido de texto")
    output_md = tmp_path / "salida.md"

    parser = DoclingParser()

    with pytest.raises(ValueError) as exc_info:
        parser.parse_to_markdown(str(invalid_file), str(output_md))

    assert "no es un PDF válido" in str(exc_info.value)


def test_parse_to_markdown_conversion_failure(tmp_path: Path) -> None:
    """
    Verifica el manejo de excepciones cuando el convertidor interno de Docling
    falla por corrupción o error interno.
    """
    fake_pdf = tmp_path / "corrupto.pdf"
    fake_pdf.write_bytes(b"corrupted pdf data")
    output_md = tmp_path / "salida.md"

    mock_converter = MagicMock()
    mock_converter.convert.side_effect = RuntimeError("PDF invalido o dañado")

    parser = DoclingParser(converter=mock_converter)

    with pytest.raises(ValueError) as exc_info:
        parser.parse_to_markdown(str(fake_pdf), str(output_md))

    assert "Error al procesar y convertir el archivo PDF" in str(exc_info.value)
    assert "PDF invalido o dañado" in str(exc_info.value)