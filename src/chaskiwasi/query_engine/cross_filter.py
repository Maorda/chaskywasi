import importlib.metadata
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IntentRule:
    """Define una regla de enrutamiento basada en palabras clave."""
    keywords: List[str]
    metadata_filter: Dict[str, Any]


class CrossQueryFilter:
    """Generador dinámico de filtros cruzados para ChromaDB compatible con Entry Points."""

    def __init__(
        self,
        load_plugins: bool = True,
        custom_rules: Optional[List[IntentRule]] = None,
    ) -> None:
        """
        Inicializa el filtro con reglas inyectadas manualmente o descubiertas vía plugins.
        """
        self.rules: List[IntentRule] = custom_rules or []
        
        if load_plugins:
            self._load_rules_from_entry_points()

    def _load_rules_from_entry_points(self) -> None:
        """
        Escanea el entorno de Python buscando plugins registrados bajo 'chaskywasi.query_rules'.
        """
        try:
            # Compatibilidad nativa para Python 3.10+
            entry_points = importlib.metadata.entry_points(group="chaskywasi.query_rules")
            for ep in entry_points:
                try:
                    plugin_callable = ep.load()
                    plugin_rules = plugin_callable()
                    
                    if isinstance(plugin_rules, list):
                        self.rules.extend(plugin_rules)
                        logger.info("Plugin de reglas cargado exitosamente: '%s'", ep.name)
                except Exception as e:
                    logger.warning("Fallo al cargar el plugin de reglas '%s': %s", ep.name, e)
        except KeyError:
            # No hay plugins instalados para este grupo
            pass

    def generate_where_clause(self, query_text: str, doc_id: str) -> Dict[str, Any]:
        """
        Analiza el texto iterando sobre las reglas dinámicas y genera el diccionario
        de metadatos bajo las restricciones de la API de ChromaDB.
        """
        base_filter = {"id_documento": doc_id}

        if not query_text or not isinstance(query_text, str) or not query_text.strip():
            return base_filter

        query_lower = query_text.lower()

        for rule in self.rules:
            if any(w in query_lower for w in rule.keywords):
                return {
                    "$and": [
                        base_filter,
                        rule.metadata_filter
                    ]
                }

        return base_filter