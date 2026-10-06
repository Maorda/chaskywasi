from enum import Enum

from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.classification.strategies.base_strategy import (
    BaseStrategy,
    ClassificationContext,
    ClassificationResult,
)
from chaskiwasi.config.taxonomy_registry import Taxonomy, TaxonomyRegistry
from chaskiwasi.plugins.contracts import PluginContext, PluginDefinition
from chaskiwasi.plugins.registry import PluginRegistry


class SourceA(Enum):
    A = "a"


class SectionA(Enum):
    HEADER = "header"
    BODY = "body"


class SourceB(Enum):
    B = "b"


class SectionB(Enum):
    TITLE = "title"
    DETAIL = "detail"


class StrategyA(BaseStrategy):
    def classify(self, chunk: str, context: ClassificationContext) -> ClassificationResult:
        if "header" in chunk.lower():
            return ClassificationResult(SourceA.A, SectionA.HEADER, True)
        return ClassificationResult.no_match()


def make_plugin(name, source_enum, section_enum, strategy):
    taxonomy = Taxonomy(name, source_enum, section_enum)

    def factory(context: PluginContext):
        assert context.taxonomy is taxonomy
        return [strategy()]

    return PluginDefinition(name=name, taxonomy=taxonomy, strategy_factory=factory)


def test_taxonomy_registry_isolated_per_plugin():
    TaxonomyRegistry.clear()
    taxonomy_a = Taxonomy("plugin_a", SourceA, SectionA)
    taxonomy_b = Taxonomy("plugin_b", SourceB, SectionB)

    TaxonomyRegistry.register("plugin_a", taxonomy_a)
    TaxonomyRegistry.register("plugin_b", taxonomy_b)

    assert TaxonomyRegistry.get("plugin_a") is taxonomy_a
    assert TaxonomyRegistry.get("plugin_b") is taxonomy_b
    assert TaxonomyRegistry.get("plugin_a").source_enum is not SourceB


def test_cascade_uses_plugin_context_not_global_taxonomy():
    taxonomy = Taxonomy("plugin_a", SourceA, SectionA)
    plugin_context = PluginContext("plugin_a", taxonomy)
    factory = CascadeFactory(
        strategies=[StrategyA()],
        plugin_context=plugin_context,
    )

    source, section = factory.process_chunk("HEADER DEL DOCUMENTO")

    assert source is SourceA.A
    assert section is SectionA.HEADER


def test_plugins_can_coexist_without_shared_taxonomy():
    PluginRegistry.clear()
    plugin_a = make_plugin("plugin_a", SourceA, SectionA, StrategyA)

    class StrategyB(BaseStrategy):
        def classify(self, chunk, context):
            if "title" in chunk.lower():
                return ClassificationResult(SourceB.B, SectionB.TITLE, True)
            return ClassificationResult.no_match()

    plugin_b = make_plugin("plugin_b", SourceB, SectionB, StrategyB)
    PluginRegistry.register(plugin_a)
    PluginRegistry.register(plugin_b)

    factory_a = PluginRegistry.build_cascade_factory("plugin_a")
    factory_b = PluginRegistry.build_cascade_factory("plugin_b")

    source_a, section_a = factory_a.process_chunk("header")
    source_b, section_b = factory_b.process_chunk("title")

    assert source_a is SourceA.A
    assert section_a is SectionA.HEADER
    assert source_b is SourceB.B
    assert section_b is SectionB.TITLE
