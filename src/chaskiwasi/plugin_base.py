from typing import Protocol, Dict, Any, runtime_checkable
from .models import MemoryContext

@runtime_checkable
class BasePlugin(Protocol):
    """
    Contrato obligatorio que todo plugin (remaju, sunarp, etc.) debe cumplir.
    Permite que el núcleo sea 100% agnóstico y trate a todos por igual.
    """
    def __init__(self, parameters: Dict[str, Any]) -> None:
        ...

    async def execute(self, context: MemoryContext) -> MemoryContext:
        """
        Ejecuta la lógica del plugin, procesa en memoria RAM y actualiza 
        el MemoryContext con artefactos o payloads.
        """
        ...