# dantesito/chasky/cli.py

import asyncio
import sys
import typer
from rich import print
from rich.table import Table

# CORREGIDO: Importaciones basadas en tu árbol de archivos real
from chaskiwasi.orchestration.trigger import ChaskywasiTrigger
from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.classification.strategies.context_overlap_strategy import ContextOverlapStrategy

app = typer.Typer(
    help="Casa del Mensajero - Centro de Control Estratégico RAG y Almacenamiento Vectorial.",
    add_completion=False
)

# Subgrupos de comandos profesionales
ingesta_app = typer.Typer(help="Comandos para disparar y controlar la ingesta de legajos.")
vector_app = typer.Typer(help="Comandos para auditar y mantener la base de datos ChromaDB.")
app.add_typer(ingesta_app, name="ingesta")
app.add_typer(vector_app, name="vector")


# ==============================================================================
# COMANDOS DE INGESTA
# ==============================================================================

@ingesta_app.command("tambo")
def disparar_tambo(
    plugins: list[str] = typer.Argument(..., help="Lista de plugins a ejecutar en paralelo (ej. remaju)")
):
    """
    Gatilla la extracción paralela en Chaskitambo y consolida los reportes en Chaskiwasi.
    """
    print("[bold cyan]wasi 🏛️  -> Ordenando salida de Chasquis hacia los paraderos...[/bold cyan]\n")
    
    # 1. Inicializamos la fábrica en cascada con tu estrategia contextual real
    estrategia_contexto = ContextOverlapStrategy()
    cascade_factory = CascadeFactory(strategies=[estrategia_contexto])
    
    # 2. Instanciamos tu clase real 'ChaskywasiTrigger' inyectándole la fábrica
    orchestrator = ChaskywasiTrigger(cascade_factory=cascade_factory)
    
    # 3. Forzar política de bucle Proactor requerida por Playwright en Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        # Ejecutamos el pipeline asíncronamente con un ID de lote de prueba
        asyncio.run(orchestrator.orchestrate_extraction_and_rag(
            global_id="LOTE-TEST-01", 
            plugin_names=plugins
        ))
    except KeyboardInterrupt:
        print("\n[bold yellow]⚠️ Operación cancelada por el operador central.[/bold yellow]")
    except Exception as e:
        print(f"\n[bold red]❌ Error crítico en el pipeline: {e}[/bold red]")


# ==============================================================================
# COMANDOS VECTORIALES (MOCK)
# ==============================================================================

@vector_app.command("status")
def ver_estado_vectores():
    """
    Muestra un reporte analítico de las colecciones y chunks en ChromaDB.
    """
    print("[bold green]📊 Analizando estado de la memoria persistente (ChromaDB)...[/bold green]\n")
    
    table = Table(title="Colecciones Activas en Chaskiwasi")
    table.add_column("Colección", justify="left", style="cyan", no_wrap=True)
    table.add_column("Total Chunks", justify="right", style="magenta")
    
    table.add_row("expedientes_remaju", "0 (Pendiente indexación)", "384")
    print(table)


if __name__ == "__main__":
    app()
