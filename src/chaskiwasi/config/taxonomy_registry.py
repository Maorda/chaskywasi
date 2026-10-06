"""Registro de taxonomías independientes por plugin.

El core es dueño del registro activo; los plugins son dueños de sus taxonomías.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Type


@dataclass(frozen=True)
class Taxonomy:
    """Taxonomía perteneciente exclusivamente a un plugin."""

    name: str
    source_enum: Type[Enum]
    section_enum: Type[Enum]

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not name:
            raise ValueError("El nombre de la taxonomía no puede estar vacío.")
        if not isinstance(self.source_enum, type) or not issubclass(self.source_enum, Enum):
            raise TypeError("source_enum debe ser una clase Enum.")
        if not isinstance(self.section_enum, type) or not issubclass(self.section_enum, Enum):
            raise TypeError("section_enum debe ser una clase Enum.")
        object.__setattr__(self, "name", name)

    def source_values(self) -> tuple[Enum, ...]:
        return tuple(self.source_enum)

    def section_values(self) -> tuple[Enum, ...]:
        return tuple(self.section_enum)

    def contains_source(self, value: object) -> bool:
        return isinstance(value, self.source_enum)

    def contains_section(self, value: object) -> bool:
        return isinstance(value, self.section_enum)


class TaxonomyRegistry:
    """Registro thread-safe de taxonomías indexadas por plugin.

    El registro no descubre entry points por sí mismo. Esa responsabilidad
    pertenece a PluginRegistry, que garantiza que taxonomía y plugin se carguen
    como una única definición coherente.
    """

    _taxonomies: Dict[str, Taxonomy] = {}
    _lock = threading.RLock()

    @classmethod
    def register(cls, plugin_name: str, taxonomy: Taxonomy) -> None:
        name = cls._normalize_name(plugin_name)
        taxonomy_name = cls._normalize_name(taxonomy.name)
        if name != taxonomy_name:
            raise ValueError(
                f"El plugin '{name}' y la taxonomía '{taxonomy.name}' deben tener el mismo nombre."
            )
        with cls._lock:
            existing = cls._taxonomies.get(name)
            if existing is not None and existing != taxonomy:
                raise ValueError(f"Ya existe una taxonomía diferente registrada para '{name}'.")
            cls._taxonomies[name] = taxonomy

    @classmethod
    def register_many(cls, items: Iterable[tuple[str, Taxonomy]]) -> None:
        for plugin_name, taxonomy in items:
            cls.register(plugin_name, taxonomy)

    @classmethod
    def get(cls, plugin_name: str) -> Taxonomy:
        name = cls._normalize_name(plugin_name)
        with cls._lock:
            taxonomy = cls._taxonomies.get(name)
        if taxonomy is None:
            raise KeyError(f"No existe una taxonomía registrada para el plugin '{name}'.")
        return taxonomy

    @classmethod
    def try_get(cls, plugin_name: str) -> Optional[Taxonomy]:
        try:
            return cls.get(plugin_name)
        except KeyError:
            return None

    @classmethod
    def all(cls) -> Dict[str, Taxonomy]:
        with cls._lock:
            return dict(cls._taxonomies)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._taxonomies.clear()

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = str(name).strip().lower()
        if not normalized:
            raise ValueError("El nombre no puede estar vacío.")
        return normalized
