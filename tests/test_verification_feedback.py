"""Tests for verification_feedback.py"""

import pytest
from pathlib import Path

from rlm_runtime.tools.verification_feedback import (
    parse_agent_guide,
    verify_sparql_query,
    detect_anti_patterns,
    generate_suggestions,
    format_verification_feedback,
    load_agent_guide_for_ontology,
    AgentGuideMetadata,
    PropertyMetadata,
)


# Sample agent guide content
SAMPLE_GUIDE = """# Test Ontology Agent Guide

## Overview
Test ontology for verification.

## Core Classes
- **test:Entity** - Main entity class

## Key Properties

### Protein Properties
- **up:organism** - Links to taxon
- **up:reviewed** - Boolean for Swiss-Prot (true) vs TrEMBL (false)

### 1. **prov:wasGeneratedBy**
- **Domain**: Entity → **Range**: Activity
- **Usage**: Shows which Activity created an Entity
- **When to use**: When you want to trace back from an Entity to its creating Activity

## Anti-Patterns Avoided

1. **Don't search by label for known accessions**: If you have the accession, construct the URI directly

2. **Don't use rdfs:subClassOf+ on materialized hierarchies**: Use rdfs:subClassOf directly

## Important Considerations

1. Always filter by `up:reviewed true` when possible for curated data
2. Use LIMIT during development
3. Avoid unbounded property paths
"""


def test_parse_agent_guide(tmp_path):
    """Test parsing of AGENT_GUIDE.md."""
    guide_path = tmp_path / "test" / "AGENT_GUIDE.md"
    guide_path.parent.mkdir()
    guide_path.write_text(SAMPLE_GUIDE)

    metadata = parse_agent_guide(guide_path)

    assert metadata.ontology_name == "test"
    assert len(metadata.properties) > 0
    assert len(metadata.anti_patterns) > 0
    assert len(metadata.considerations) > 0


def test_parse_properties_section():
    """Test property parsing from guide."""
    guide_path = Path("ontology/uniprot/AGENT_GUIDE.md")

    if not guide_path.exists():
        pytest.skip("UniProt guide not found")

    metadata = parse_agent_guide(guide_path)

    # Should have extracted properties
    assert len(metadata.properties) > 0

    # Check if we found common properties (format may vary)
    property_names = list(metadata.properties.keys())
    assert len(property_names) > 0


def test_parse_anti_patterns():
    """Test anti-pattern extraction from guide."""
    guide_path = Path("ontology/uniprot/AGENT_GUIDE.md")

    if not guide_path.exists():
        pytest.skip("UniProt guide not found")

    metadata = parse_agent_guide(guide_path)

    # UniProt guide should have anti-patterns or considerations
    total_guidance = len(metadata.anti_patterns) + len(metadata.considerations)
    assert total_guidance > 0


def test_detect_anti_patterns_label_filter():
    """Test detection of label filtering anti-pattern."""
    metadata = AgentGuideMetadata(ontology_name="test")
    metadata.anti_patterns = [
        "Don't search by label for known accessions"
    ]

    # Bad query: filters by label
    bad_query = """
    SELECT ?protein WHERE {
        ?protein a up:Protein ;
                 rdfs:label ?label .
        FILTER(CONTAINS(?label, "P12345"))
    }
    """

    matches = detect_anti_patterns(bad_query, metadata)
    assert len(matches) > 0
    assert "label" in matches[0].lower()


def test_detect_anti_patterns_property_path():
    """Test detection of property path on materialized hierarchy."""
    metadata = AgentGuideMetadata(ontology_name="test")
    metadata.anti_patterns = [
        "Don't use rdfs:subClassOf+ on materialized hierarchies"
    ]

    # Bad query: uses property path
    bad_query = """
    SELECT ?child WHERE {
        ?child rdfs:subClassOf+ taxon:9606 .
    }
    """

    matches = detect_anti_patterns(bad_query, metadata)
    assert len(matches) > 0


def test_generate_suggestions_no_limit():
    """Test suggestion to add LIMIT."""
    metadata = AgentGuideMetadata(ontology_name="test")

    query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
    results = []

    suggestions = generate_suggestions(query, results, metadata)

    # Should suggest adding LIMIT
    assert any("LIMIT" in s for s in suggestions)


def test_generate_suggestions_many_results():
    """Test suggestion for queries with many results."""
    metadata = AgentGuideMetadata(ontology_name="test")

    query = "SELECT ?s WHERE { ?s a up:Protein }"
    results = [{}] * 2000  # Simulate 2000 results

    suggestions = generate_suggestions(query, results, metadata)

    # Should suggest narrowing scope
    assert any("narrow" in s.lower() or "filter" in s.lower() for s in suggestions)


def test_generate_suggestions_no_results():
    """Test suggestion for queries with no results."""
    metadata = AgentGuideMetadata(ontology_name="test")

    query = "SELECT ?s WHERE { ?s a up:NonexistentClass }"
    results = []

    suggestions = generate_suggestions(query, results, metadata)

    # Should suggest verification
    assert any("verify" in s.lower() or "no results" in s.lower() for s in suggestions)


def test_format_verification_feedback():
    """Test formatting of verification feedback."""
    verification = {
        'has_issues': True,
        'constraint_violations': ['Domain mismatch for property X'],
        'anti_pattern_matches': ['⚠ Label filtering detected'],
        'suggestions': ['💡 Add LIMIT clause', '💡 Verify URIs'],
    }

    feedback = format_verification_feedback(verification)

    assert "Verification Feedback" in feedback
    assert "Constraint Violations" in feedback
    assert "Anti-Patterns Detected" in feedback
    assert "Suggestions" in feedback
    assert "Domain mismatch" in feedback
    assert "Label filtering" in feedback


def test_format_verification_feedback_empty():
    """Test that no feedback is returned when query is clean."""
    verification = {
        'has_issues': False,
        'constraint_violations': [],
        'anti_pattern_matches': [],
        'suggestions': [],
    }

    feedback = format_verification_feedback(verification)

    assert feedback == ""


def test_verify_sparql_query_integration():
    """Integration test of query verification."""
    metadata = AgentGuideMetadata(ontology_name="test")
    metadata.anti_patterns = [
        "Don't search by label for known accessions"
    ]
    metadata.considerations = [
        "Always filter by `up:reviewed true` when possible"
    ]

    # Query with anti-pattern
    query = """
    SELECT ?protein WHERE {
        ?protein a up:Protein ;
                 rdfs:label ?label .
        FILTER(CONTAINS(?label, "insulin"))
    }
    """

    results = [{}] * 500  # Simulate some results

    verification = verify_sparql_query(query, results, metadata)

    assert verification['has_issues'] is True
    assert len(verification['anti_pattern_matches']) > 0


def test_load_agent_guide_for_ontology_prov():
    """Test loading guide for PROV ontology."""
    prov_path = Path("ontology/prov.ttl")

    if not prov_path.exists():
        pytest.skip("PROV ontology not found")

    metadata = load_agent_guide_for_ontology(prov_path)

    if metadata is None:
        pytest.skip("PROV guide not generated yet")

    assert metadata.ontology_name == "prov"


def test_load_agent_guide_for_ontology_dul():
    """Test loading guide for DUL ontology."""
    dul_path = Path("ontology/dul/DUL.ttl")

    if not dul_path.exists():
        pytest.skip("DUL ontology not found")

    metadata = load_agent_guide_for_ontology(dul_path)

    if metadata is None:
        pytest.skip("DUL guide not generated yet")

    assert metadata.ontology_name == "dul"


def test_load_agent_guide_for_ontology_nonexistent():
    """Test loading guide for nonexistent ontology."""
    fake_path = Path("ontology/nonexistent.ttl")

    metadata = load_agent_guide_for_ontology(fake_path)

    assert metadata is None  # Should return None, not error


# Integration tests with real guides (if available)
def test_parse_real_prov_guide():
    """Test parsing real PROV guide."""
    guide_path = Path("ontology/prov/AGENT_GUIDE.md")

    if not guide_path.exists():
        pytest.skip("PROV guide not found")

    metadata = parse_agent_guide(guide_path)

    assert metadata.ontology_name == "prov"
    # PROV guide should have properties and guidance
    assert len(metadata.properties) + len(metadata.anti_patterns) + len(metadata.considerations) > 0


def test_parse_real_uniprot_guide():
    """Test parsing real UniProt guide."""
    guide_path = Path("ontology/uniprot/AGENT_GUIDE.md")

    if not guide_path.exists():
        pytest.skip("UniProt guide not found")

    metadata = parse_agent_guide(guide_path)

    assert metadata.ontology_name == "uniprot"
    # UniProt is comprehensive, should have all types of guidance
    assert len(metadata.properties) > 0
    assert len(metadata.anti_patterns) + len(metadata.considerations) > 0
