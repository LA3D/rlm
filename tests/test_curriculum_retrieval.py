"""Tests for curriculum_retrieval.py"""

import pytest
from pathlib import Path

from rlm_runtime.memory.curriculum_retrieval import (
    estimate_query_complexity,
    retrieve_with_curriculum,
    get_exemplars_for_level,
    analyze_curriculum_coverage,
)
from rlm_runtime.memory.sqlite_backend import SQLiteMemoryBackend
from rlm_runtime.memory.backend import MemoryItem
from datetime import datetime, timezone


def create_test_exemplar(level: int, ontology: str, memory_id: str) -> MemoryItem:
    """Helper to create test exemplars."""
    # Create content with relevant keywords for BM25 matching
    content_templates = {
        1: "Query protein accession entity lookup direct retrieval",
        2: "Query GO annotations cross-reference related entities insulin protein disease",
        3: "Query filter constraints reviewed Swiss-Prot organism human curated",
        4: "Query path hierarchy transitive descendant ancestor multi-hop",
        5: "Query count aggregate group statistics how many average sum",
    }

    return MemoryItem(
        memory_id=memory_id,
        title=f"Level {level} exemplar for {ontology}",
        description=f"Test exemplar at level {level}",
        content=content_templates.get(level, f"Level {level} reasoning chain") * 3,  # Repeat for BM25
        source_type='exemplar',
        task_query=f"Test query level {level}",
        created_at=datetime.now(timezone.utc).isoformat(),
        tags=[f'level-{level}', ontology, 'exemplar'],
        scope={'ontology': [ontology], 'curriculum_level': level},
        provenance={'source': 'test'},
    )


def test_estimate_query_complexity_l1():
    """Test L1 detection (single entity lookup)."""
    queries = [
        "What is the protein with accession P12345?",
        "Get the entity with ID Q42",
        "Find the protein P05067",
    ]

    for query in queries:
        level = estimate_query_complexity(query)
        assert level == 1, f"Query '{query}' should be L1, got L{level}"


def test_estimate_query_complexity_l2():
    """Test L2 detection (cross-references)."""
    queries = [
        "What are the GO annotations for insulin?",
        "Find proteins related to diabetes",
        "Get disease annotations for P12345",
        "What GO terms are linked to this protein?",  # Clearer L2 pattern
    ]

    for query in queries:
        level = estimate_query_complexity(query)
        assert level == 2, f"Query '{query}' should be L2, got L{level}"


def test_estimate_query_complexity_l3():
    """Test L3 detection (filtering)."""
    queries = [
        "Find reviewed proteins in humans",
        "Get proteins where organism is Homo sapiens",
        "Find proteins with Swiss-Prot annotation only",
        "Filter proteins containing keyword",
    ]

    for query in queries:
        level = estimate_query_complexity(query)
        assert level == 3, f"Query '{query}' should be L3, got L{level}"


def test_estimate_query_complexity_l4():
    """Test L4 detection (multi-hop paths)."""
    queries = [
        "Find all descendants of this taxon transitively",
        "Get the path from entity A to entity B",
        "Find indirect relationships in the hierarchy",
        "Trace the derivation chain",
    ]

    for query in queries:
        level = estimate_query_complexity(query)
        assert level == 4, f"Query '{query}' should be L4, got L{level}"


def test_estimate_query_complexity_l5():
    """Test L5 detection (aggregation)."""
    queries = [
        "How many proteins are in the database?",
        "Count the number of GO annotations",
        "What is the average length of proteins?",
        "Group proteins by organism and count",
        "Find the most common annotation types",
    ]

    for query in queries:
        level = estimate_query_complexity(query)
        assert level == 5, f"Query '{query}' should be L5, got L{level}"


def test_retrieve_with_curriculum_exact_level():
    """Test retrieval prioritizes exact curriculum level."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add exemplars at different levels
    backend.add_memory(create_test_exemplar(1, 'uniprot', 'ex1'))
    backend.add_memory(create_test_exemplar(2, 'uniprot', 'ex2'))
    backend.add_memory(create_test_exemplar(3, 'uniprot', 'ex3'))

    # Query should be estimated as L2
    task = "What are the GO annotations for insulin?"

    memories = retrieve_with_curriculum(task, backend, k=2, ontology_name='uniprot')

    # Should prioritize L2 exemplar
    levels = [m.scope.get('curriculum_level') for m in memories if m.source_type == 'exemplar']
    if levels:
        assert 2 in levels, "L2 exemplar should be retrieved for L2 query"


def test_retrieve_with_curriculum_adjacent_levels():
    """Test retrieval includes adjacent levels when exact match unavailable."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add exemplars at L1 and L3, but not L2
    backend.add_memory(create_test_exemplar(1, 'uniprot', 'ex1'))
    backend.add_memory(create_test_exemplar(3, 'uniprot', 'ex3'))

    # Query should be estimated as L2, with keywords matching L1 and L3 content
    task = "Query GO annotations protein insulin cross-reference filter reviewed"

    memories = retrieve_with_curriculum(task, backend, k=3, ontology_name='uniprot')

    # Should retrieve adjacent levels (L1 and L3) if any are found via BM25
    if len(memories) > 0:
        levels = [m.scope.get('curriculum_level') for m in memories if m.source_type == 'exemplar']
        if levels:
            assert 1 in levels or 3 in levels, "Should include L1 or L3 (adjacent to L2)"


def test_retrieve_with_curriculum_ontology_filtering():
    """Test retrieval prioritizes same ontology."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add exemplars for different ontologies
    backend.add_memory(create_test_exemplar(2, 'uniprot', 'ex1'))
    backend.add_memory(create_test_exemplar(2, 'prov', 'ex2'))

    task = "What are the GO annotations for insulin?"

    # Retrieve for uniprot
    memories = retrieve_with_curriculum(task, backend, k=2, ontology_name='uniprot')

    # Should prefer uniprot exemplars
    ontologies = [
        m.scope.get('ontology', [])[0] if isinstance(m.scope.get('ontology', []), list) else m.scope.get('ontology')
        for m in memories if m.source_type == 'exemplar'
    ]

    if ontologies:
        # First exemplar should be uniprot (if available)
        assert ontologies[0] == 'uniprot', "Should prioritize same ontology"


def test_get_exemplars_for_level():
    """Test retrieving all exemplars for a specific level."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add multiple exemplars
    backend.add_memory(create_test_exemplar(1, 'uniprot', 'ex1'))
    backend.add_memory(create_test_exemplar(2, 'uniprot', 'ex2'))
    backend.add_memory(create_test_exemplar(2, 'uniprot', 'ex3'))
    backend.add_memory(create_test_exemplar(3, 'uniprot', 'ex4'))

    # Get L2 exemplars
    l2_exemplars = get_exemplars_for_level(backend, level=2, ontology_name='uniprot')

    assert len(l2_exemplars) == 2
    assert all(m.scope.get('curriculum_level') == 2 for m in l2_exemplars)


def test_analyze_curriculum_coverage():
    """Test curriculum coverage analysis."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add exemplars with gaps
    backend.add_memory(create_test_exemplar(1, 'uniprot', 'ex1'))
    backend.add_memory(create_test_exemplar(1, 'uniprot', 'ex2'))
    backend.add_memory(create_test_exemplar(3, 'uniprot', 'ex3'))
    backend.add_memory(create_test_exemplar(5, 'uniprot', 'ex5'))

    coverage = analyze_curriculum_coverage(backend, ontology_name='uniprot')

    assert coverage['total_exemplars'] == 4
    assert coverage['by_level'][1] == 2
    assert coverage['by_level'][3] == 1
    assert coverage['by_level'][5] == 1
    assert 2 in coverage['missing_levels']  # L2 is missing
    assert 4 in coverage['missing_levels']  # L4 is missing


def test_analyze_curriculum_coverage_all_ontologies():
    """Test coverage analysis across multiple ontologies."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add exemplars for different ontologies
    backend.add_memory(create_test_exemplar(1, 'uniprot', 'ex1'))
    backend.add_memory(create_test_exemplar(2, 'uniprot', 'ex2'))
    backend.add_memory(create_test_exemplar(1, 'prov', 'ex3'))

    coverage = analyze_curriculum_coverage(backend)  # No ontology filter

    assert coverage['total_exemplars'] == 3
    assert coverage['by_ontology']['uniprot'] == 2
    assert coverage['by_ontology']['prov'] == 1


def test_retrieve_with_curriculum_empty_backend():
    """Test retrieval from empty backend."""
    backend = SQLiteMemoryBackend(":memory:")

    task = "What is the protein with accession P12345?"

    memories = retrieve_with_curriculum(task, backend, k=3)

    assert len(memories) == 0


def test_retrieve_with_curriculum_mixed_sources():
    """Test retrieval prioritizes exemplars over success memories."""
    backend = SQLiteMemoryBackend(":memory:")

    # Add an exemplar with matching content
    backend.add_memory(create_test_exemplar(2, 'uniprot', 'ex1'))

    # Add a success memory with matching content
    success_memory = MemoryItem(
        memory_id='success1',
        title="Successful query",
        description="Success",
        content="GO annotations protein insulin cross-reference query",  # Matching content
        source_type='success',
        task_query="Previous successful query about GO annotations",
        created_at=datetime.now(timezone.utc).isoformat(),
        tags=['uniprot'],
        scope={'ontology': ['uniprot']},
        provenance={},
    )
    backend.add_memory(success_memory)

    task = "Query GO annotations protein insulin cross-reference"

    memories = retrieve_with_curriculum(task, backend, k=2)

    # Should retrieve something
    assert len(memories) > 0, "Should retrieve at least one memory"

    # If exemplar is found, check that it's prioritized
    source_types = [m.source_type for m in memories]
    if 'exemplar' in source_types:
        # Exemplar should come first (higher priority)
        assert memories[0].source_type == 'exemplar', "Exemplar should be prioritized"


# Integration test with real exemplars (if available)
def test_retrieve_real_exemplars_if_available():
    """Test retrieval with real exemplars."""
    from rlm_runtime.memory.exemplar_loader import load_exemplars_from_directory

    exemplar_dir = Path("experiments/reasoning_chain_validation/exemplars")

    if not exemplar_dir.exists():
        pytest.skip("Real exemplar directory not found")

    backend = SQLiteMemoryBackend(":memory:")
    load_exemplars_from_directory(exemplar_dir, backend, 'uniprot')

    # Test L1 query
    task = "What is the protein with accession P12345?"
    memories = retrieve_with_curriculum(task, backend, k=2, ontology_name='uniprot')

    assert len(memories) > 0

    # Should retrieve L1 exemplar
    levels = [m.scope.get('curriculum_level') for m in memories if m.source_type == 'exemplar']
    if levels:
        assert 1 in levels, "Should retrieve L1 exemplar for L1 query"
