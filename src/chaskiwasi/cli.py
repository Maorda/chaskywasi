"""CLI del motor Chaskiwasi, sin dependencias sobre orquestadores externos."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich import print
from rich.table import Table

from chaskiwasi.config.settings import settings
from chaskiwasi.orchestration.trigger import ChaskiwasiTrigger
from chaskiwasi.plugins.registry import PluginRegistry


def listar_plugins() -> None:
    """Lista los plugins Chaskiwasi instalados."""
    plugins = PluginRegistry.all()
    if not plugins:
        print("[yellow]No se detectaron plugins Chaskiwasi.[/yellow]")
        return

    table = Table(title="Plugins Chaskiwasi")
    table.add_column("Plugin")
    table.add_column("Taxonomía")
    table.add_column("Extractor")
    table.add_column("Reglas")

    for name, plugin in sorted(plugins.items()):
        table.add_row(
            name,
            plugin.taxonomy.name,
            "sí" if plugin.extractor else "no",
            "sí" if plugin.query_rules_factory else "no",
        )
    print(table)


def procesar_pdf(pdf_path: Path, plugin: str, lote_id: str | None) -> None:
    """Procesa un PDF mediante un plugin y guarda el JSON resultante."""
    execution_id = lote_id or f"PDF-{pdf_path.stem}"
    print(f"[cyan]Chaskiwasi -> {pdf_path}[/cyan]")
    print(f"[dim]Plugin: {plugin} | ID: {execution_id}[/dim]")
    asyncio.run(
        ChaskiwasiTrigger().process_file(
            global_id=execution_id,
            plugin_name=plugin,
            file_path=pdf_path,
        )
    )
    print("[green]Procesamiento completado.[/green]")


def ver_estado_vectores() -> None:
    print(f"[cyan]Persistencia ChromaDB:[/cyan] {settings.CHROMA_PERSISTENT_PATH}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Motor documental y RAG de Chaskiwasi.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Lista los plugins instalados.")
    list_parser.set_defaults(handler=lambda args: listar_plugins())

    ingesta = subparsers.add_parser("ingesta", help="Procesamiento documental.")
    ingesta_sub = ingesta.add_subparsers(dest="ingesta_command", required=True)
    pdf = ingesta_sub.add_parser("pdf", help="Procesa un PDF mediante un plugin.")
    pdf.add_argument("pdf_path", type=Path)
    pdf.add_argument("--plugin", "-p", required=True)
    pdf.add_argument("--lote", "-l", default=None)
    pdf.set_defaults(handler=lambda args: procesar_pdf(args.pdf_path, args.plugin, args.lote))

    vector = subparsers.add_parser("vector", help="Operaciones de almacenamiento vectorial.")
    vector_sub = vector.add_subparsers(dest="vector_command", required=True)
    status = vector_sub.add_parser("status", help="Muestra la ruta de persistencia.")
    status.set_defaults(handler=lambda args: ver_estado_vectores())
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except Exception as exc:
        print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1) from exc


app = main

if __name__ == "__main__":
    main()
