# src/chaskiwasi/bridge.py
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from chaskitambo import ChaskiDocument
from chaskiwasi.factory import ConfigurationFactory
from chaskiwasi.main import ExtractorDocumentalUniversal


class ChaskitamboChaskiwasiBridge:
    """
    Adaptador universal y agnóstico que conecta los flujos en streaming de Chaskitambo
    con el motor de análisis de Chaskiwasi, delegando las reglas de negocio a cada plugin.
    """
    def __init__(self, output_dir: str = "./salida_unificada"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.factory = ConfigurationFactory()
        if not self.factory.claves_disponibles:
            raise RuntimeError("No se detectaron plugins de configuración en 'chaskiwasi.configs'.")
            
        self.extractor_universal = ExtractorDocumentalUniversal(
            config=None,
            carpeta_base=str(self.output_dir),
            factory=self.factory
        )

    async def handle_document(self, document: ChaskiDocument) -> None:
        """
        Método adaptador universal que procesa cualquier ChaskiDocument independiente de su fuente.
        """
        id_ext = document.id_externo
        fuente = document.fuente
        pdf_bytes = document.pdf_bytes
        nombre_sugerido = document.nombre_archivo_sugerido
        scraper_metadata = document.metadatos.get("detalle", document.metadatos)

        logger.info(f" -> [BRIDGE] Procesando documento ID: {id_ext} | Fuente: {fuente}")

        if not pdf_bytes:
            logger.warning(f"[-] El documento {id_ext} no contiene bytes válidos. Omitiendo...")
            return

        # 1. Seleccionar la configuración específica basada en la fuente del documento (ej. 'remaju', 'sunarp')
        config_plugin = self.factory.obtener_por_clave(fuente)
        if not config_plugin:
            logger.error(f"[-] No se encontró una configuración de Chaskiwasi para la fuente '{fuente}'.")
            return

        # Asignar la configuración activa al procesador universal
        self.extractor_universal.config = config_plugin
        self.extractor_universal.json_schema = config_plugin.json_schema
        self.extractor_universal.palabras_clave = list(config_plugin.palabras_clave)

        # 2. Procesar el PDF mediante el motor de 4 capas
        resultado_lectura = self.extractor_universal.procesar_pdf_desde_bytes(pdf_bytes, nombre_sugerido)
        
        if resultado_lectura.get("requiere_revision_manual"):
            logger.warning(f"[-] Documento {id_ext} derivado a revisión manual. Motivo: {resultado_lectura.get('motivo')}")
            self._guardar_json_salida(id_ext, {
                "id_externo": id_ext,
                "fuente": fuente,
                "metadatos_scraper": scraper_metadata,
                "requiere_revision_manual": True,
                "motivo": resultado_lectura.get("motivo")
            })
            return

        # 3. Extracción profunda asistida por IA (Gemini) usando el esquema del plugin
        if resultado_lectura.get("modo_vision_multimodal"):
            resultado_ia = self.extractor_universal.ejecutar_extraccion_gemini(
                resultado_lectura["contenido_payload"],
                es_archivo_completo=True,
                nombre_archivo=nombre_sugerido
            )
        else:
            resultado_ia = self.extractor_universal.ejecutar_extraccion_gemini(
                resultado_lectura["contenido_payload"],
                es_archivo_completo=False
            )

        # 4. POLIMORFISMO: Delegar la fusión de datos exclusivamente al plugin activo
        registro_fusionado = config_plugin.fusionar_datos(scraper_metadata, resultado_ia)
        
        # Inyectar metadatos estándar de trazabilidad
        registro_fusionado["id_externo"] = id_ext
        registro_fusionado["fuente"] = fuente

        # 5. Persistencia del resultado unificado
        self._guardar_json_salida(id_ext, registro_fusionado)
        logger.success(f"[✓] Registro unificado generado y almacenado con éxito para ID: {id_ext}")

    def _guardar_json_salida(self, id_ext: str, data: Dict[str, Any]):
        ruta_destino = self.output_dir / f"{id_ext}_unificado.json"
        with open(ruta_destino, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)