from enum import Enum

from chaskiwasi.plugins.contracts import PluginDefinition
from chaskiwasi.plugins.registry import PluginRegistry
from chaskiwasi.config.taxonomy_registry import Taxonomy
from chaskiwasi.query_engine.cross_filter import CrossQueryFilter, IntentRule


class Source(Enum):
    DOCUMENT = "document"


class Section(Enum):
    TITLE = "title"
    BODY = "body"


def _plugin():
    taxonomy = Taxonomy("test_filter", Source, Section)

    return PluginDefinition(
        name="test_filter",
        taxonomy=taxonomy,
        strategy_factory=lambda context: [],
        query_rules_factory=lambda: (
            IntentRule(
                keywords=("titulo", "título"),
                metadata_filter={"tipo_seccion": "title"},
                priority=10,
            ),
        ),
    )


def test_cross_filter_loads_plugin_rules():
    PluginRegistry.clear()
    PluginRegistry.register(_plugin())

    query_filter = CrossQueryFilter()
    where = query_filter.generate_where_clause("quiero el título", "DOC-1", "test_filter")

    assert where == {
        "$and": [
            {"id_documento": "DOC-1"},
            {"plugin": "test_filter"},
            {"tipo_seccion": "title"},
        ]
    }


def test_cross_filter_can_filter_only_by_plugin():
    PluginRegistry.clear()
    PluginRegistry.register(_plugin())

    query_filter = CrossQueryFilter()
    where = query_filter.generate_where_clause("consulta general", plugin_name="test_filter")

    assert where == {"plugin": "test_filter"}
