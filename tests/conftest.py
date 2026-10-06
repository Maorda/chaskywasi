import enum
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class MockSourceEnum(enum.Enum):
    REMAJU = "remaju"
    SUNARP = "sunarp"


class MockSectionEnum(enum.Enum):
    ENCABEZADO = "encabezado"
    RESOLUCION = "resolucion"
    PARTES = "partes"
    GRAVAMEN = "gravamen"


@pytest.fixture
def mock_source_enum():
    return MockSourceEnum


@pytest.fixture
def mock_section_enum():
    return MockSectionEnum


@pytest.fixture
def mock_taxonomy():
    from chaskiwasi.config.taxonomy_registry import Taxonomy

    return Taxonomy("test", MockSourceEnum, MockSectionEnum)


@pytest.fixture
def plugin_context(mock_taxonomy):
    from chaskiwasi.plugins.contracts import PluginContext

    return PluginContext(name="test", taxonomy=mock_taxonomy)
