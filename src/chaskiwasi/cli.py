# dantesito/chasky/cli.py

import asyncio
import sys
import typer
import importlib.metadata  # <-- AGREGADO para leer los entry points
from dotenv import load_dotenv  
from rich import print
from rich.table import Table

# Cargar variables de entorno
load_dotenv()  

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
# COMANDOS PRINCIPALES
# ==============================================================================

# ==============================================================================
# COMANDOS PRINCIPALES
# ==============================================================================

@app.command("list")
def listar_plugins():
    """
    Lista todos los plugins instalados dinámicamente en el ecosistema Chaskiwasi.
    """
    print("[bold cyan]🔌 Escaneando red de Chasquis (plugins instalados)...[/bold cyan]\n")
    
    table = Table(title="Plugins Detectados en el Ecosistema")
    table.add_column("Categoría (Entry Point)", style="cyan", no_wrap=True)
    table.add_column("Nombre del Plugin", style="magenta", justify="left")
    table.add_column("Versión", style="yellow", justify="center") # <-- COLUMNA AÑADIDA
    table.add_column("Módulo Destino", style="green", justify="left")
    
    # Grupos definidos en tu arquitectura (pyproject.toml)
    target_groups = ["chaskiwasi.query_rules", "chaskiwasi.classifiers", "chaskiwasi.extractors"]
    
    eps = importlib.metadata.entry_points()
    plugins_encontrados = False
    
    for group in target_groups:
        group_eps = eps.select(group=group)
        for ep in group_eps:
            plugins_encontrados = True
            
            # Obtener la versión del paquete (Distribution) que provee el plugin
            version = "Desconocida"
            if hasattr(ep, 'dist') and ep.dist is not None:
                version = ep.dist.version
                
            table.add_row(group, ep.name, version, ep.value)
            
    if plugins_encontrados:
        print(table)
        print("\n[dim]Nota: Estos plugins son inyectados automáticamente en el motor base.[/dim]")
    else:
        print("[bold yellow]⚠️ No se detectaron plugins instalados para Chaskiwasi.[/bold yellow]")
        print("Asegúrate de instalar los plugins (ej. 'pip install -e /ruta/chaskiwasi-legal-pe').")


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