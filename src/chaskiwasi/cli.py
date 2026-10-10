
# src/chaskiwasi/cli.py

import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from chaskiwasi.contract import BaseExtractionConfig
from chaskiwasi.factory import ConfigurationFactory
from chaskiwasi.main import ExtractorDocumentalUniversal


app = typer.Typer(
    help="CLI oficial del motor de extracción documental Chaskiwasi.",
    no_args_is_help=True,
)

ingesta_app = typer.Typer(
    help="Comandos de ingesta documental.",
    no_args_is_help=True,
)

app.add_typer(ingesta_app, name="ingesta")


def _obtener_entry_points():
    """Obtiene los entry points de plugins compatibles con Python."""
    grupo_plugin = "chaskiwasi.plugins"

    if sys.version_info >= (3, 10):
        return importlib.metadata.entry_points(group=grupo_plugin)

    return importlib.metadata.entry_points().get(grupo_plugin, [])


def _crear_factory() -> ConfigurationFactory:
    """Crea la fábrica y verifica que existan plugins registrados."""
    factory = ConfigurationFactory()

    if not _obtener_entry_points():
        logger.error(
            "No se encontraron plugins instalados en "
            "'chaskiwasi.plugins'."
        )
        raise typer.Exit(code=1)

    return factory


def _resolver_carpeta(path: str) -> Path:
    """Valida y devuelve la ruta absoluta de una carpeta."""
    carpeta = Path(path).expanduser().resolve()

    if not carpeta.exists():
        logger.error(f"La ruta no existe: {carpeta}")
        raise typer.Exit(code=1)

    if not carpeta.is_dir():
        logger.error(f"La ruta no es una carpeta: {carpeta}")
        raise typer.Exit(code=1)

    archivos_pdf = [
        archivo
        for archivo in carpeta.iterdir()
        if archivo.is_file() and archivo.suffix.lower() == ".pdf"
    ]

    if not archivos_pdf:
        logger.error(f"No se encontraron archivos PDF en: {carpeta}")
        raise typer.Exit(code=1)

    return carpeta


def _ejecutar_plugin(plugin: str, path: str) -> None:
    """Ejecuta un plugin explícito sobre los PDF de una carpeta."""
    carpeta = _resolver_carpeta(path)
    factory = _crear_factory()

    try:
        config_activa = factory.obtener_por_clave(plugin)
    except (ValueError, KeyError) as exc:
        logger.error(f"No se pudo seleccionar el plugin '{plugin}': {exc}")
        raise typer.Exit(code=1) from exc

    if not isinstance(config_activa, BaseExtractionConfig):
        logger.error(
            f"El plugin '{plugin}' no devuelve una configuración "
            "compatible con BaseExtractionConfig."
        )
        raise typer.Exit(code=1)

    logger.info(f"Plugin seleccionado: {plugin}")
    logger.info(
        f"Configuración activa: {type(config_activa).__name__}"
    )
    logger.info(f"Carpeta de entrada: {carpeta}")

    procesador = ExtractorDocumentalUniversal(
        config=config_activa,
        carpeta_base=str(carpeta),
    )

    try:
        procesador.procesar_carpeta_local()
    except Exception as exc:
        logger.exception(
            f"Falló el procesamiento con el plugin '{plugin}': {exc}"
        )
        raise typer.Exit(code=1) from exc

    logger.success(
        f"Procesamiento finalizado. Carpeta de resultados: {carpeta}"
    )


@app.command("run", help="Ejecuta un plugin sobre una carpeta de PDF.")
def cmd_run(
    plugin: str = typer.Argument(
        ...,
        help="Clave del plugin instalado. Ejemplo: remaju.",
    ),
    path: str = typer.Option(
        ".",
        "--path",
        "-d",
        help="Carpeta con los PDF. Por defecto, la carpeta actual.",
    ),
):
    """
    Ejecuta el plugin indicado sin autodetección.

    Ejemplo:
        chaskiwasi run remaju
        chaskiwasi run remaju --path D:\\documentos\\remaju
    """
    _ejecutar_plugin(plugin=plugin, path=path)


@app.command("list", help="Lista los plugins instalados y sus versiones.")
def cmd_list():
    """Lista los plugins y comprueba su herencia del contrato base."""
    logger.info(
        "Inspeccionando plugins registrados en 'chaskiwasi.plugins'..."
    )

    entry_points = _obtener_entry_points()

    if not entry_points:
        logger.warning("No se encontraron plugins instalados.")
        return

    encabezado = (
        f"\n{'PLUGIN (Clave)':<25} | "
        f"{'PAQUETE DISTRIBUCIÓN':<30} | "
        f"{'VERSIÓN':<12} | "
        f"{'ESTADO CONTRATO':<25}\n"
    )
    tabla = encabezado + "-" * 100 + "\n"

    for ep in entry_points:
        plugin_key = ep.name
        dist_name = ep.dist.name if ep.dist else "Desconocido"
        version = ep.dist.version if ep.dist else "N/A"

        try:
            config_cls = ep.load()

            if not isinstance(config_cls, type):
                raise TypeError(
                    "El entry point no apunta a una clase."
                )

            if not issubclass(config_cls, BaseExtractionConfig):
                raise TypeError(
                    "La clase no hereda de BaseExtractionConfig."
                )

            # Comprueba también que la configuración pueda instanciarse.
            config_cls()

            estado = "Válido"
        except Exception as exc:
            estado = "Inválido"
            logger.warning(
                f"Plugin '{plugin_key}': {exc}"
            )

        tabla += (
            f"{plugin_key:<25} | "
            f"{dist_name:<30} | "
            f"{version:<12} | "
            f"{estado:<25}\n"
        )

    tabla += "-" * 100 + "\n"
    print(tabla)


@ingesta_app.command("pdf", help="Procesa una carpeta de PDF.")
def cmd_ingesta_pdf(
    path: str = typer.Argument(
        ...,
        help="Ruta a una carpeta que contiene archivos PDF.",
    ),
    plugin: Optional[str] = typer.Option(
        None,
        "--plugin",
        "-p",
        help="Clave del plugin. Si se omite, se usa la autodetección "
             "del primer PDF.",
    ),
):
    """
    Mantiene el comando anterior de ingesta por compatibilidad.

    Con --plugin, utiliza esa configuración explícitamente.
    Sin --plugin, selecciona la configuración según el primer PDF.
    """
    carpeta = _resolver_carpeta(path)
    factory = _crear_factory()

    if plugin:
        try:
            config_activa = factory.obtener_por_clave(plugin)
        except (ValueError, KeyError) as exc:
            logger.error(
                f"No se pudo seleccionar el plugin '{plugin}': {exc}"
            )
            raise typer.Exit(code=1) from exc
    else:
        import pymupdf as fitz

        primer_pdf = next(
            archivo
            for archivo in sorted(carpeta.iterdir())
            if archivo.is_file()
            and archivo.suffix.lower() == ".pdf"
        )

        try:
            with fitz.open(str(primer_pdf)) as documento:
                texto_muestra = (
                    documento[0].get_text()
                    if len(documento) > 0
                    else ""
                )

            config_activa = factory.autodetectar_configuracion(
                texto_muestra
            )
        except Exception as exc:
            logger.error(f"No se pudo detectar el plugin: {exc}")
            raise typer.Exit(code=1) from exc

    if not isinstance(config_activa, BaseExtractionConfig):
        logger.error(
            "La configuración seleccionada no cumple el contrato base."
        )
        raise typer.Exit(code=1)

    logger.info(
        f"Configuración seleccionada: {type(config_activa).__name__}"
    )

    procesador = ExtractorDocumentalUniversal(
        config=config_activa,
        carpeta_base=str(carpeta),
    )

    try:
        procesador.procesar_carpeta_local()
    except Exception as exc:
        logger.exception(f"Falló la ingesta: {exc}")
        raise typer.Exit(code=1) from exc

    logger.success("Ingesta finalizada.")


if __name__ == "__main__":
    app()
