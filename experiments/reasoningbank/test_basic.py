"""Basic smoke tests for ReasoningBank experiments.

Verifies core components work without running full experiments.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

def test_blob():
    "Test BlobRef handle pattern."
    from experiments.reasoningbank.core.blob import Store, Ref
    store = Store()
    ref = store.put("Hello world " * 100, "text")
    assert isinstance(ref, Ref)
    assert ref.sz == len("Hello world " * 100)
    assert ref.dtype == "text"
    assert store.get(ref.key) == "Hello world " * 100
    assert len(store.peek(ref.key, 20)) == 20
    print("✓ BlobRef works")

def test_mem():
    "Test memory store."
    from experiments.reasoningbank.core.mem import MemStore, Item
    store = MemStore()
    item = Item(
        id=Item.make_id("Test", "Content"),
        title="Test Procedure",
        desc="A test",
        content="1. Do this\n2. Do that",
        src="seed",
        tags=["test"]
    )
    store.add(item)
    hits = store.search("test", k=5)
    assert len(hits) > 0
    assert hits[0]['title'] == "Test Procedure"
    items = store.get([hits[0]['id']])
    assert len(items) == 1
    assert items[0].content == "1. Do this\n2. Do that"
    print("✓ MemStore works")

def test_packers():
    "Test layer packers."
    from rdflib import Graph
    from experiments.reasoningbank.packers import l0_sense, l1_schema

    g = Graph().parse('ontology/prov.ttl')

    # L0 sense card
    sense = l0_sense.pack(g, budget=600)
    assert 'triples' in sense
    assert 'Formalism' in sense
    assert len(sense) <= 600
    print("✓ L0 sense packer works")

    # L1 schema
    schema = l1_schema.pack(g, budget=1000)
    assert len(schema) <= 1000
    print("✓ L1 schema packer works")

def test_context_builder():
    "Test context builder."
    from rdflib import Graph
    from experiments.reasoningbank.ctx.builder import Cfg, Layer, Builder
    from experiments.reasoningbank.core.mem import MemStore

    cfg = Cfg(l0=Layer(True, 600))
    builder = Builder(cfg)
    g = Graph().parse('ontology/prov.ttl')
    ctx = builder.build(g, "What is Activity?", None)
    assert 'Formalism' in ctx
    print("✓ ContextBuilder works")

if __name__ == '__main__':
    print("\nRunning basic smoke tests...\n")
    test_blob()
    test_mem()
    test_packers()
    test_context_builder()
    print("\n✓ All basic tests passed!\n")
