"""Contrato base para estrategias de clasificación."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from chaskiwasi.config.taxonomy_registry import Taxonomy
from chaskiwasi.plugins.contracts import PluginContext


@dataclass(frozen=True)
class ClassificationContext:
    """Contexto controlado que el core entrega a cada estrategia."""

    plugin: PluginContext
    current_source: Optional[Any] = None
    current_section: Optional[Any] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def taxonomy(self) -> Taxonomy:
        return self.plugin.taxonomy


@dataclass(frozen=True)
class ClassificationResult:
    """Resultado normalizado de una estrategia."""

    source: Optional[Any] = None
    section: Optional[Any] = None
    matched: bool = False
    reason: Optional[str] = None

    @classmethod
    def no_match(cls, reason: Optional[str] = None) -> "ClassificationResult":
        return cls(reason=reason)


class BaseStrategy(ABC):
    """Interfaz única para todas las estrategias del motor."""

    @abstractmethod
    def classify(
        self,
        chunk: str,
        context: ClassificationContext,
    ) -> ClassificationResult:
        """Clasifica un chunk usando únicamente el contexto recibido."""
        raise NotImplementedError
