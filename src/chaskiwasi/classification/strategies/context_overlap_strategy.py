# dantesito/chasky/classification/strategies/context_overlap_strategy.py

from typing import Optional, Tuple

from chaskiwasi.classification.strategies.base_strategy import BaseStrategy
from chaskiwasi.config.taxonomy_registry import SectionEnum, SourceEnum


class ContextOverlapStrategy(BaseStrategy):
    """Arrastra la fuente institucional desde el contexto del chunk anterior."""

    def classify(
        self,
        chunk_text: str,
        current_source: Optional[SourceEnum] = None,
    ) -> Tuple[Optional[SourceEnum], Optional[SectionEnum]]:
        """Mantiene la fuente previa sin inspeccionar el contenido del chunk."""
        if current_source is not None:
            return current_source, None

        return None, None