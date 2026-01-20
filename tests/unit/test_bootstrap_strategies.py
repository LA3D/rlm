"""Unit tests for bootstrap general strategies."""

import pytest
from rlm.procedural_memory import (
    bootstrap_general_strategies,
    MemoryItem,
    MemoryStore,
    validate_bootstrap_strategies
)
import tempfile
from pathlib import Path


def test_bootstrap_creates_seven_strategies():
    """Bootstrap returns exactly 7 MemoryItem objects."""
    strategies = bootstrap_general_strategies()
    assert len(strategies) == 7
    assert all(isinstance(s, MemoryItem) for s in strategies)


def test_bootstrap_strategies_serializable():
    """All strategies can be saved/loaded from JSON."""
    strategies = bootstrap_general_strategies()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / 'test_bootstrap.json'
        store = MemoryStore(path=test_path)

        for s in strategies:
            store.add(s)

        store.save()

        # Reload
        loaded = MemoryStore.load(test_path)
        assert len(loaded.memories) == 7
        assert loaded.memories[0].title == strategies[0].title


def test_bootstrap_strategies_tagged_universal():
    """All strategies tagged with 'universal'."""
    strategies = bootstrap_general_strategies()
    for s in strategies:
        assert 'universal' in s.tags, f"Strategy '{s.title}' missing 'universal' tag"


def test_bootstrap_no_ontology_specific_content():
    """Strategies don't reference PROV/SIO/etc URIs."""
    strategies = bootstrap_general_strategies()
    ontology_prefixes = ['prov:', 'sio:', 'schema:', 'foaf:']

    for s in strategies:
        content_lower = s.content.lower()
        for prefix in ontology_prefixes:
            assert prefix not in content_lower, \
                f"Strategy '{s.title}' contains ontology-specific prefix '{prefix}'"


def test_validate_bootstrap_passes():
    """validate_bootstrap_strategies() returns valid=True."""
    result = validate_bootstrap_strategies()
    assert result['valid'] == True, f"Bootstrap validation failed: {result['checks']}"
    assert result['checks']['count'] == True
    assert result['checks']['unique_titles'] == True
    assert result['checks']['all_valid'] == True
    assert result['checks']['tagged_universal'] == True
    assert result['checks']['no_hardcoded_uris'] == True


def test_bootstrap_strategies_have_unique_titles():
    """All strategies have unique titles (no duplicates)."""
    strategies = bootstrap_general_strategies()
    titles = [s.title for s in strategies]
    assert len(titles) == len(set(titles)), "Duplicate titles found in bootstrap strategies"


def test_bootstrap_strategies_have_content():
    """All strategies have non-empty content."""
    strategies = bootstrap_general_strategies()
    for s in strategies:
        assert len(s.content) > 0, f"Strategy '{s.title}' has empty content"
        assert len(s.description) > 0, f"Strategy '{s.title}' has empty description"
