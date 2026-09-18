import logging
from typing import Any, List, Optional, Tuple

from chaskiwasi.classification.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class CascadeFactory:
    """
    Fábrica y orquestador de clasificación en cascada agnóstico para chaskywasi.
    Aplica una arquitectura de enrutamiento por estrategias ordenadas jerárquicamente.
    """

    def __init__(
        self,
        strategies: Optional[List[BaseStrategy]] = None,
        default_source: Optional[Any] = None,
        default_section: Optional[Any] = None,
    ) -> None:
        self._strategies: List[BaseStrategy] = strategies or []
        self.default_source = default_source
        self.default_section = default_section

    def process_chunk(
        self,
        text: Optional[str],
        current_source: Optional[Any] = None,
    ) -> Tuple[Optional[Any], Optional[Any]]:
        """Procesa un fragmento individual de texto iterando sobre la lista de estrategias."""
        effective_default_source = current_source or self.default_source

        if not text or not text.strip():
            return effective_default_source, self.default_section

        for strategy in self._strategies:
            try:
                src_res, sec_res = strategy.classify(
                    text, current_source=effective_default_source
                )

                if sec_res is not None:
                    final_source = src_res or effective_default_source
                    return final_source, sec_res
            except Exception as e:
                logger.warning(
                    "Estrategia %s falló durante la clasificación: %s",
                    strategy.__class__.__name__,
                    str(e),
                )

        return effective_default_source, self.default_section

    def process_chunks_batch(
        self,
        chunks: List[str],
        current_source: Optional[Any] = None,
    ) -> List[Tuple[Optional[Any], Optional[Any]]]:
        """Procesa una lista de fragmentos secuencialmente manteniendo el contexto actual."""
        results = []
        active_source = current_source or self.default_source
        
        for chunk in chunks:
            src, sec = self.process_chunk(chunk, current_source=active_source)
            if src is not None:
                active_source = src
            results.append((src, sec))
            
        return results