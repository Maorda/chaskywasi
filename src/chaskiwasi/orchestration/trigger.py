# chaskiwasi/orchestration/trigger.py
import asyncio
import sys
from pathlib import Path
from loguru import logger
from typing import List

# Importaciones cruzadas de tus dos librerías andinas locales
from chaskitambo import ChaskitamboEngine, ChaskiDocument
from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.consolidation.consolidator import ChaskyConsolidator


class ChaskywasiTrigger:
    """
    Gatillador y Orquestador Supremo del ecosistema.
    
    Reside en chaskywasi y se encarga de despertar al motor de chaskitambo,
    recibir secuencialmente sus documentos en tiempo real mediante streaming de memoria,
    y enviarlos al pipeline de consolidación RAG (Docling + Cascade + ChromaDB).
    """

    def __init__(self, cascade_factory: CascadeFactory, output_dir: str | Path = "./reportes_maestros"):
        self.cascade_factory = cascade_factory
        self.consolidator = ChaskyConsolidator(cascade_factory=self.cascade_factory)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def orchestrate_extraction_and_rag(self, global_id: str, plugin_names: List[str]):
        """
        Dispara el raspado paralelo en chaskitambo y procesa los documentos 
        de forma secuencial a medida que van llegando en memoria.
        """
        logger.info(f"🔮 [CHASKYWASI-TRIGGER] Iniciando ciclo de vida para Expediente Global: {global_id}")
        
        # Inicializamos el motor de descubrimiento dinámico de chaskitambo
        tambo_engine = ChaskitamboEngine()
        
        # Diccionario interno para acumular los bytes recolectados por los productores paralelos
        # Estructura requerida por ChaskyConsolidator: {"nombre_fuente": bytes}
        collected_sources = {}

        # ----------------------------------------------------------------------
        # HANDLER SECUENCIAL: Este es el callback que ejecutará el consumidor de la cola
        # ----------------------------------------------------------------------
        async def chaskywasi_sequential_handler(doc: ChaskiDocument):
            logger.info(f"📥 [TRIGGER-HANDLER] Capturado flujo en RAM para ID Externo: {doc.id_externo} | Fuente: {doc.fuente}")
            
            if not doc.pdf_bytes:
                logger.warning(f"⚠️ El documento {doc.id_externo} no contiene bytes de PDF válidos. Saltando persistencia RAG.")
                return

            # Almacenamos el flujo binario usando una clave compuesta o la fuente directa
            key_identificador = f"{doc.fuente}_{doc.id_externo}"
            collected_sources[key_identificador] = doc.pdf_bytes
            
            # [OPCIONAL] Si quisieras insertar fragmentos directamente en ChromaDB en tiempo real 
            # línea por línea sin esperar al consolidador final, podrías mapear aquí tu ChromaPersistentManager.

        # ----------------------------------------------------------------------
        # DISPARO CONCURRENTE HACIA EL MOTOR EXTERNO
        # ----------------------------------------------------------------------
        logger.info(f"🚀 [TRIGGER] Despertando motores paralelos de chaskitambo para: {plugin_names}")
        try:
            # Forzamos la política de bucle proactor si estamos en Windows antes de lanzar Playwright de forma interna
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            # Invocamos el motor paralelo con salida secuencial que auditamos previamente
            await tambo_engine.run_plugins_parallel(
                plugin_names=plugin_names,
                chaskywasi_handler=chaskywasi_sequential_handler
            )
            
        except Exception:
            logger.exception("❌ Error crítico durante la recolección paralela de datos de chaskitambo")
            return

        # ----------------------------------------------------------------------
        # CONSOLIDACIÓN Y CLASIFICACIÓN RAG (DOCLING + CASCADE)
        # ----------------------------------------------------------------------
        if not collected_sources:
            logger.error("❌ No se logró recolectar ningún documento binario. Abortando consolidación.")
            return

        logger.info(f"⚙️ [TRIGGER] Iniciando Ingesta y Segmentación RAG para {len(collected_sources)} fuentes capturadas...")
        
        target_json_report = self.output_dir / f"master_{global_id}.json"
        
        try:
            # Ejecutamos de forma síncrona/bloqueante controlada el pipeline agnóstico de chaskywasi
            # pasando los archivos binarios directamente extraídos de la RAM
            await asyncio.to_thread(
                self.consolidator.build_master_expediente,
                global_id=global_id,
                data_sources=collected_sources,
                output_json_path=target_json_report
            )
            logger.info(f"✨ [OK] Pipeline completado de punta a punta. Reporte Maestro en: {target_json_report}")
            
        except Exception:
            logger.exception("❌ Falló la fase de consolidación y fragmentación RAG en el Consolidador")
