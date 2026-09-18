# dantesito/chasky/config/taxonomy_registry.py
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Contenedores en RAM que guardarán las clases reales provistas por dantesito-quipu o los mocks de test
_SourceEnumClass: Optional[Any] = None
_SectionEnumClass: Optional[Any] = None


class TaxonomyRegistry:
    """
    Registro y validador agnóstico de taxonomías para PyPI.
    Permite que la aplicación inyecte sus Enums en caliente al arrancar.
    """

    @classmethod
    def inject_taxonomies(cls, source_enum_class: Any, section_enum_class: Any) -> None:
        """Inyecta de forma segura las clases de enums del cliente en el core."""
        global _SourceEnumClass, _SectionEnumClass
        _SourceEnumClass = source_enum_class
        _SectionEnumClass = section_enum_class
        logger.info("[CHASKY-REGISTRY] Taxonomías del cliente inyectadas con éxito.")

    @classmethod
    def get_source_enum(cls) -> Any:
        """Devuelve la clase SourceEnum activa o un Fallback si no fue inyectada."""
        global _SourceEnumClass
        if _SourceEnumClass is None:
            raise RuntimeError("Falta inyectar la clase SourceEnum al arrancar la aplicación.")
        return _SourceEnumClass

    @classmethod
    def get_section_enum(cls) -> Any:
        """Devuelve la clase SectionEnum activa o un Fallback si no fue inyectada."""
        global _SectionEnumClass
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
