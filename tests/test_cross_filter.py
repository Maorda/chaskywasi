# tests/test_cross_filter.py

from chaskiwasi.query_engine.cross_filter import (
    CrossQueryFilter,
)

from chaskiwasi_plugin_remaju.query_rules import (
    get_query_rules,
)


def test_single_intent_keeps_section_filter():
    query_filter = CrossQueryFilter(
        load_plugins=False,
        custom_rules=get_query_rules(),
    )

    result = query_filter.generate_where_clause(
        "¿Quién es el demandado?"
    )

    assert result == {
        "$and": [
            {
                "$and": [
                    {
                        "fuente": "remaju_resolution"
                    },
                    {
                        "tipo_seccion": "header"
                    },
                ]
            }
        ]
    }

    def test_multiple_intents_are_combined_with_or():
        query_filter = CrossQueryFilter(
            load_plugins=False,
            custom_rules=get_query_rules(),
        )

        result = query_filter.generate_where_clause(
            "demandado y dirección del inmueble"
        )

        serialized = str(result)

        assert "$or" in serialized
        assert "header" in serialized
        assert "body" in serialized
    def test_cartel_intent_does_not_require_footer():
        query_filter = CrossQueryFilter(
            load_plugins=False,
            custom_rules=get_query_rules(),
        )

        result = query_filter.generate_where_clause(
            "¿Se ordenó fijar carteles?"
        )

        serialized = str(result)

        assert "remaju_resolution" in serialized
        assert "footer" not in serialized