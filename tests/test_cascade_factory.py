from unittest.mock import MagicMock

from chaskiwasi.classification.cascade_factory import CascadeFactory
from chaskiwasi.classification.strategies.base_strategy import ClassificationResult
from chaskiwasi.config.taxonomy_registry import Taxonomy
from chaskiwasi.plugins.contracts import PluginContext
def make_factory(mock_source_enum, mock_section_enum, *strategies):
    taxonomy = Taxonomy("test", mock_source_enum, mock_section_enum)
    return CascadeFactory(
        strategies=list(strategies),
        plugin_context=PluginContext("test", taxonomy),
        default_source=mock_source_enum.REMAJU,
        default_section=mock_section_enum.RESOLUCION,
    )


def test_first_strategy_success(mock_source_enum, mock_section_enum):
    first = MagicMock()
    second = MagicMock()
    first.classify.return_value = ClassificationResult(
        mock_source_enum.SUNARP, mock_section_enum.ENCABEZADO, True
    )
    factory = make_factory(mock_source_enum, mock_section_enum, first, second)

    source, section = factory.process_chunk("texto")

    assert source is mock_source_enum.SUNARP
    assert section is mock_section_enum.ENCABEZADO
    second.classify.assert_not_called()

    context = first.classify.call_args.args[1]
    assert context.plugin.name == "test"
    assert context.taxonomy.name == "test"


def test_batch_propagates_source_and_section(mock_source_enum, mock_section_enum):
    first = MagicMock()
    first.classify.side_effect = [
        ClassificationResult(mock_source_enum.SUNARP, mock_section_enum.ENCABEZADO, True),
        ClassificationResult.no_match(),
    ]
    factory = make_factory(mock_source_enum, mock_section_enum, first)

    results = factory.process_chunks_batch(["uno", "dos"])

    assert results == [
        (mock_source_enum.SUNARP, mock_section_enum.ENCABEZADO),
        (mock_source_enum.SUNARP, mock_section_enum.ENCABEZADO),
    ]


def test_empty_batch(mock_source_enum, mock_section_enum):
    assert make_factory(mock_source_enum, mock_section_enum).process_chunks_batch([]) == []


def test_factory_without_plugin_context_requires_explicit_context(plugin_context):
    from chaskiwasi.classification.strategies.base_strategy import ClassificationContext

    factory = CascadeFactory(default_source="SRC", default_section="SEC")
    context = ClassificationContext(plugin=plugin_context)

    assert factory.process_chunk("texto", context=context) == ("SRC", "SEC")


def test_factory_without_plugin_context_fails_without_explicit_context():
    factory = CascadeFactory(default_source="SRC", default_section="SEC")

    try:
        factory.process_chunk("texto")
    except RuntimeError as exc:
        assert "PluginContext" in str(exc)
    else:
        raise AssertionError("Se esperaba RuntimeError cuando no existe PluginContext")
