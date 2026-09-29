# D:\libs\chaskywasi\src\chaskiwasi\orchestration\trigger.py
import asyncio
import json
import sys
from pathlib import Path
from loguru import logger
from typing import List

# Importaciones cruzadas del ecosistema andino
from chaskitambo import ChaskitamboEngine, ChaskiDocument
from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.consolidation.consolidator import ChaskyConsolidator

# 🚀 CONECTOR MAESTRO CON QUIPU
try:
    from quipu.main import procesar_expediente_completo
    from quipu.config.settings import QuipuSettings
    _QUIPU_AVAILABLE = True
    logger.info("🚚 [SYSTEM] Librería de transporte 'quipu' acoplada con éxito al disparador.")
except ImportError:
    _QUIPU_AVAILABLE = False
    logger.warning("⚠️ [SYSTEM] La librería 'quipu' no está enlazada en este entorno virtual.")


class ChaskywasiTrigger:
    """
    Gatillador y Orquestador Supremo del ecosistema.
    
    Reside en chaskywasi y se encarga de despertar al motor de chaskitambo,
    recibir EN TIEMPO REAL cada documento mediante streaming de memoria,
    procesarlo por Docling e inyectarlo inmediatamente a NestJS usando quipu.
    """

    def __init__(self, cascade_factory: CascadeFactory, output_dir: str | Path = "./reportes_maestros"):
        self.cascade_factory = cascade_factory
        self.consolidator = ChaskyConsolidator(cascade_factory=self.cascade_factory)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def orchestrate_extraction_and_rag(self, global_id: str, plugin_names: List[str]):
        """
        Dispara el raspado paralelo en chaskitambo, procesando y despachando
        cada expediente de forma inmediata a medida que llegan a la RAM.
        """
        logger.info(f"🔮 [CHASKYWASI-TRIGGER] Iniciando ciclo de vida streaming para lote: {global_id}")
        
        # Inicializamos el motor de descubrimiento dinámico de chaskitambo
        tambo_engine = ChaskitamboEngine()
        
        # Cargamos las configuraciones de red globales de quipu (.env) de una sola vez
        settings_quipu = QuipuSettings() if _QUIPU_AVAILABLE else None
        
        # Contador interno para el control del stream en consola
        total_procesados_stream = 0

        # ----------------------------------------------------------------------
        # HANDLER SECUENCIAL EN CALIENTE (PROCESA Y TRANSMITE EN TIEMPO REAL)
        # ----------------------------------------------------------------------
        async def chaskywasi_sequential_handler(doc: ChaskiDocument):
            nonlocal total_procesados_stream
            logger.info(f"📥 [STREAM-HANDLER] Capturado remate en RAM -> ID: {doc.id_externo} | Fuente: {doc.fuente}")
            
            if not doc.pdf_bytes:
                logger.warning(f"⚠️ El documento {doc.id_externo} no contiene bytes de PDF válidos. Saltando.")
                return

            total_procesados_stream += 1
            
            # Estructura requerida por tu ChaskyConsolidator: {"identificador": bytes}
            id_tarjeta_individual = f"{doc.fuente}_{doc.id_externo}"
            payload_ram_individual = {id_tarjeta_individual: doc.pdf_bytes}
            
            # Definimos la ruta física individual del reporte Markdown para auditoría local
            reporte_individual_path = self.output_dir / f"master_{global_id}_{doc.id_externo}.json"

            try:
                # 1. Fase Semántica: Fragmentamos con Docling de forma inmediata
                logger.info(f"⚙️ [STREAM-RAG] Fragmentando estructuralmente con Docling el expediente: {doc.id_externo}")
                await asyncio.to_thread(
                    self.consolidator.build_master_expediente,
                    global_id=global_id,
                    data_sources=payload_ram_individual,
                    output_json_path=reporte_individual_path
                )
                logger.info(f"✨ [OK] Reporte estructural intermedio guardado en: {reporte_individual_path}")

                # 2. Fase de Red: Despachamos el pipeline de quipu hacia la nube y NestJS
                if _QUIPU_AVAILABLE and settings_quipu:
                    logger.info(f"🚚 [STREAM-QUIPU] Transmitiendo DTO a NestJS para expediente: {doc.id_externo}")
                    
                    mapa_fuente_virtual = {doc.fuente: f"memory://{doc.fuente}/{doc.id_externo}.pdf"}
                    
                    # CORREGIDO: Inyectamos el DTO real extraído de la ficha en el parámetro raw_data
                    pipeline_success = await procesar_expediente_completo(
                        global_id=doc.id_externo,
                        pdf_bytes=doc.pdf_bytes,
                        sources_paths=mapa_fuente_virtual,
                        raw_data=doc.metadatos.get("detalle", {}),  # <-- LLAVE CLAVE: Enviamos los datos reales capturados en RAM
                        settings=settings_quipu
                    )
                    
                    if pipeline_success:
                        logger.info(f"🎉 [STREAM-OK] Sincronización exitosa en NestJS para: {doc.id_externo}")
                    else:
                        logger.error(f"❌ El pipeline de quipu reportó fallos de transmisión para: {doc.id_externo}")
                else:
                    logger.warning(f"⚠️ Omitiendo despacho de red para {doc.id_externo}. Quipu no inicializado.")
                        
            except Exception:
                logger.exception(f"❌ Error crítico en el flujo streaming individual para la tarjeta {doc.id_externo}")

        # ----------------------------------------------------------------------
        # DISPARO CONCURRENTE HACIA EL MOTOR EXTERNO
        # ----------------------------------------------------------------------
        logger.info(f"🚀 [TRIGGER] Activando motores paralelos de chaskitambo para: {plugin_names}")
        try:
            # Invocamos la ejecución concurrente hacia chaskitambo
            await tambo_engine.run_plugins_parallel(
                plugin_names=plugin_names,
                chaskywasi_handler=chaskywasi_sequential_handler
            )
            
            if total_procesados_stream > 0:
                logger.info(f"✨ [TRIGGER] Orquestación por streaming finalizada. Total expedientes procesados: {total_procesados_stream}")
            else:
                logger.info("✨ [TRIGGER] Toda la bandeja web estaba al día. No se detectaron expedientes nuevos para transmitir.")
            
        except Exception:
            logger.exception("❌ Error crítico durante la ejecución paralela de la suite")
