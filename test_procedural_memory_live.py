#!/usr/bin/env python3
"""Live tests for procedural memory with real LLM API calls.

This script tests the complete procedural memory loop with real Claude API calls.
It requires ANTHROPIC_API_KEY to be set and will incur API costs.
"""

import sys
from pathlib import Path
import tempfile
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from rlm.procedural_memory import (
    MemoryItem, MemoryStore,
    extract_trajectory_artifact,
    judge_trajectory,
    extract_memories,
    retrieve_memories,
    format_memories_for_injection,
    rlm_run_with_memory
)
from rlm._rlmpaper_compat import RLMIteration, CodeBlock, REPLResult
from rlm.ontology import setup_ontology_context


def test_judge_trajectory():
    """Test judge_trajectory with real LLM."""
    print("\n" + "="*60)
    print("TEST 1: judge_trajectory with real LLM")
    print("="*60)

    # Create a realistic success artifact
    success_artifact = {
        'task': 'What is prov:Activity?',
        'final_answer': 'prov:Activity is a class in the PROV ontology representing activities that occur over a period of time.',
        'iteration_count': 2,
        'converged': True,
        'key_steps': [
            {'iteration': 1, 'action': "search('Activity')", 'outcome': 'Found 3 entities including prov:Activity'},
            {'iteration': 2, 'action': "describe_entity('prov:Activity')", 'outcome': 'prov:Activity is a class'}
        ],
        'variables_created': ['search_results', 'activity_info'],
        'errors_encountered': []
    }

    print("\nJudging SUCCESS trajectory...")
    print(f"Task: {success_artifact['task']}")
    print(f"Answer: {success_artifact['final_answer']}")

    judgment = judge_trajectory(success_artifact)

    print(f"\nJudgment:")
    print(f"  Success: {judgment['is_success']}")
    print(f"  Reason: {judgment['reason']}")
    print(f"  Confidence: {judgment['confidence']}")
    print(f"  Missing: {judgment['missing']}")

    assert isinstance(judgment['is_success'], bool), "is_success should be bool"
    assert isinstance(judgment['reason'], str), "reason should be string"
    assert judgment['confidence'] in ['high', 'medium', 'low'], "confidence should be high/medium/low"

    # Create a failure artifact
    failure_artifact = {
        'task': 'What is prov:Activity?',
        'final_answer': 'No answer provided',
        'iteration_count': 3,
        'converged': False,
        'key_steps': [
            {'iteration': 1, 'action': "search('Activity')", 'outcome': 'ERROR: Connection timeout'},
            {'iteration': 2, 'action': "search('Activity')", 'outcome': 'ERROR: Connection timeout'},
            {'iteration': 3, 'action': "print('giving up')", 'outcome': 'giving up'}
        ],
        'variables_created': [],
        'errors_encountered': ['Connection timeout', 'Connection timeout']
    }

    print("\n" + "-"*60)
    print("Judging FAILURE trajectory...")
    print(f"Task: {failure_artifact['task']}")
    print(f"Answer: {failure_artifact['final_answer']}")

    judgment = judge_trajectory(failure_artifact)

    print(f"\nJudgment:")
    print(f"  Success: {judgment['is_success']}")
    print(f"  Reason: {judgment['reason']}")
    print(f"  Confidence: {judgment['confidence']}")
    print(f"  Missing: {judgment['missing']}")

    print("\n✓ judge_trajectory test passed")


def test_extract_memories():
    """Test extract_memories with real LLM."""
    print("\n" + "="*60)
    print("TEST 2: extract_memories with real LLM")
    print("="*60)

    # Success trajectory
    success_artifact = {
        'task': 'Find properties of prov:Activity',
        'final_answer': 'prov:Activity has properties: prov:startedAtTime, prov:endedAtTime, prov:wasAssociatedWith',
        'iteration_count': 3,
        'converged': True,
        'key_steps': [
            {'iteration': 1, 'action': "search('Activity')", 'outcome': 'Found prov:Activity'},
            {'iteration': 2, 'action': "describe_entity('prov:Activity')", 'outcome': 'A class representing activities'},
            {'iteration': 3, 'action': "get_properties('prov:Activity')", 'outcome': 'Listed 3 properties'}
        ],
        'variables_created': ['activity_props'],
        'errors_encountered': []
    }

    success_judgment = {
        'is_success': True,
        'reason': 'Answer grounded in ontology data with systematic exploration',
        'confidence': 'high',
        'missing': []
    }

    print("\nExtracting memories from SUCCESS trajectory...")
    print(f"Task: {success_artifact['task']}")

    memories = extract_memories(success_artifact, success_judgment)

    print(f"\nExtracted {len(memories)} memories:")
    for i, mem in enumerate(memories, 1):
        print(f"\n{i}. {mem.title}")
        print(f"   Description: {mem.description}")
        print(f"   Source: {mem.source_type}")
        print(f"   Tags: {mem.tags}")
        print(f"   Content preview: {mem.content[:100]}...")

    assert len(memories) <= 3, "Should extract at most 3 memories"
    assert all(isinstance(m, MemoryItem) for m in memories), "All should be MemoryItem"
    assert all(m.source_type == 'success' for m in memories), "All should be success type"

    # Failure trajectory
    failure_artifact = {
        'task': 'Find properties of prov:Activity',
        'final_answer': 'No answer provided',
        'iteration_count': 5,
        'converged': False,
        'key_steps': [
            {'iteration': 1, 'action': "query('SELECT ?p WHERE {prov:Activity ?p ?o}')", 'outcome': 'ERROR: Invalid SPARQL'},
            {'iteration': 2, 'action': "query('SELECT * {prov:Activity ?p ?o}')", 'outcome': 'ERROR: Syntax error'},
            {'iteration': 3, 'action': "search('Activity properties')", 'outcome': 'No results'},
            {'iteration': 4, 'action': "print('stuck')", 'outcome': 'stuck'},
        ],
        'variables_created': [],
        'errors_encountered': ['Invalid SPARQL', 'Syntax error']
    }

    failure_judgment = {
        'is_success': False,
        'reason': 'Failed to produce answer due to repeated SPARQL syntax errors',
        'confidence': 'high',
        'missing': ['Correct SPARQL syntax', 'Query validation']
    }

    print("\n" + "-"*60)
    print("Extracting memories from FAILURE trajectory...")
    print(f"Task: {failure_artifact['task']}")

    memories = extract_memories(failure_artifact, failure_judgment)

    print(f"\nExtracted {len(memories)} memories:")
    for i, mem in enumerate(memories, 1):
        print(f"\n{i}. {mem.title}")
        print(f"   Description: {mem.description}")
        print(f"   Source: {mem.source_type}")
        print(f"   Tags: {mem.tags}")
        print(f"   Content preview: {mem.content[:100]}...")

    if memories:  # May return empty if no lessons
        assert all(m.source_type == 'failure' for m in memories), "All should be failure type"

    print("\n✓ extract_memories test passed")


def test_memory_store_persistence():
    """Test MemoryStore save/load with real memories."""
    print("\n" + "="*60)
    print("TEST 3: Memory store persistence")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / 'test_memories.json'

        # Create store and add memories
        store = MemoryStore(path=store_path)

        mem1 = MemoryItem(
            id='test-1',
            title='SPARQL query pattern for entity search',
            description='Use rdfs:label with FILTER for case-insensitive search.',
            content='- Use rdfs:label predicate\n- Add FILTER with regex\n- Include LIMIT clause',
            source_type='success',
            task_query='Find entities by name',
            created_at=datetime.utcnow().isoformat(),
            tags=['sparql', 'search', 'entity']
        )

        mem2 = MemoryItem(
            id='test-2',
            title='Property exploration strategy',
            description='Systematically explore properties using describe then probe.',
            content='- Start with describe_entity()\n- Use get_properties() for details\n- Check domain and range',
            source_type='success',
            task_query='What properties does X have?',
            created_at=datetime.utcnow().isoformat(),
            tags=['properties', 'exploration']
        )

        store.add(mem1)
        store.add(mem2)

        print(f"Added {len(store.memories)} memories")

        # Save
        result = store.save()
        print(f"Save result: {result}")
        assert store_path.exists(), "Store file should exist"

        # Load
        loaded = MemoryStore.load(store_path)
        print(f"Loaded {len(loaded.memories)} memories")

        assert len(loaded.memories) == 2, "Should load 2 memories"
        assert loaded.memories[0].title == mem1.title, "Title should match"
        assert loaded.memories[1].tags == mem2.tags, "Tags should match"

        # Test retrieval
        results = retrieve_memories(loaded, 'How do I search for entities in SPARQL?', k=2)
        print(f"\nRetrieved {len(results)} memories for search query")
        for r in results:
            print(f"  - {r.title} (accessed {r.access_count} times)")

        assert len(results) > 0, "Should retrieve at least one memory"
        assert results[0].access_count > 0, "Access count should increment"

        # Test injection formatting
        formatted = format_memories_for_injection(results, max_bullets=3)
        print(f"\nFormatted for injection ({len(formatted)} chars):")
        print(formatted[:200] + "...")

        assert '## Relevant Prior Experience' in formatted
        assert 'assess which of these strategies' in formatted

        print("\n✓ Memory store persistence test passed")


def test_integration_with_rlm():
    """Test full integration with rlm_run_with_memory."""
    print("\n" + "="*60)
    print("TEST 4: Full integration with rlm_run_with_memory")
    print("="*60)

    # Check if PROV ontology exists
    prov_path = Path('ontology/prov.ttl')
    if not prov_path.exists():
        print(f"⚠ Skipping integration test - {prov_path} not found")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(path=Path(tmpdir) / 'integration_test.json')

        # First run - no memories
        print("\n--- First Run (no prior memories) ---")
        ns = {}
        setup_ontology_context('ontology/prov.ttl', ns, name='prov')

        query1 = "What is prov:Activity?"
        print(f"Query: {query1}")

        answer1, iters1, ns1, mems1 = rlm_run_with_memory(
            query1,
            ns['prov_meta'].summary(),
            store,
            ns=ns,
            max_iters=5
        )

        print(f"\nAnswer: {answer1}")
        print(f"Iterations: {len(iters1)}")
        print(f"Memories extracted: {len(mems1)}")
        for mem in mems1:
            print(f"  - {mem.title} [{mem.source_type}]")

        assert answer1 is not None or len(iters1) > 0, "Should produce answer or iterations"
        print(f"Store now has {len(store.memories)} memories")

        # Second run - similar task, should retrieve memories
        print("\n" + "-"*60)
        print("--- Second Run (with prior memories) ---")
        ns2 = {}
        setup_ontology_context('ontology/prov.ttl', ns2, name='prov')

        query2 = "What is prov:Entity?"
        print(f"Query: {query2}")

        # Check what memories would be retrieved
        relevant = retrieve_memories(store, query2, k=3)
        print(f"\nMemories being retrieved for second run: {len(relevant)}")
        for r in relevant:
            print(f"  - {r.title}")

        answer2, iters2, ns2, mems2 = rlm_run_with_memory(
            query2,
            ns2['prov_meta'].summary(),
            store,
            ns=ns2,
            max_iters=5
        )

        print(f"\nAnswer: {answer2}")
        print(f"Iterations: {len(iters2)}")
        print(f"New memories extracted: {len(mems2)}")
        for mem in mems2:
            print(f"  - {mem.title} [{mem.source_type}]")

        print(f"\nFinal store has {len(store.memories)} memories")

        # Show all memories with access counts
        print("\n--- All Memories in Store ---")
        for mem in store.memories:
            print(f"\n{mem.title}")
            print(f"  Source: {mem.source_type}")
            print(f"  Accessed: {mem.access_count} times")
            print(f"  Tags: {mem.tags}")

        # Verify persistence
        assert store.path.exists(), "Store should be saved to disk"
        loaded = MemoryStore.load(store.path)
        assert len(loaded.memories) == len(store.memories), "Should persist all memories"

        print("\n✓ Full integration test passed")


def main():
    """Run all live tests."""
    print("="*60)
    print("PROCEDURAL MEMORY - LIVE TESTS WITH REAL LLM")
    print("="*60)
    print("\nThese tests make real Claude API calls and will incur costs.")
    print("Make sure ANTHROPIC_API_KEY is set in your environment.")

    try:
        # Test 1: Judge
        test_judge_trajectory()

        # Test 2: Extractor
        test_extract_memories()

        # Test 3: Persistence
        test_memory_store_persistence()

        # Test 4: Full integration
        test_integration_with_rlm()

        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
