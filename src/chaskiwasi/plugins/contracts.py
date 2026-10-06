"""Contratos agnósticos que un plugin puede implementar."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Mapping, Optional, Sequence

from chaskiwasi.config.taxonomy_registry import Taxonomy

if TYPE_CHECKING:
    from chaskiwasi.classification.strategies.base_strategy import BaseStrategy
    from chaskiwasi.query_engine.cross_filter import IntentRule


@dataclass(frozen=True)
class PluginContext:
    """Contexto de ejecución controlado que el core entrega al plugin."""

    name: str
    taxonomy: Taxonomy
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionContext:
    """Entrada normalizada para extracción específica de negocio."""

    plugin: PluginContext
    document_id: str
    text: str
    sections: Mapping[str, str]
    metadata: Mapping[str, Any] = field(default_factory=dict)


StrategyFactory = Callable[[PluginContext], Sequence["BaseStrategy"]]
QueryRulesFactory = Callable[[], Sequence["IntentRule"]]
Extractor = Callable[[ExtractionContext], Dict[str, Any]]


@dataclass(frozen=True)
class PluginDefinition:
    """Definición completa de un plugin de Chaskiwasi."""

    name: str
    taxonomy: Taxonomy
    strategy_factory: StrategyFactory
    query_rules_factory: Optional[QueryRulesFactory] = None
    extractor: Optional[Extractor] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = self.name.strip().lower()
        if not normalized:
            raise ValueError("El nombre del plugin no puede estar vacío.")
        if normalized != self.taxonomy.name.strip().lower():
            raise ValueError(
                f"El plugin '{self.name}' debe utilizar la taxonomía '{self.name}'."
            )
