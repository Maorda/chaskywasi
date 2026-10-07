# D:\libs\chaskywasi\src\chaskiwasi\cli.py

"""CLI del motor Chaskiwasi, sin dependencias sobre orquestadores externos."""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
from pathlib import Path
from typing import Any

from rich import print
from rich.table import Table

from chaskiwasi.config.settings import settings
from chaskiwasi.orchestration.trigger import ChaskiwasiTrigger
from chaskiwasi.plugins.registry import PluginRegistry


def _obtener_mapa_versiones_entry_points() -> dict[str, str]:
    """Obtiene un diccionario {nombre_plugin: version} desde los Entry Points de 'chaskiwasi.plugins'."""
    mapa_versiones: dict[str, str] = {}
    try:
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            plugin_eps = eps.select(group="chaskiwasi.plugins")
        elif isinstance(eps, dict):
            plugin_eps = eps.get("chaskiwasi.plugins", [])
        else:
            plugin_eps = []

        for ep in plugin_eps:
            dist = getattr(ep, "dist", None)
            if dist and getattr(dist, "version", None):
                mapa_versiones[ep.name] = dist.version
    except Exception:
        pass
    return mapa_versiones


def _obtener_version_plugin(
    plugin_name: str,
    plugin: Any,
    ep_versions: dict[str, str],
) -> str:
    """Resuelve la versión exacta del plugin usando una cadena de fallbacks precisa."""
    # 1. Primera prioridad: Versión según el Entry Point de pip/poetry (ej. 'remaju' -> '0.2.0')
    if plugin_name in ep_versions:
        return ep_versions[plugin_name]

    # 2. Atributos explícitos en el objeto plugin (si el plugin define .version o .VERSION)
    version = getattr(plugin, "version", None) or getattr(plugin, "VERSION", None)
    if version:
        return str(version)

    # 3. Inspección del módulo de la clase real (evitando paquetes base de chaskiwasi)
    obj_type = type(plugin) if not isinstance(plugin, type) else plugin
    module_name = getattr(obj_type, "__module__", "") or getattr(plugin, "__module__", "")

    if module_name and not module_name.startswith("chaskiwasi."):
        root_package = module_name.split(".")[0]

        # Mapear módulo importado (chaskiwasi_plugin_remaju) a distribución PyPI (chaskiwasi-plugin-remaju)
        try:
            if hasattr(importlib.metadata, "packages_distributions"):
                pkgs_map = importlib.metadata.packages_distributions()
                dists = pkgs_map.get(root_package, [])
                if dists:
                    return importlib.metadata.version(dists[0])
        except Exception:
            pass

        try:
            return importlib.metadata.version(root_package)
        except importlib.metadata.PackageNotFoundError:
            pass

        try:
            module = __import__(root_package)
            if hasattr(module, "__version__"):
                return str(module.__version__)
        except Exception:
            pass

    return "N/A"


def listar_plugins() -> None:
    """Lista los plugins Chaskiwasi instalados y sus características."""
    plugins = PluginRegistry.all()

    if not plugins:
        print("[yellow]No se detectaron plugins Chaskiwasi.[/yellow]")
        return

    ep_versions = _obtener_mapa_versiones_entry_points()

    table = Table(title="Plugins Chaskiwasi")
    table.add_column("Plugin", style="bold cyan")
    table.add_column("Versión", justify="center", style="green")
    table.add_column("Taxonomía")
    table.add_column("Extractor", justify="center")
    table.add_column("Reglas", justify="center")

    for name, plugin in sorted(plugins.items()):
        version_str = _obtener_version_plugin(name, plugin, ep_versions)
        taxonomy_name = getattr(getattr(plugin, "taxonomy", None), "name", "N/A")

        has_extractor = "sí" if getattr(plugin, "extractor", None) else "no"
        has_rules = "sí" if getattr(plugin, "query_rules_factory", None) else "no"

        table.add_row(
            name,
            version_str,
            taxonomy_name,
            has_extractor,
            has_rules,
        )

    print(table)


def procesar_pdf(
    pdf_path: Path,
    plugin: str,
    lote_id: str | None,
) -> None:
    """Procesa un PDF mediante un plugin y muestra el resultado."""
    execution_id = lote_id or f"PDF-{pdf_path.stem}"

    print(f"[cyan]Chaskiwasi -> {pdf_path}[/cyan]")
    print(f"[dim]Plugin: {plugin} | ID: {execution_id}[/dim]")

    result = asyncio.run(
        ChaskiwasiTrigger().process_file(
            global_id=execution_id,
            plugin_name=plugin,
            file_path=pdf_path,
        )
    )

    print("[green]Procesamiento completado.[/green]")
    print(result)


def ver_estado_vectores() -> None:
    """Muestra la ruta de persistencia configurada para ChromaDB."""
    print(
        f"[cyan]Persistencia ChromaDB:[/cyan] "
        f"{settings.CHROMA_PERSISTENT_PATH}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Motor documental y RAG de Chaskiwasi."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    list_parser = subparsers.add_parser(
        "list",
        help="Lista los plugins instalados y sus versiones.",
    )

    list_parser.set_defaults(
        handler=lambda args: listar_plugins()
    )

    ingesta = subparsers.add_parser(
        "ingesta",
        help="Procesamiento documental.",
    )

    ingesta_sub = ingesta.add_subparsers(
        dest="ingesta_command",
        required=True,
    )

    pdf = ingesta_sub.add_parser(
        "pdf",
        help="Procesa un PDF mediante un plugin.",
    )

    pdf.add_argument(
        "pdf_path",
        type=Path,
    )

    pdf.add_argument(
        "--plugin",
        "-p",
        required=True,
    )

    pdf.add_argument(
        "--lote",
        "-l",
        default=None,
    )

    pdf.set_defaults(
        handler=lambda args: procesar_pdf(
            args.pdf_path,
            args.plugin,
            args.lote,
        )
    )

    vector = subparsers.add_parser(
        "vector",
        help="Operaciones de almacenamiento vectorial.",
    )

    vector_sub = vector.add_subparsers(
        dest="vector_command",
        required=True,
    )

    status = vector_sub.add_parser(
        "status",
        help="Muestra la ruta de persistencia.",
    )

    status.set_defaults(
        handler=lambda args: ver_estado_vectores()
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


app = main


if __name__ == "__main__":
    main()