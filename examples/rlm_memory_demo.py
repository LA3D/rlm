#!/usr/bin/env python3
"""Interactive demo of RLM with dataset memory.

Run this to see RLM using memory operations in action.

Usage:
    python examples/rlm_memory_demo.py
"""

from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context
from rlm.ontology import setup_ontology_context
from pathlib import Path


def simple_demo():
    """Simple demo: RLM stores and retrieves facts."""
    print("\n" + "="*70)
    print("DEMO 1: Basic Memory Operations")
    print("="*70)

    ns = {}
    setup_dataset_context(ns)

    context = """
You have access to these memory operations:

```python
# Add a fact to memory
mem_add(subject_uri, predicate_uri, object_uri_or_literal,
        source='agent', reason='Optional explanation')

# Query memory with SPARQL
results = mem_query('SELECT ?s ?p ?o WHERE { ?s ?p ?o }', limit=100)

# Describe an entity
desc = mem_describe('http://example.org/alice')
```

Store facts in memory as you discover them.
"""

    query = """
Please do the following:
1. Store this fact: Alice (http://ex.org/alice) is 30 years old (http://ex.org/age)
2. Store this fact: Bob (http://ex.org/bob) is 25 years old
3. Query memory to verify both facts were stored
4. Tell me what you found
"""

    print(f"\nQuery: {query}")
    print("\nRunning RLM...")
    print("-" * 70)

    answer, iterations, ns = rlm_run(
        query=query,
        context=context,
        ns=ns,
        max_iters=5
    )

    print(f"\n{'='*70}")
    print(f"RLM Answer: {answer}")
    print(f"{'='*70}")

    # Show what happened
    ds_meta = ns['ds_meta']
    print(f"\nMemory Statistics:")
    print(f"  Triples stored: {len(ds_meta.mem)}")
    print(f"  Provenance events: {len(ds_meta.prov)}")
    print(f"  Iterations used: {len(iterations)}")
    print(f"  Session ID: {ds_meta.session_id}")

    print(f"\nMemory Contents:")
    for s, p, o in ds_meta.mem.triples((None, None, None)):
        print(f"  {s}")
        print(f"    {p}")
        print(f"      {o}")

    print(f"\nProvenance Sample (showing event types):")
    from rdflib import RDF
    for event in list(ds_meta.prov.subjects(RDF.type, None))[:3]:
        event_type = list(ds_meta.prov.objects(event, RDF.type))[0]
        print(f"  Event: {event}")
        print(f"    Type: {event_type}")
        # Show other properties
        for p, o in list(ds_meta.prov.predicate_objects(event))[:5]:
            if p != RDF.type:
                print(f"    {str(p).split('/')[-1]}: {o}")

    return ns


def ontology_demo():
    """Demo: RLM uses ontology to guide memory storage."""
    print("\n" + "="*70)
    print("DEMO 2: Ontology + Memory Integration")
    print("="*70)

    ont_path = Path('ontology/prov.ttl')
    if not ont_path.exists():
        print("Skipping: prov.ttl not found")
        return

    ns = {}
    setup_dataset_context(ns)
    setup_ontology_context(str(ont_path), ns, name='prov')

    context = """
You have access to:

1. PROV Ontology (in prov_meta):
   - prov_meta.classes - list of all classes
   - prov_meta.labels - dict of URI -> label
   - search_by_label(search_text) - find entities by label
   - describe_entity(uri) - get entity details

2. Memory Operations:
   - mem_add(subject, predicate, object, source='agent', reason='...')
   - mem_query(sparql)

Strategy: Use the ontology to understand concepts, then store examples in memory.
"""

    query = """
Please do the following:
1. Search the PROV ontology for the "Activity" class
2. Get its definition/comment
3. Store a note about it in memory using this pattern:
   - subject: the Activity class URI
   - predicate: http://example.org/myNote
   - object: your summary of what Activity means
4. Query memory to verify it was stored
"""

    print(f"\nQuery: {query}")
    print("\nRunning RLM...")
    print("-" * 70)

    answer, iterations, ns = rlm_run(
        query=query,
        context=context,
        ns=ns,
        max_iters=8
    )

    print(f"\n{'='*70}")
    print(f"RLM Answer: {answer}")
    print(f"{'='*70}")

    # Show integration
    print(f"\nOntology Statistics:")
    print(f"  Classes: {len(ns['prov_meta'].classes)}")
    print(f"  Properties: {len(ns['prov_meta'].properties)}")

    print(f"\nMemory Statistics:")
    print(f"  Triples stored: {len(ns['ds_meta'].mem)}")
    print(f"  Provenance events: {len(ns['ds_meta'].prov)}")

    print(f"\nMemory Contents:")
    for s, p, o in ns['ds_meta'].mem.triples((None, None, None)):
        print(f"  Subject: {s}")
        print(f"  Predicate: {p}")
        print(f"  Note: {o}")

    return ns


def multi_turn_demo():
    """Demo: Memory persists across multiple RLM runs."""
    print("\n" + "="*70)
    print("DEMO 3: Memory Persistence Across Turns")
    print("="*70)

    ns = {}
    setup_dataset_context(ns)

    context = "You have mem_add(), mem_query(), and mem_describe() available."

    # Turn 1
    print("\n--- Turn 1: Store initial facts ---")
    query1 = "Store these relationships: Alice knows Bob, Bob knows Charlie, Charlie knows Diana."

    answer1, iters1, ns = rlm_run(query1, context, ns=ns, max_iters=5)
    print(f"Answer: {answer1}")
    print(f"Memory now has: {len(ns['ds_meta'].mem)} triples")

    # Turn 2
    print("\n--- Turn 2: Query stored facts ---")
    query2 = "Who does Bob know? Use mem_query to find out."

    answer2, iters2, ns = rlm_run(query2, context, ns=ns, max_iters=5)
    print(f"Answer: {answer2}")
    print(f"Memory still has: {len(ns['ds_meta'].mem)} triples")

    # Turn 3
    print("\n--- Turn 3: Add more facts ---")
    query3 = "Add this: Diana knows Alice. Then find all transitive relationships."

    answer3, iters3, ns = rlm_run(query3, context, ns=ns, max_iters=5)
    print(f"Answer: {answer3}")
    print(f"Memory now has: {len(ns['ds_meta'].mem)} triples")

    print(f"\n{'='*70}")
    print(f"Total iterations across 3 turns: {len(iters1) + len(iters2) + len(iters3)}")
    print(f"Session ID (same throughout): {ns['ds_meta'].session_id}")
    print(f"Provenance events: {len(ns['ds_meta'].prov)}")
    print(f"{'='*70}")

    return ns


def snapshot_demo():
    """Demo: Save and restore dataset snapshots."""
    print("\n" + "="*70)
    print("DEMO 4: Snapshot & Restore")
    print("="*70)

    # Create and populate
    ns = {}
    setup_dataset_context(ns)

    print("Storing some facts in memory...")
    ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30')
    ns['mem_add']('http://ex.org/bob', 'http://ex.org/age', '25')

    print(f"Memory has {len(ns['ds_meta'].mem)} triples")

    # Save snapshot
    import tempfile
    snapshot_path = tempfile.mktemp(suffix='.trig')
    result = ns['snapshot_dataset'](path=snapshot_path)
    print(f"\n{result}")

    # Show snapshot contents
    print(f"\nSnapshot file preview:")
    with open(snapshot_path, 'r') as f:
        lines = f.readlines()
        for line in lines[:20]:  # First 20 lines
            print(f"  {line.rstrip()}")

    # Restore in new namespace
    from rlm.dataset import load_snapshot
    ns2 = {}
    result = load_snapshot(snapshot_path, ns2, name='restored')
    print(f"\n{result}")
    print(f"Restored memory has: {len(ns2['restored_meta'].mem)} triples")

    # Cleanup
    import os
    os.unlink(snapshot_path)

    return ns2


if __name__ == '__main__':
    print("\n" + "="*70)
    print(" RLM Dataset Memory - Interactive Demo")
    print("="*70)

    try:
        # Run demos
        simple_demo()
        multi_turn_demo()
        ontology_demo()
        snapshot_demo()

        print("\n" + "="*70)
        print(" ✓ All demos completed successfully!")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
