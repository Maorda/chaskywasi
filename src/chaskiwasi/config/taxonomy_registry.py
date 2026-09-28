# src/chaskiwasi/config/taxonomy_registry.py

import importlib.metadata
import logging
import threading
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Type

if TYPE_CHECKING:
    # Esto ayuda a los IDEs (VS Code, PyCharm) y a MyPy a entender
    # que SourceEnum y SectionEnum existen cuando se importan de este módulo.
    SourceEnum: Type[Enum]
    SectionEnum: Type[Enum]

logger = logging.getLogger(__name__)

# Contenedores en RAM que guardarán las clases reales provistas por el cliente
_SourceEnumClass: Optional[Type[Enum]] = None
_SectionEnumClass: Optional[Type[Enum]] = None

# Banderas y cerrojos para manejar la concurrencia (FastAPI / Cloud Run)
_AlreadyDiscovered: bool = False
_discovery_lock = threading.Lock()


class TaxonomyRegistry:
    """
    Registro y validador agnóstico de taxonomías para PyPI.
    Permite que la aplicación inyecte sus Enums en caliente al arrancar o los descubra vía Entry Points.
    """

    @classmethod
    def inject_taxonomies(cls, source_enum_class: Type[Enum], section_enum_class: Type[Enum]) -> None:
        """Inyecta de forma segura las clases de enums del cliente en el core."""
        global _SourceEnumClass, _SectionEnumClass, _AlreadyDiscovered
        
        _SourceEnumClass = source_enum_class
        _SectionEnumClass = section_enum_class
        _AlreadyDiscovered = True  # Previene que el auto-discover sobreescriba esto
        
        logger.info("[CHASKY-REGISTRY] Taxonomías del cliente inyectadas con éxito de forma manual.")

    @classmethod
    def auto_discover_via_entry_points(cls) -> None:
        """
        Escanea dinámicamente el venv buscando el entry point 'chaskywasi.taxonomy'.
        Si lo encuentra, invoca el cargador e inyecta las clases automáticamente.
        Seguro para entornos concurrentes gracias al cerrojo (Lock).
        """
        global _SourceEnumClass, _SectionEnumClass, _AlreadyDiscovered
        
        if _AlreadyDiscovered:
            return

        with _discovery_lock:
            # Doble verificación (Double-Checked Locking Pattern)
            if _AlreadyDiscovered:
                return
                
            _AlreadyDiscovered = True
            try:
                # Escaneamos el entorno de Python compatible con 3.10+
                entry_points = importlib.metadata.entry_points(group="chaskywasi.taxonomy")
                
                for ep in entry_points:
                    try:
                        logger.info(f"[CHASKY-REGISTRY] Intentando auto-cargar taxonomía desde Entry Point: '{ep.name}'")
                        loader_callable = ep.load()
                        
                        # El contrato exige que el entry point devuelva una tupla (SourceEnum, SectionEnum)
                        source_enum_class, section_enum_class = loader_callable()
                        
                        _SourceEnumClass = source_enum_class
                        _SectionEnumClass = section_enum_class
                        
                        logger.info(f"🚀 [CHASKY-REGISTRY] Taxonomías auto-inyectadas con éxito desde '{ep.name}' vía Entry Points.")
                        return  # Salida inmediata al resolver con éxito el primer entry point válido
                    except Exception as e:
                        # exc_info=True preserva el stacktrace en los logs si el módulo falla al importar
                        logger.warning(f"[CHASKY-REGISTRY] Falló la carga del entry point '{ep.name}': {e}", exc_info=True)
            except Exception as e:
                logger.error(f"[CHASKY-REGISTRY] Error crítico en el escaneo de entry points: {e}", exc_info=True)

    @classmethod
    def get_source_enum(cls) -> Type[Enum]:
        """Devuelve la clase SourceEnum activa o intenta resolverla vía Entry Points."""
        global _SourceEnumClass
        if _SourceEnumClass is None:
            cls.auto_discover_via_entry_points()
            
        if _SourceEnumClass is None:
            raise RuntimeError("Falta inyectar la clase SourceEnum al arrancar la aplicación.")
        return _SourceEnumClass

    @classmethod
    def get_section_enum(cls) -> Type[Enum]:
        """Devuelve la clase SectionEnum activa o intenta resolverla vía Entry Points."""
        global _SectionEnumClass
        if _SectionEnumClass is None:
            cls.auto_discover_via_entry_points()
            
        if _SectionEnumClass is None:
            raise RuntimeError("Falta inyectar la clase SectionEnum al arrancar la aplicación.")
        return _SectionEnumClass


# =====================================================================
# 🚀 INTERCEPTOR DE ATRIBUTOS A NIVEL DE MÓDULO (EL SECRETO DEL ÉXITO)
# =====================================================================
def __getattr__(name: str) -> Any:
    """
    Simula de forma polimórfica la existencia de SourceEnum y SectionEnum.
    Resuelve el ImportError interceptando los 'from taxonomy_registry import ...'
    """
    if name == "SourceEnum":
        return TaxonomyRegistry.get_source_enum()
    if name == "SectionEnum":
        return TaxonomyRegistry.get_section_enum()
    raise AttributeError(f"El módulo '{__name__}' no posee el atributo '{name}'")