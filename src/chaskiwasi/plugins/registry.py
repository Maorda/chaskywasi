"""Descubrimiento y ciclo de vida de plugins de Chaskiwasi."""

from __future__ import annotations

import importlib.metadata
import logging
import threading
from typing import Dict, Iterable, Optional

from chaskiwasi.config.taxonomy_registry import TaxonomyRegistry
from chaskiwasi.plugins.contracts import PluginDefinition

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registro thread-safe de plugins instalados."""

    _plugins: Dict[str, PluginDefinition] = {}
    _discovered: bool = False
    _lock = threading.RLock()

    @classmethod
    def register(cls, plugin: PluginDefinition) -> None:
        name = cls._normalize_name(plugin.name)
        with cls._lock:
            existing = cls._plugins.get(name)
            if existing is not None and existing != plugin:
                raise ValueError(f"Ya existe un plugin diferente registrado para '{name}'.")
            TaxonomyRegistry.register(name, plugin.taxonomy)
            cls._plugins[name] = plugin

    @classmethod
    def get(cls, plugin_name: str) -> PluginDefinition:
        cls.discover()
        name = cls._normalize_name(plugin_name)
        with cls._lock:
            plugin = cls._plugins.get(name)
        if plugin is None:
            raise KeyError(f"No existe un plugin registrado llamado '{name}'.")
        return plugin

    @classmethod
    def try_get(cls, plugin_name: str) -> Optional[PluginDefinition]:
        try:
            return cls.get(plugin_name)
        except KeyError:
            return None

    @classmethod
    def all(cls) -> Dict[str, PluginDefinition]:
        cls.discover()
        with cls._lock:
            return dict(cls._plugins)

    @classmethod
    def discover(cls, force: bool = False) -> None:
        with cls._lock:
            if cls._discovered and not force:
                return
            cls._discovered = True

        try:
            entry_points = importlib.metadata.entry_points(group="chaskiwasi.plugins")
        except Exception:
            entry_points = ()

        for entry_point in entry_points:
            try:
                loader = entry_point.load()
                plugin = loader()
                if not isinstance(plugin, PluginDefinition):
                    raise TypeError(
                        f"El entry point '{entry_point.name}' no devolvió PluginDefinition."
                    )
                if plugin.name.strip().lower() != entry_point.name.strip().lower():
                    raise ValueError(
                        f"El nombre del plugin '{plugin.name}' no coincide con el entry point "
                        f"'{entry_point.name}'."
                    )
                cls.register(plugin)
                logger.info("Plugin Chaskiwasi cargado: %s", plugin.name)
            except Exception:
                logger.exception("No se pudo cargar el plugin '%s'.", entry_point.name)

    @classmethod
    def build_strategies(cls, plugin_name: str):
        plugin = cls.get(plugin_name)
        context = plugin_context(plugin)
        return list(plugin.strategy_factory(context))

    @classmethod
    def build_cascade_factory(cls, plugin_name: str):
        from chaskiwasi.classification.cascade_factory import CascadeFactory

        plugin = cls.get(plugin_name)
        context = plugin_context(plugin)
        strategies = list(plugin.strategy_factory(context))
        return CascadeFactory(
            strategies=strategies,
            plugin_context=context,
        )

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._plugins.clear()
            cls._discovered = False
        TaxonomyRegistry.clear()

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = str(name).strip().lower()
        if not normalized:
            raise ValueError("El nombre del plugin no puede estar vacío.")
        return normalized


def plugin_context(plugin: PluginDefinition):
    from chaskiwasi.plugins.contracts import PluginContext

    return PluginContext(
        name=plugin.name,
        taxonomy=plugin.taxonomy,
        metadata=plugin.metadata,
    )
