# src/chaskiwasi/bridge.py
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from chaskitambo import ChaskiDocument
from chaskiwasi.factory import ConfigurationFactory
from chaskiwasi.main import ExtractorDocumentalUniversal


def fusionar_json_alta_fidelidad(scraper_metadata: Dict[str, Any], ai_extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fusiona el JSON nativo extraído del portal web por Playwright con el 
    JSON estructurado y validado por la Inteligencia Artificial (Gemini / Pydantic).
    """
    registro_unificado = dict(scraper_metadata)
    datos_ia = ai_extraction_result.get("datos_extraidos", {})
    
    expediente_ia = datos_ia.get("numero_expediente")
    if expediente_ia and expediente_ia != "No detectado":
        if "remate" in registro_unificado:
            registro_unificado["remate"]["expediente"] = expediente_ia
        else:
            registro_unificado["numero_expediente"] = expediente_ia

    if datos_ia.get("demandantes"):
        registro_unificado["demandantes_validados_ia"] = datos_ia["demandantes"]
    if datos_ia.get("demandados"):
        registro_unificado["demandados_validados_ia"] = datos_ia["demandados"]

    registro_unificado["resolucion_judicial_analisis"] = {
        "direccion_inmueble": datos_ia.get("direccion"),
        "requiere_cartel": datos_ia.get("requiere_cartel", False),
        "campos_faltantes_ia": ai_extraction_result.get("campos_faltantes", []),
        "completado_exitosamente": ai_extraction_result.get("completado_exitosamente", False)
    }
    
    return registro_unificado


class ChaskitamboChaskiwasiBridge:
    """
    Adaptador que conecta los flujos asíncronos en streaming de ChaskiDocument (Chaskitambo)
    con el pipeline inteligente de 4 capas de Chaskiwasi.
    """
    def __init__(self, output_dir: str = "./salida_unificada"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        factory = ConfigurationFactory()
        if not factory.claves_disponibles:
            raise RuntimeError("No se detectaron plugins de configuración en 'chaskiwasi.configs'.")
            
        self.extractor_universal = ExtractorDocumentalUniversal(
            config=None,
            carpeta_base=str(self.output_dir),
            factory=factory
        )

    async def handle_document(self, document: ChaskiDocument) -> None:
        """
        Método adaptador que actúa como 'chaskywasi_handler' para ChaskitamboEngine.
        """
        id_ext = document.id_externo
        fuente = document.fuente
        pdf_bytes = document.pdf_bytes
        nombre_sugerido = document.nombre_archivo_sugerido
        scraper_metadata = document.metadatos.get("detalle", {})

        logger.info(f" -> [BRIDGE] Procesando documento en streaming ID: {id_ext} | Fuente: {fuente}")

        if not pdf_bytes:
            logger.warning(f"[-] El documento {id_ext} no contiene bytes válidos. Omitiendo análisis...")
            return

        # 1. Procesar el PDF mediante el motor de 4 capas de Chaskiwasi
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

        # 2. Extracción profunda asistida por IA (Gemini)
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

        # 3. Fusión de Alta Fidelidad
        registro_fusionado = fusionar_json_alta_fidelidad(scraper_metadata, resultado_ia)
        registro_fusionado["id_externo"] = id_ext
        registro_fusionado["fuente"] = fuente

        # 4. Persistencia
        self._guardar_json_salida(id_ext, registro_fusionado)
        logger.success(f"[✓] Registro unificado generado y almacenado con éxito para ID: {id_ext}")

    def _guardar_json_salida(self, id_ext: str, data: Dict[str, Any]):
        ruta_destino = self.output_dir / f"{id_ext}_unificado.json"
        with open(ruta_destino, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)