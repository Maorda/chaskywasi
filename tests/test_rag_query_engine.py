from chaskiwasi.query_engine.cross_filter import CrossQueryFilter
from chaskiwasi.query_engine.rag_query_engine import RagQueryEngine


class FakeCollection:
    def __init__(self):
        self.kwargs = None

    def query(self, **kwargs):
        self.kwargs = kwargs
        return {"ids": [["demo_DOC-1_0"]]}


class FakeManager:
    def __init__(self):
        self.collection = FakeCollection()

    def get_or_create_collection(self, name):
        return self.collection


def test_rag_query_engine_builds_plugin_and_intent_filters():
    query_filter = CrossQueryFilter(
        load_plugins=False,
        custom_rules=[],
    )
    manager = FakeManager()
    engine = RagQueryEngine("docs", manager=manager, query_filter=query_filter)

    result = engine.search("consulta general", doc_id="DOC-1", plugin_name="demo")

    assert result == {"ids": [["demo_DOC-1_0"]]}
    assert manager.collection.kwargs["where"] == {
        "$and": [
            {"id_documento": "DOC-1"},
            {"plugin": "demo"},
        ]
    }
