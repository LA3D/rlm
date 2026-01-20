"""Unit tests for memory-recipe separation validation."""

import pytest
from rlm.procedural_memory import MemoryStore, bootstrap_general_strategies
from rlm.reasoning_bank import ONTOLOGY_RECIPES, validate_memory_recipe_separation


def test_no_overlap_memory_and_recipes():
    """Bootstrap strategies don't duplicate ONTOLOGY_RECIPES."""
    memory_store = MemoryStore()
    for s in bootstrap_general_strategies():
        memory_store.add(s)

    result = validate_memory_recipe_separation(memory_store)
    assert result['valid'] == True, \
        f"Validation failed: {result['overlap_count']} overlapping titles: {result['overlapping_titles']}"
    assert result['overlap_count'] == 0


def test_ontology_recipes_are_domain_specific():
    """ONTOLOGY_RECIPES (when populated) have ontology field set."""
    if not ONTOLOGY_RECIPES:
        pytest.skip("ONTOLOGY_RECIPES is empty - this is expected for now")

    for recipe in ONTOLOGY_RECIPES:
        assert recipe.ontology is not None, \
            f"Recipe '{recipe.title}' should have ontology field set (domain-specific)"


def test_memory_store_contains_universal_strategies():
    """Bootstrap memory store has strategies tagged as universal."""
    memory_store = MemoryStore()
    for s in bootstrap_general_strategies():
        memory_store.add(s)

    universal_count = sum(1 for m in memory_store.memories if 'universal' in m.tags)
    assert universal_count == 7, \
        f"Expected 7 universal strategies, got {universal_count}"
