# dantesito/chasky/classification/strategies/base_strategy.py
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any

# 🚀 CONTRATO ACTIVO: Importación obligatoria para control de tipos dinámicos
from chaskiwasi.config.taxonomy_registry import TaxonomyRegistry


class BaseStrategy(ABC):
    """
    Interfaz contractual agnóstica para todas las estrategias de inferencia semántica.
    
    Expone de forma segura las clases de Enums inyectadas por el cliente mediante
    propiedades dinámicas de solo lectura, eliminando la fragilidad de constructores.
    """

    @property
    def source_enum_class(self) -> Any:
        """
        Devuelve de forma dinámica la clase SourceEnum del cliente.
        🛡️ CORTAFUEGOS EN CALIENTE: Lanza RuntimeError si no fue inyectada al arrancar.
        """
        return TaxonomyRegistry.get_source_enum()

    @property
    def section_enum_class(self) -> Any:
        """
        Devuelve de forma dinámica la clase SectionEnum del cliente.
        🛡️ CORTAFUEGOS EN CALIENTE: Lanza RuntimeError si no fue inyectada al arrancar.
        """
        return TaxonomyRegistry.get_section_enum()

    @abstractmethod
    def classify(self, chunk: str, current_source: Optional[str] = None) -> Tuple[Optional[Any], Optional[Any]]:
        """
        Analiza un fragmento y devuelve una tupla conteniendo las instancias
        de los Enums dinámicos del cliente (SourceEnum, SectionEnum).

        :param chunk: Fragmento de texto Markdown a evaluar.
        :param current_source: Contexto de origen acumulado o arrastrado.
        :return: Tupla conteniendo (Instancia de SourceEnum, Instancia de SectionEnum)
        """
        pass
