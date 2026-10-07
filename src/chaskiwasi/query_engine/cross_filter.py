# chaskiwasi/query_engine/cross_filter.py

"""Mecanismo genérico de consulta basado en reglas de plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class IntentRule:
    """Regla declarativa de intención aportada por un plugin."""

    keywords: Sequence[str]
    metadata_filter: Dict[str, Any]
    priority: int = 0
    plugin_name: Optional[str] = None

    def __post_init__(self) -> None:
        normalized = tuple(
            str(keyword).strip().lower()
            for keyword in self.keywords
            if str(keyword).strip()
        )

        if not normalized:
            raise ValueError(
                "IntentRule necesita al menos una keyword no vacía."
            )

        if (
            not isinstance(self.metadata_filter, dict)
            or not self.metadata_filter
        ):
            raise ValueError(
                "IntentRule necesita un metadata_filter no vacío."
            )

        object.__setattr__(
            self,
            "keywords",
            normalized,
        )

        object.__setattr__(
            self,
            "metadata_filter",
            dict(self.metadata_filter),
        )

        if self.plugin_name is not None:
            object.__setattr__(
                self,
                "plugin_name",
                str(self.plugin_name).strip().lower(),
            )


class CrossQueryFilter:
    """Carga reglas del registro de plugins y compone filtros de consulta."""

    def __init__(
        self,
        load_plugins: bool = True,
        custom_rules: Optional[Iterable[IntentRule]] = None,
    ) -> None:
        self.rules: List[IntentRule] = list(
            custom_rules or []
        )

        if load_plugins:
            self._load_rules_from_registry()

    def add_rules(
        self,
        rules: Iterable[IntentRule],
        plugin_name: Optional[str] = None,
    ) -> None:
        """Agrega reglas validando su contrato."""
        for rule in rules:
            if not isinstance(rule, IntentRule):
                raise TypeError(
                    "Todas las reglas deben ser instancias de IntentRule."
                )

            if plugin_name and rule.plugin_name is None:
                rule = IntentRule(
                    keywords=rule.keywords,
                    metadata_filter=rule.metadata_filter,
                    priority=rule.priority,
                    plugin_name=plugin_name,
                )

            self.rules.append(rule)

    def _load_rules_from_registry(self) -> None:
        """Carga las reglas declaradas por los plugins registrados."""
        from chaskiwasi.plugins.registry import PluginRegistry

        for plugin_name, plugin in PluginRegistry.all().items():
            if plugin.query_rules_factory is None:
                continue

            try:
                self.add_rules(
                    plugin.query_rules_factory() or (),
                    plugin_name=plugin_name,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "No se pudieron cargar las reglas del plugin '%s'.",
                    plugin_name,
                )

    def generate_where_clause(
        self,
        query_text: Optional[str],
        doc_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Genera el filtro de recuperación para una consulta.

        Las intenciones de mayor prioridad son las que gobiernan la consulta.

        Si existe una sola intención especializada, su filtro se aplica
        directamente.

        Si existen varias intenciones especializadas con la misma prioridad,
        sus filtros se combinan mediante OR.

        Los filtros base, como documento o plugin, siempre se aplican mediante
        AND.
        """
        normalized_plugin = (
            plugin_name.strip().lower()
            if plugin_name
            else None
        )

        base_filters: List[Dict[str, Any]] = []

        if doc_id:
            base_filters.append(
                {
                    "id_documento": doc_id,
                }
            )

        if normalized_plugin:
            base_filters.append(
                {
                    "plugin": normalized_plugin,
                }
            )

        if (
            not isinstance(query_text, str)
            or not query_text.strip()
        ):
            return self._compose_filters(base_filters)

        normalized_query = query_text.lower()

        candidates = [
            rule
            for rule in self.rules
            if (
                normalized_plugin is None
                or rule.plugin_name in (
                    None,
                    normalized_plugin,
                )
            )
        ]

        matched = [
            rule
            for rule in candidates
            if any(
                keyword in normalized_query
                for keyword in rule.keywords
            )
        ]

        if not matched:
            return self._compose_filters(
                base_filters
            )

        highest = max(
            rule.priority
            for rule in matched
        )

        selected = [
            rule
            for rule in matched
            if rule.priority == highest
        ]

        intent_filters = [
            rule.metadata_filter
            for rule in selected
        ]

        intent_filter = self._compose_intent_filters(
            intent_filters
        )

        if not intent_filter:
            return self._compose_filters(
                base_filters
            )

        return self._compose_filters(
            [
                *base_filters,
                intent_filter,
            ]
        )

    @staticmethod
    def _compose_intent_filters(
        filters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Combina filtros derivados de múltiples intenciones.

        Las intenciones representan alternativas de recuperación.

        Por ello:

            intención A OR intención B

        mientras que los filtros estructurales/base se aplican fuera,
        mediante AND.
        """
        if not filters:
            return {}

        if len(filters) == 1:
            return filters[0]

        return {
            "$or": filters,
        }

    @staticmethod
    def _compose_filters(
        filters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Combina restricciones que deben cumplirse simultáneamente."""
        if not filters:
            return {}

        if len(filters) == 1:
            return filters[0]

        return {
            "$and": filters,
        }