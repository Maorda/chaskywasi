from unittest.mock import MagicMock, patch

import pytest

from chaskiwasi.query_engine.cross_filter import CrossQueryFilter, IntentRule


@pytest.fixture
def generic_rules():
    """Reglas agnósticas de prueba para verificar el motor sin depender de un dominio específico."""
    return [
        IntentRule(
            keywords=["médico", "doctor", "hospital"],
            metadata_filter={"$and": [{"domain": "health"}]},
        ),
        IntentRule(
            keywords=["banco", "finanzas", "préstamo"],
            metadata_filter={"$and": [{"domain": "finance"}]},
        ),
    ]


def test_empty_or_none_query_returns_base_filter(generic_rules):
    filter_engine = CrossQueryFilter(load_plugins=False, custom_rules=generic_rules)
    
    res_empty = filter_engine.generate_where_clause("", "doc-123")
    res_none = filter_engine.generate_where_clause(None, "doc-123")
    res_spaces = filter_engine.generate_where_clause("   ", "doc-123")
    
    expected = {"id_documento": "doc-123"}
    assert res_empty == expected
    assert res_none == expected
    assert res_spaces == expected


def test_no_match_returns_base_filter(generic_rules):
    filter_engine = CrossQueryFilter(load_plugins=False, custom_rules=generic_rules)
    
    result = filter_engine.generate_where_clause("consulta de ingeniería civil", "doc-456")
    assert result == {"id_documento": "doc-456"}


def test_match_applies_correct_rule(generic_rules):
    filter_engine = CrossQueryFilter(load_plugins=False, custom_rules=generic_rules)
    
    result = filter_engine.generate_where_clause("necesito ver a un doctor urgente", "doc-789")
    
    expected = {
        "$and": [
            {"id_documento": "doc-789"},
            {"$and": [{"domain": "health"}]}
        ]
    }
    assert result == expected


@patch("importlib.metadata.entry_points")
def test_plugin_auto_discovery(mock_entry_points):
    """Verifica que el motor descubre e inyecta reglas desde paquetes externos (Entry Points)."""
    
    mock_ep = MagicMock()
    mock_ep.name = "mock_plugin"
    # Simulamos que el plugin externo retorna una lista de IntentRules
    mock_ep.load.return_value = lambda: [
        IntentRule(keywords=["plugin_test"], metadata_filter={"source": "external_plugin"})
    ]
    
    mock_entry_points.return_value = [mock_ep]
    
    filter_engine = CrossQueryFilter(load_plugins=True)
    
    assert len(filter_engine.rules) == 1
    assert filter_engine.rules[0].keywords == ["plugin_test"]
    
    # Validamos que el enrutamiento funciona con la regla inyectada dinámicamente
    result = filter_engine.generate_where_clause("este es un plugin_test", "doc-999")
    expected = {
        "$and": [
            {"id_documento": "doc-999"},
            {"source": "external_plugin"}
        ]
    }
    assert result == expected