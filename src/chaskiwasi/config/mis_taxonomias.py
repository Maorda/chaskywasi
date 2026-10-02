# Un archivo cualquiera en tu suite
# D:\libs\chaskywasi\src\chaskiwasi\config\mis_taxonomias.py
from enum import Enum

class SourceEnum(Enum):
    REMAJU = "remaju"
    SUNARP = "sunarp"
    RENIEC = "reniec"

class SectionEnum(Enum):
    INTRODUCCION = "introduccion"
    DESCRIPCION = "descripcion"
    DATOS_GENERALES = "datos_generales"
    DESCONOCIDO = "desconocido"

def cargar_taxonomia_peru():
    """
    Función contractual que el Entry Point invocará dinámicamente.
    Retorna la tupla exacta requerida por el core de chaskywasi.
    """
    return SourceEnum, SectionEnum
