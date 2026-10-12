import sys
import asyncio
from pathlib import Path
import typer
from loguru import logger
import yaml
import importlib.metadata
from chaskiwasi.contract import BaseExtractionConfig
app = typer.Typer(help="Motor orquestador central de Chaskiwasi basado en Pipelines YAML.")

class PipelineOrchestrator:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Caché en memoria exclusiva para esta ejecución: { "plugin_name": { "llave_valor": [datos_o_bytes] } }
        self.cache_enriquecimientos = {}
        # Locks asíncronos por cada fuente y llave para evitar condiciones de carrera simultáneas
        self.locks = {}

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            logger.error(f"[-] No se encontró el archivo de configuración en: {self.config_path}")
            raise typer.Exit(code=1)
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _get_nested_value(self, data: dict, dotted_path: str):
        """
        Resuelve rutas anidadas de forma 100% agnóstica. 
        Soporta diccionarios, índices numéricos (ej. '0') y proyección automática 
        si encuentra una lista de objetos intermendia.
        Ejemplo: 'detalle.inmuebles.partidaRegistral' extrae todas las partidas 
        de la lista de inmuebles de forma transparente, sin que el CLI conozca el dominio.
        """
        parts = dotted_path.split(".")
        current = data
        
        for i, part in enumerate(parts):
            if current is None:
                return None
                
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                if part.isdigit():
                    idx = int(part)
                    current = current[idx] if len(current) > idx else None
                else:
                    # PROYECCIÓN GENÉRICA: Si encontramos una lista y la ruta continúa,
                    # recorremos cada elemento de la lista extrayendo la sub-ruta restante.
                    remaining_path = ".".join(parts[i+1:])
                    results = []
                    for item in current:
                        val = self._get_nested_value(item, remaining_path)
                        if val is not None:
                            if isinstance(val, list):
                                for sub_v in val:
                                    if sub_v not in results:
                                        results.append(sub_v)
                            elif val not in results:
                                results.append(val)
                    return results if results else None
            else:
                return None
                
        # Si el resultado final es un valor único, lo normalizamos a lista si el pipeline lo requiere, 
        # o lo retornamos tal cual.
        return current

    async def obtener_o_ejecutar_enriquecimiento(
        self, engine, bridge, plugin_name: str, match_key: str, match_value: str, cardinality: str, plugin_params: dict, param_name: str = None, expediente_valor: str = None
    ):
        if plugin_name not in self.cache_enriquecimientos:
            self.cache_enriquecimientos[plugin_name] = {}
            self.locks[plugin_name] = {}

        if match_value not in self.locks[plugin_name]:
            self.locks[plugin_name][match_value] = asyncio.Lock()

        async with self.locks[plugin_name][match_value]:
            # 1. Comprobar Caché en Memoria (RAM)
            if match_value in self.cache_enriquecimientos[plugin_name]:
                logger.info(f"   ⚡ [CACHE HIT] '{plugin_name}' para '{match_key}: {match_value}' recuperado de la RAM.")
                return self.cache_enriquecimientos[plugin_name][match_value]

            # 2. Ejecutar Scraper en vivo
            logger.info(f"   🌐 [CACHE MISS] Ejecutando '{plugin_name}' para [{match_key}: {match_value}]...")
            
            elementos_capturados = []

            async def interceptor_secundario(doc_sec):
                elementos_capturados.append(doc_sec)
                if cardinality == "one-to-one":
                    await bridge.handle_document(doc_sec)

            # 🎯 INYECCIÓN 100% AGNÓSTICA: Pasamos parámetros + partida + expediente resuelto
            kwargs_ejecucion = dict(plugin_params)
            if param_name and match_value:
                kwargs_ejecucion[param_name] = match_value
            if expediente_valor:
                kwargs_ejecucion["expediente"] = expediente_valor

            await engine.run_plugins_parallel(
                [plugin_name], 
                chaskywasi_handler=interceptor_secundario,
                plugin_kwargs={plugin_name: kwargs_ejecucion}
            )

            self.cache_enriquecimientos[plugin_name][match_value] = elementos_capturados
            return elementos_capturados

@app.command("list", help="Lista los plugins instalados y sus versiones.")
def cmd_list():
    """Lista los plugins instalados, su versión y verifica el cumplimiento del contrato."""
    logger.info("Inspeccionando plugins registrados en 'chaskiwasi.plugins'...")
    
    grupo_plugin = "chaskiwasi.plugins"
    entry_points = importlib.metadata.entry_points(group=grupo_plugin) if sys.version_info >= (3, 10) else importlib.metadata.entry_points().get(grupo_plugin, [])

    if not entry_points:
        logger.warning("No se encontraron plugins instalados en el entorno.")
        return

    tabla = f"\n{'PLUGIN (Clave)':<25} | {'PAQUETE DISTRIBUCIÓN':<30} | {'VERSIÓN':<10} | {'ESTADO CONTRATO':<15}\n"
    tabla += "-" * 88 + "\n"

    for ep in entry_points:
        plugin_key = ep.name
        dist_name = ep.dist.name if ep.dist else "Desconocido"
        version = ep.dist.version if ep.dist and ep.dist.version else "N/A"

        cumple_contrato = False
        try:
            config_cls = ep.load()
            if issubclass(config_cls, BaseExtractionConfig):
                cumple_contrato = True
        except Exception as e:
            logger.debug(f"Error cargando plugin '{plugin_key}': {e}")

        estado = "✅ Válido" if cumple_contrato else "❌ Inválido (Falla contrato)"
        tabla += f"{plugin_key:<25} | {dist_name:<30} | {version:<10} | {estado:<15}\n"
    
    tabla += "-" * 88 + "\n"
    print(tabla)

@app.command("run", help="Ejecuta un pipeline inteligente basado en un archivo YAML de configuración.")
def run_pipeline(
    config: str = typer.Option(..., "--config", "-c", help="Ruta al archivo YAML de configuración del pipeline")
):
    """
    Ejecución maestra:
    Ejemplo: chaskiwasi run --config pipeline_remate.yaml
    """
    async def _run():
        from chaskitambo.core.engine import ChaskitamboEngine
        from chaskiwasi.bridge import ChaskitamboChaskiwasiBridge

        orchestrator = PipelineOrchestrator(config)
        cfg = orchestrator.config

        engine = ChaskitamboEngine()
        target_cfg = cfg.get("target", {})
        bridge = ChaskitamboChaskiwasiBridge(output_dir=target_cfg.get("output_dir", "./salida_unificada"))

        primary_cfg = cfg.get("primary_source", {})
        primary_plugin = primary_cfg.get("plugin")
        extraction_keys = primary_cfg.get("extraction_keys", {})
        
        # 🟢 1. Extraer los parámetros configurados en el YAML para la fuente primaria
        primary_params = primary_cfg.get("parameters", {})

        logger.info(f" -> [PIPELINE] Iniciando '{cfg.get('pipeline_name')}' (Fuente primaria: {primary_plugin})")

        # 1. Capturar elementos de la fuente primaria
        registros_principales = []

        async def interceptor_principal(doc):
            registros_principales.append(doc)
            logger.info(f" -> [{primary_plugin.upper()}] Documento principal capturado: ID {doc.id_externo}")

        logger.info(f" -> [FASE 1] Ejecutando fuente primaria '{primary_plugin}' con parámetros {primary_params}...")
        
        # 🟢 2. Inyectar los parámetros a la ejecución paralela del motor
        await engine.run_plugins_parallel(
            [primary_plugin], 
            chaskywasi_handler=interceptor_principal,
            plugin_kwargs={primary_plugin: primary_params}
        )

        # 2. Procesar enriquecimientos declarados en el YAML
        enrichments = cfg.get("enrichments", [])

        for doc_prin in registros_principales:
            metadatos_doc = doc_prin.metadatos or {}
            
            # 🟢 Extraer de forma agnóstica el expediente usando la configuración de extraction_keys
            expediente_dotted_path = extraction_keys.get("expediente", "expediente")
            expediente_valor = orchestrator._get_nested_value(metadatos_doc, expediente_dotted_path) or doc_prin.id_externo

            # Contenedor unificado en memoria para el JSON Maestro de este expediente
            paquete_maestro = {
                "documento_principal": doc_prin,
                "enriquecimientos": {}
            }

            for enrich in enrichments:
                p_name = enrich.get("plugin")
                cardinality = enrich.get("cardinality", "one-to-many")
                match_field_key = enrich.get("match_with")
                enrich_params = enrich.get("parameters", {})
                param_name = enrich.get("param_name") # Obtenido puramente del YAML

                dotted_path = extraction_keys.get(match_field_key, match_field_key)
                match_value = orchestrator._get_nested_value(metadatos_doc, dotted_path) or metadatos_doc.get(match_field_key)

                if not match_value:
                    logger.warning(f"[-] El documento {doc_prin.id_externo} no encontró la clave '{match_field_key}'. Omitiendo '{p_name}'.")
                    continue

                resultados_enriquecimiento = await orchestrator.obtener_o_ejecutar_enriquecimiento(
                    engine=engine,
                    bridge=bridge,
                    plugin_name=p_name,
                    match_key=match_field_key,
                    match_value=match_value,
                    cardinality=cardinality,
                    plugin_params=enrich_params,
                    param_name=param_name,
                    expediente_valor=expediente_valor  # 🟢 Inyectamos el expediente capturado por el orquestador
                )

                paquete_maestro["enriquecimientos"][p_name] = {
                    "llave_usada": match_field_key,
                    "valor_llave": match_value,
                    "cardinality": cardinality,
                    "items": resultados_enriquecimiento
                }

            # 3. Consolidación Final en Memoria y Envío al Bridge de Chaskiwasi
            logger.info(f" -> [MAESTRO] Consolidando expediente {doc_prin.id_externo} con sus fuentes secundarias...")
            await bridge.handle_pipeline_maestro(paquete_maestro)

        logger.success(f"[★★★ PIPELINE '{cfg.get('pipeline_name')}' COMPLETADO CON ÉXITO ★★★]")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.warning(" -> [CLI] Ejecución del pipeline interrumpida manualmente por el usuario.")

if __name__ == "__main__":
    app()