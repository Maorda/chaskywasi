"""Estrategia de continuidad contextual."""

from __future__ import annotations

from chaskiwasi.classification.strategies.base_strategy import (
    BaseStrategy,
    ClassificationContext,
    ClassificationResult,
)


class ContextOverlapStrategy(BaseStrategy):
    """Conserva la clasificación anterior cuando el plugin no detecta una nueva."""

    def classify(self, chunk: str, context: ClassificationContext) -> ClassificationResult:
        if context.current_source is None and context.current_section is None:
            return ClassificationResult.no_match("sin contexto previo")

        if context.current_section is None:
            # Una fuente sola no constituye una clasificación de sección.
            return ClassificationResult.no_match("solo existe contexto de fuente")

        return ClassificationResult(
            source=context.current_source,
            section=context.current_section,
            matched=True,
            reason="contexto_anterior",
        )
