from enum import Enum
from unittest.mock import MagicMock

from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.config.taxonomy_registry import Taxonomy
from chaskiwasi.plugins.contracts import PluginContext


class Source(Enum):
    REMAJU = "remaju"
    SUNARP = "sunarp"


class Section(Enum):
    ENCABEZADO = "encabezado"
    PARTES = "partes"
    RESOLUCION = "resolucion"


def make_factory():
    taxonomy = Taxonomy("batch_test", Source, Section)
    context = PluginContext("batch_test", taxonomy)

    strat1 = MagicMock()
    strat2 = MagicMock()
    strat1.classify.side_effect = [
        (Source.SUNARP, Section.ENCABEZADO),
        (None, None),
        (None, None),
    ]
    strat2.classify.side_effect = [
        (None, Section.PARTES),
        (None, None),
    ]

    return CascadeFactory(
        strategies=[strat1, strat2],
        plugin_context=context,
        default_source=Source.REMAJU,
        default_section=Section.RESOLUCION,
    ), strat1, strat2


def test_process_chunks_batch_success_and_context_propagation():
    factory, strat1, strat2 = make_factory()

    results = factory.process_chunks_batch(
        [
            "Chunk 0: Encabezado registral SUNARP",
            "Chunk 1: Cláusula de comprador y vendedor",
            "Chunk 2: Texto sin coincidencia de reglas",
        ],
        current_source=Source.REMAJU,
    )

    assert results == [
        (Source.SUNARP, Section.ENCABEZADO),
        (Source.SUNARP, Section.PARTES),
        (Source.SUNARP, Section.PARTES),
    ]
    assert strat1.classify.call_count == 3
    assert strat2.classify.call_count == 2

    first_context = strat1.classify.call_args_list[0].args[1]
    second_context = strat1.classify.call_args_list[1].args[1]
    assert first_context.current_source is Source.REMAJU
    assert first_context.current_section is Section.RESOLUCION
    assert second_context.current_source is Source.SUNARP
    assert second_context.current_section is Section.ENCABEZADO


def test_process_chunks_batch_empty_list():
    factory = CascadeFactory(
        plugin_context=PluginContext("batch_test", Taxonomy("batch_test", Source, Section)),
        default_source=Source.REMAJU,
        default_section=Section.RESOLUCION,
    )

    assert factory.process_chunks_batch([]) == []


def test_process_chunks_batch_with_blank_and_none_chunks():
    factory = CascadeFactory(
        plugin_context=PluginContext("batch_test", Taxonomy("batch_test", Source, Section)),
        strategies=[],
        default_source=Source.REMAJU,
        default_section=Section.RESOLUCION,
    )

    results = factory.process_chunks_batch(
        ["", "   ", None],
        current_source=Source.REMAJU,
    )

    assert results == [
        (Source.REMAJU, Section.RESOLUCION),
        (Source.REMAJU, Section.RESOLUCION),
        (Source.REMAJU, Section.RESOLUCION),
    ]
