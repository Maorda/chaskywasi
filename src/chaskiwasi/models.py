from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class PluginArtifact(BaseModel):
    """
    Representa cualquier archivo binario (PDF, etc.) o bloque de datos 
    producido por un plugin de forma agnóstica.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    plugin_origin: str          # Ej: "sunarp", "remaju"
    identifier_key: str         # Ej: "partida_registral", "expediente"
    identifier_value: str       # Ej: "40001133"
    file_bytes: bytes           # El stream del PDF en RAM
    metadata: Dict[str, Any] = {} # Metadatos libres definidos por el plugin

class MemoryContext(BaseModel):
    """
    Contenedor maestro 100% agnóstico del dominio. 
    Solo transporta IDs, payloads genéricos y artefactos binarios en RAM.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    execution_id: str
    
    # Datos y binario de la fuente primaria (manejados por su respectivo plugin)
    primary_source_name: str
    primary_payload: Dict[str, Any] = {}
    primary_bytes: Optional[bytes] = None
    
    # Lista genérica de artefactos recolectados por los plugins de enriquecimiento
    artifacts: List[PluginArtifact] = []
    
    # Control general del flujo
    status: str = "initialized"
    error_logs: List[str] = []