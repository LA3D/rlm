"""Live integration tests for memory-based architecture.

These tests require:
- ANTHROPIC_API_KEY environment variable
- Real ontology files (ontology/prov.ttl)
- LLM API access
"""

import pytest
from rlm.ontology import setup_ontology_context, build_sense_structured
from rlm.procedural_memory import MemoryStore, bootstrap_general_strategies, retrieve_memories
from rlm.reasoning_bank import rlm_run_enhanced
from rlm.core import rlm_run


@pytest.mark.live
def test_bootstrap_strategies_reduce_iterations():
    """Validates improvement with bootstrap strategies (83% improvement expected)."""
    # Setup ontology
    ns_baseline = {}
    setup_ontology_context('ontology/prov.ttl', ns_baseline, name='prov')
    sense = build_sense_structured('ontology/prov.ttl', name='prov_sense', ns=ns_baseline)

    # Baseline: sense only, no memory
    answer_baseline, iters_baseline, _ = rlm_run_enhanced(
        query="What is the Activity class?",
        context=ns_baseline['prov_meta'].summary(),
        ns=ns_baseline,
        sense=sense,
        memory_store=None,  # No memory
        max_iters=10
    )

    # With bootstrap strategies
    ns_memory = {}
    setup_ontology_context('ontology/prov.ttl', ns_memory, name='prov')

    memory_store = MemoryStore()
    for s in bootstrap_general_strategies():
        memory_store.add(s)

    answer_memory, iters_memory, _ = rlm_run_enhanced(
        query="What is the Activity class?",
        context=ns_memory['prov_meta'].summary(),
        ns=ns_memory,
        sense=sense,
        memory_store=memory_store,
        max_iters=10
    )

    # Assert: memory reduces iterations by >50%
    baseline_count = len(iters_baseline)
    memory_count = len(iters_memory)
    improvement = (baseline_count - memory_count) / baseline_count if baseline_count > 0 else 0

    assert improvement > 0.5, \
        f"Expected >50% improvement, got {improvement*100:.1f}% ({baseline_count} → {memory_count} iters)"

    # Both should produce valid answers
    assert answer_memory is not None and len(answer_memory) > 0
    assert 'Activity' in answer_memory or 'activity' in answer_memory.lower()


@pytest.mark.live
def test_memory_retrieval_is_relevant():
    """BM25 retrieves appropriate strategies for query type."""
    memory_store = MemoryStore()
    for s in bootstrap_general_strategies():
        memory_store.add(s)

    # Entity query should retrieve "Describe Entity"
    entity_mems = retrieve_memories(memory_store, "What is Activity?", k=3)
    titles = [m.title for m in entity_mems]
    assert any('Describe Entity' in t for t in titles), \
        f"Entity query should retrieve 'Describe Entity', got: {titles}"

    # Hierarchy query should retrieve subclass/superclass strategies
    hierarchy_mems = retrieve_memories(memory_store, "Find subclasses of Activity", k=3)
    titles = [m.title for m in hierarchy_mems]
    assert any('Subclass' in t or 'Superclass' in t for t in titles), \
        f"Hierarchy query should retrieve subclass/superclass strategies, got: {titles}"


@pytest.mark.live
def test_sense_plus_memory_full_stack():
    """Full integration: all 4 layers work together.

    Tests:
    - Layer 0: Sense card
    - Layer 1: Retrieved memories (general strategies)
    - Layer 2: Ontology recipes (empty is ok)
    - Layer 3: Base context
    """
    ns = {}
    setup_ontology_context('ontology/prov.ttl', ns, name='prov')
    sense = build_sense_structured('ontology/prov.ttl', name='prov_sense', ns=ns)

    memory_store = MemoryStore()
    for s in bootstrap_general_strategies():
        memory_store.add(s)

    answer, iterations, _ = rlm_run_enhanced(
        query="What is Activity?",
        context=ns['prov_meta'].summary(),
        ns=ns,
        sense=sense,
        memory_store=memory_store,
        ontology='prov',
        max_iters=10
    )

    # Should converge quickly with all layers (≤3 iterations expected)
    assert len(iterations) <= 3, \
        f"Expected ≤3 iterations with full stack, got {len(iterations)}"

    # Should produce valid answer
    assert answer is not None
    assert len(answer) > 0
    assert 'Activity' in answer or 'activity' in answer.lower()


@pytest.mark.live
def test_validate_sense_precondition_on_real_ontology():
    """Test sense validation gate with real PROV ontology."""
    from rlm.ontology import validate_sense_precondition

    ns = {}
    setup_ontology_context('ontology/prov.ttl', ns, name='prov')
    sense = build_sense_structured('ontology/prov.ttl', name='prov_sense', ns=ns)

    result = validate_sense_precondition(sense, ns['prov_meta'])

    # Validation should pass
    assert result['proceed'] == True, f"Validation failed: {result['reason']}"
    assert result['grounding_valid'] == True
    assert result['card_size_ok'] == True
    assert result['has_required_fields'] == True
    assert result['card_size'] <= 800, f"Card size {result['card_size']} > 800 chars"
