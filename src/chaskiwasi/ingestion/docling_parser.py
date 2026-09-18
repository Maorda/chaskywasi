# dantesito/chasky/ingestion/docling_parser.py
from pathlib import Path
from typing import Optional

from docling.document_converter import DocumentConverter, ConversionResult


class DoclingParser:
    """
    Orquestador de extracción de documentos para dantesito-chasky.
    Procesa PDFs mediante el pipeline de Docling y persiste el resultado en Markdown
    directamente a disco para minimizar el impacto en memoria volátil (RAM).
    """

    def __init__(self, converter: Optional[DocumentConverter] = None) -> None:
        """
        Inicializa el convertidor de Docling. Permite la inyección de una instancia
        personalizada para facilitación de pruebas unitarias o configuraciones avanzadas.
        """
        self._converter: DocumentConverter = converter or DocumentConverter()

    def parse_to_markdown(self, pdf_path: str, output_md_path: str) -> str:
        """
        Procesa un archivo PDF en `pdf_path`, extrae su estructura en formato Markdown
        y la escribe inmediatamente en el archivo físico en `output_md_path`.

        Args:
            pdf_path: Ruta del archivo PDF de entrada.
            output_md_path: Ruta del archivo Markdown de salida.

        Returns:
            str: Contenido extraído en formato Markdown.

        Raises:
            FileNotFoundError: Si el archivo PDF especificado no existe.
            ValueError: Si la ruta de entrada no es un PDF o el documento no se puede procesar.
        """
        input_path = Path(pdf_path)
        output_path = Path(output_md_path)

        if not input_path.is_file():
            raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")

        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"El archivo especificado no es un PDF válido: {pdf_path}")

        try:
            result: ConversionResult = self._converter.convert(str(input_path))
            markdown_content: str = result.document.export_to_markdown()

            # Asegurar la creación del directorio padre si no existe
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Volcado directo a disco para mantener un footprint mínimo de memoria
            output_path.write_text(markdown_content, encoding="utf-8")

            return markdown_content

        except Exception as e:
            if isinstance(e, (FileNotFoundError, ValueError)):
                raise
            raise ValueError(
                f"Error al procesar y convertir el archivo PDF '{pdf_path}': {str(e)}"
            ) from e