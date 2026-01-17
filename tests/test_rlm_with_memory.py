"""Test RLM with dataset memory integration.

This demonstrates how RLM can use memory operations to build up knowledge
across iterations and track provenance.
"""

from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context
from rlm.ontology import setup_ontology_context
from pathlib import Path


def test_rlm_basic_memory():
    """Test RLM can add to and query memory."""
    ns = {}
    setup_dataset_context(ns)

    context = """
You have access to memory operations:
- mem_add(subject, predicate, object, source='agent', reason=None)
- mem_query(sparql, limit=100)
- mem_describe(uri, limit=20)

Store facts you discover in memory.
"""

    query = "Remember that Alice is 30 years old and Bob is 25 years old. Then query memory to confirm what you stored."

    answer, iterations, ns = rlm_run(
        query=query,
        context=context,
        ns=ns,
        max_iters=5
    )

    # Verify memory was used
    ds_meta = ns['ds_meta']
    assert len(ds_meta.mem) >= 2, "Should have stored at least 2 facts"
    assert len(ds_meta.prov) > 0, "Should have provenance records"

    # Verify RLM found the answer
    assert answer is not None, "RLM should have returned an answer"

    print(f"✓ Memory: {len(ds_meta.mem)} triples")
    print(f"✓ Provenance: {len(ds_meta.prov)} events")
    print(f"✓ Iterations: {len(iterations)}")
    print(f"✓ Answer: {answer[:100]}...")

    return ns


def test_rlm_with_ontology_memory():
    """Test RLM using ontology + memory together."""
    # Find ontology file
    ont_path = Path('ontology/prov.ttl')
    if not ont_path.exists():
        print("Skipping: prov.ttl not found")
        return

    ns = {}
    setup_dataset_context(ns)
    setup_ontology_context(str(ont_path), ns, name='prov')

    context = """
You have access to:
1. The PROV ontology in 'prov_meta' with classes and properties
2. Memory operations: mem_add(), mem_query(), mem_describe()

Use the ontology to understand PROV concepts, then store examples in memory.
"""

    query = """
Find the Activity class in the PROV ontology.
Store its comment in memory using the pattern:
  subject: http://www.w3.org/ns/prov#Activity
  predicate: http://example.org/hasNote
  object: <the comment text>

Then query memory to verify it was stored.
"""

    answer, iterations, ns = rlm_run(
        query=query,
        context=context,
        ns=ns,
        max_iters=8
    )

    # Verify ontology was used
    prov_meta = ns['prov_meta']
    assert len(prov_meta.classes) > 0, "Should have loaded ontology classes"

    # Verify memory was used
    ds_meta = ns['ds_meta']
    assert len(ds_meta.mem) > 0, "Should have stored facts from ontology"
    assert len(ds_meta.prov) > 0, "Should have provenance"

    # Verify answer
    assert answer is not None, "RLM should have completed"

    print(f"✓ Ontology classes: {len(prov_meta.classes)}")
    print(f"✓ Memory: {len(ds_meta.mem)} triples")
    print(f"✓ Provenance: {len(ds_meta.prov)} events")
    print(f"✓ Iterations: {len(iterations)}")

    # Show what was stored
    print("\nMemory contents:")
    for s, p, o in list(ds_meta.mem.triples((None, None, None)))[:5]:
        print(f"  {s}\n    {p}\n      {o}")

    return ns


def test_rlm_memory_persistence():
    """Test that memory persists across multiple RLM runs in same namespace."""
    ns = {}
    setup_dataset_context(ns)

    context = "You have memory operations: mem_add(), mem_query()"

    # First run: store facts
    query1 = "Store these facts: Alice knows Bob, Bob knows Charlie."
    answer1, iters1, ns = rlm_run(query1, context, ns=ns, max_iters=5)

    mem_size_after_first = len(ns['ds_meta'].mem)
    assert mem_size_after_first > 0, "First run should add to memory"

    # Second run: use stored facts
    query2 = "Query memory to find who knows who. List all relationships."
    answer2, iters2, ns = rlm_run(query2, context, ns=ns, max_iters=5)

    # Memory should still have facts from first run
    assert len(ns['ds_meta'].mem) >= mem_size_after_first, "Memory should persist"

    # Provenance should track both runs
    assert len(ns['ds_meta'].prov) > 0, "Should have provenance from both runs"

    print(f"✓ First run stored: {mem_size_after_first} triples")
    print(f"✓ Memory persisted across runs")
    print(f"✓ Total iterations: {len(iters1) + len(iters2)}")
    print(f"✓ Session ID: {ns['ds_meta'].session_id}")

    return ns


def test_rlm_work_graph_workflow():
    """Test RLM using work graphs for intermediate results."""
    ns = {}
    setup_dataset_context(ns)

    context = """
You have access to:
- mem_add(), mem_query() for permanent memory
- work_create(task_id) returns (uri, graph) for temporary work
- work_to_mem(task_id, reason=...) to promote validated results
- work_cleanup(task_id) to remove scratch graphs

Use work graphs for intermediate analysis before adding to memory.
"""

    query = """
Create a work graph called 'analysis'.
Add some test triples to it.
Then promote only the validated ones to memory.
Clean up the work graph when done.
"""

    answer, iterations, ns = rlm_run(
        query=query,
        context=context,
        ns=ns,
        max_iters=8
    )

    ds_meta = ns['ds_meta']

    # Work graphs should be cleaned up
    assert len(ds_meta.work_graphs) == 0, "Work graphs should be cleaned up"

    # But memory should have the promoted facts
    assert len(ds_meta.mem) > 0, "Should have promoted facts to memory"

    # Provenance should show promotion
    prov_triples = list(ds_meta.prov.triples((None, None, None)))
    prov_str = '\n'.join(str(t) for t in prov_triples)

    print(f"✓ Memory: {len(ds_meta.mem)} triples")
    print(f"✓ Work graphs cleaned: {len(ds_meta.work_graphs)}")
    print(f"✓ Provenance events: {len(ds_meta.prov)}")

    return ns


def demo_rlm_memory_inspection():
    """Demo showing how to inspect RLM's memory usage."""
    print("\n" + "="*60)
    print("RLM Memory Demo")
    print("="*60)

    ns = test_rlm_basic_memory()

    print("\n--- Dataset Summary ---")
    print(ns['dataset_stats']())

    print("\n--- All Named Graphs ---")
    for graph_uri, count in ns['list_graphs']():
        print(f"  {graph_uri}: {count} triples")

    print("\n--- Memory Sample ---")
    mem_uri = f"urn:rlm:{ns['ds_meta'].name}:mem"
    sample = ns['graph_sample'](mem_uri, limit=5)
    for s, p, o in sample:
        print(f"  ({s}, {p}, {o})")

    print("\n--- Provenance Sample ---")
    prov_uri = f"urn:rlm:{ns['ds_meta'].name}:prov"
    prov_sample = ns['graph_sample'](prov_uri, limit=10)
    for s, p, o in prov_sample:
        print(f"  {p.split('/')[-1]}: {o}")


if __name__ == '__main__':
    print("Testing RLM with Dataset Memory\n")

    print("1. Basic memory operations...")
    test_rlm_basic_memory()

    print("\n2. Memory persistence across runs...")
    test_rlm_memory_persistence()

    print("\n3. Work graph workflow...")
    test_rlm_work_graph_workflow()

    print("\n4. Ontology + memory integration...")
    test_rlm_with_ontology_memory()

    print("\n5. Running memory inspection demo...")
    demo_rlm_memory_inspection()

    print("\n" + "="*60)
    print("✓ All RLM memory tests passed!")
    print("="*60)
