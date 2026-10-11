import asyncio
import logging
from typing import Dict, Any
from .models import MemoryContext
# Llamk'achisunmi ConfigurationFactory nisqata plugin-kuna tarinapaq
from chaskiwasi.factory import ConfigurationFactory

logger = logging.getLogger("chaskiwasi.orchestrator")

class InMemoryOrchestrator:
    def __init__(self, config: Dict[str, Any], factory: ConfigurationFactory = None):
        self.config = config
        # ConfigurationFactory nisqaqa ñam entry points nisqamanta plugin-kunata hapimun
        self.factory = factory or ConfigurationFactory()

    async def run_pipeline(self) -> MemoryContext:
        pipeline_name = self.config.get("pipeline_name", "default_pipeline")
        logger.info(f"Iniciando pipeline in-memory: '{pipeline_name}'")

        # Qallariy kontekstota RAM-pi kamaspa
        contexto = MemoryContext(
            execution_id="EXP-2026-001",
            primary_source_name="",
            status="running"
        )

        # YAML nisqamanta pipeline pasos nisqakunata liyiy
        steps = self.config.get("pipeline", [])

        for step in steps:
            plugin_name = step.get("plugin")
            parameters = step.get("parameters", {})
            
            logger.info(f"-> Activando plugin en RAM: '{plugin_name}'")
            
            try:
                # Factory nisqawan plugin-ta tarina otaq apaykachana
                # (Qhaway: ConfigurationFactory-niykipaqhina huk metodo kanqa plugin clase maskhanapaq)
                plugin_cls = self.factory.obtener_clase_plugin(plugin_name) 
                
                # Plugin-ta kamaspa parameters nisqakunawan
                plugin_instance = plugin_cls(parameters=parameters)
                
                # RAM kontekstota pasaspa plugin-ta purichina
                contexto = await plugin_instance.execute(contexto)
                
                logger.info(f"<- Plugin '{plugin_name}' finalizado con éxito.")
                
            except Exception as e:
                logger.error(f"Error crítico en el plugin '{plugin_name}': {e}")
                contexto.status = "error"
                contexto.error_logs.append(f"[{plugin_name}] {str(e)}")
                raise

        contexto.status = "completed"
        logger.info("Pipeline in-memory completado en su totalidad.")
        return contexto