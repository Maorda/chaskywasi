# src/chaskiwasi/cli.py
import os
import sys
import asyncio
import importlib.metadata
import pymupdf as fitz
import typer
from loguru import logger

from chaskiwasi.contract import BaseExtractionConfig
from chaskiwasi.factory import ConfigurationFactory
from chaskiwasi.main import ExtractorDocumentalUniversal
from chaskiwasi.bridge import ChaskitamboChaskiwasiBridge
from chaskitambo.core.engine import ChaskitamboEngine

app = typer.Typer(help="CLI oficial del motor de extracción documental Chaskiwasi.")
ingesta_app = typer.Typer(help="Comandos de ingesta documental.")
app.add_typer(ingesta_app, name="ingesta")


@app.command("list", help="Lista los plugins instalados y sus versiones.")
def cmd_list():
    """Lista los plugins instalados, su versión y verifica el cumplimiento del contrato."""
    logger.info("Inspeccionando plugins registrados en 'chaskiwasi.configs'...")
    
    grupo_plugin = "chaskiwasi.configs"
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


@ingesta_app.command("pdf", help="Ingestar documentos PDF desde una ruta o carpeta local.")
def cmd_ingesta_pdf(
    path: str = typer.Argument(..., help="Ruta al archivo PDF individual o carpeta."),
    plugin: str = typer.Option(None, "--plugin", "-p", help="Clave del plugin específico.")
):
    """Procesa un archivo PDF o carpeta de PDFs utilizando el motor universal."""
    ruta_objetivo = os.path.abspath(path)
    
    if not os.path.exists(ruta_objetivo):
        logger.error(f"La ruta '{ruta_objetivo}' no existe.")
        raise typer.Exit(code=1)

    factory = ConfigurationFactory()
    
    if os.path.isfile(ruta_objetivo) and ruta_objetivo.lower().endswith(".pdf"):
        logger.info(f"Procesando archivo individual: {ruta_objetivo}")
        doc = fitz.open(ruta_objetivo)
        texto_muestra = doc[0].get_text() if len(doc) > 0 else ""
        doc.close()

        config_activa = factory.obtener_por_clave(plugin) if plugin else factory.autodetectar_configuracion(texto_muestra)
        procesador = ExtractorDocumentalUniversal(config=config_activa, carpeta_base=os.path.dirname(ruta_objetivo))
        
        logger.info(f"Usando configuración: {config_activa.__class__.__name__}")
        resultado = procesador.verificar_y_filtrar_pdf(ruta_objetivo)
        logger.success(f"Resultado del filtrado inicial: {resultado}")

    elif os.path.isdir(ruta_objetivo):
        logger.info(f"Procesando lote en carpeta: {ruta_objetivo}")
        procesador = ExtractorDocumentalUniversal(config=None, carpeta_base=ruta_objetivo, factory=factory)
        procesador.procesar_carpeta_local()
    else:
        logger.error("La ruta proporcionada no es un archivo PDF válido ni una carpeta.")
        raise typer.Exit(code=1)


@ingesta_app.command("web", help="Ejecuta un plugin de raspado de Chaskitambo y procesa los documentos en streaming.")
def cmd_ingesta_web(
    plugin: str = typer.Argument(..., help="Nombre del plugin de Chaskitambo a ejecutar (ej. remaju).")
):
    """Gatilla el motor Chaskitambo desde Chaskiwasi aplicando el pipeline de análisis de 4 capas y fusión."""
    async def _run():
        engine = ChaskitamboEngine()
        bridge = ChaskitamboChaskiwasiBridge(output_dir="./salida_unificada")
        
        logger.info(f" -> [CHASKIWASI MASTER] Activando extractor web Chaskitambo con el plugin: '{plugin}'")
        await engine.run_plugins_parallel([plugin], chaskywasi_handler=bridge.handle_document)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.warning(" -> [CLI] Ejecución de ingesta web interrumpida manualmente.")


if __name__ == "__main__":
    app()