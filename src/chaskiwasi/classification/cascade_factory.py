"""Motor central de clasificación en cascada de Chaskiwasi."""

from __future__ import annotations

import logging
from typing import Any, Iterable, List, Optional

from chaskiwasi.classification.strategies.base_strategy import (
    BaseStrategy,
    ClassificationContext,
    ClassificationResult,
)
from chaskiwasi.plugins.contracts import PluginContext

logger = logging.getLogger(__name__)


class CascadeFactory:
    """Ejecuta estrategias ordenadas y mantiene el contexto de clasificación."""

    def __init__(
        self,
        strategies: Optional[Iterable[BaseStrategy]] = None,
        plugin_context: Optional[PluginContext] = None,
        default_source: Optional[Any] = None,
        default_section: Optional[Any] = None,
    ) -> None:
        self._strategies: List[BaseStrategy] = list(strategies or [])
        self.plugin_context = plugin_context
        self.default_source = default_source
        self.default_section = default_section

    @classmethod
    def from_plugin(cls, plugin_name: str) -> "CascadeFactory":
        from chaskiwasi.plugins.registry import PluginRegistry

        return PluginRegistry.build_cascade_factory(plugin_name)

    @property
    def strategies(self) -> tuple[BaseStrategy, ...]:
        return tuple(self._strategies)

    def process_chunk(
        self,
        text: Optional[str],
        context: Optional[ClassificationContext] = None,
        current_source: Optional[Any] = None,
        current_section: Optional[Any] = None,
    ) -> tuple[Optional[Any], Optional[Any]]:
        """Procesa un chunk y devuelve ``(source, section)`` normalizados."""
        classification_context = self._build_context(
            context=context,
            current_source=current_source,
            current_section=current_section,
        )

        fallback_source = classification_context.current_source or self.default_source
        fallback_section = classification_context.current_section or self.default_section

        if not isinstance(text, str) or not text.strip():
            return fallback_source, fallback_section

        for strategy in self._strategies:
            try:
                result = strategy.classify(text, classification_context)
                normalized = self._normalize_result(result)
                if normalized.section is not None:
                    source = normalized.source or fallback_source
                    return source, normalized.section
            except Exception:
                logger.exception(
                    "La estrategia %s falló durante la clasificación.",
                    strategy.__class__.__name__,
                )

        return fallback_source, fallback_section

    def process_chunks_batch(
        self,
        chunks: Iterable[Optional[str]],
        context: Optional[ClassificationContext] = None,
        current_source: Optional[Any] = None,
        current_section: Optional[Any] = None,
    ) -> List[tuple[Optional[Any], Optional[Any]]]:
        """Clasifica secuencialmente y propaga fuente/sección entre chunks."""
        results: List[tuple[Optional[Any], Optional[Any]]] = []
        active_source = current_source or (context.current_source if context else None) or self.default_source
        active_section = current_section or (context.current_section if context else None) or self.default_section

        for chunk in chunks:
            chunk_context = self._build_context(
                context=context,
                current_source=active_source,
                current_section=active_section,
            )
            source, section = self.process_chunk(chunk, context=chunk_context)
            if source is not None:
                active_source = source
            if section is not None:
                active_section = section
            results.append((source, section))

        return results

    def _build_context(
        self,
        context: Optional[ClassificationContext],
        current_source: Optional[Any],
        current_section: Optional[Any],
    ) -> ClassificationContext:
        if context is not None:
            return ClassificationContext(
                plugin=context.plugin,
                current_source=current_source if current_source is not None else context.current_source,
                current_section=current_section if current_section is not None else context.current_section,
                metadata=context.metadata,
            )

        if self.plugin_context is None:
            raise RuntimeError(
                "CascadeFactory necesita un PluginContext o una instancia creada explícitamente "
                "con plugin_context."
            )

        return ClassificationContext(
            plugin=self.plugin_context,
            current_source=current_source,
            current_section=current_section,
        )

    @staticmethod
    def _normalize_result(result: Any) -> ClassificationResult:
        if isinstance(result, ClassificationResult):
            return result
        if isinstance(result, tuple) and len(result) == 2:
            source, section = result
            return ClassificationResult(
                source=source,
                section=section,
                matched=section is not None,
            )
        raise TypeError(
            "Una estrategia debe devolver ClassificationResult o una tupla (source, section)."
        )
