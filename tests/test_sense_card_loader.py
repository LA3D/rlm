"""Test rich sense card loader."""

import pytest
from pathlib import Path
from rlm_runtime.context import load_rich_sense_card


def test_load_agent_guide_dul():
    """Test loading AGENT_GUIDE.md for DUL ontology."""
    guide = load_rich_sense_card(
        Path("ontology/dul/DUL.owl"),
        "dul",
        fallback_to_generated=False
    )

    # Check that it's the rich guide (not minimal sense card)
    assert len(guide) > 5000  # AGENT_GUIDE is ~600 lines, >10K chars
    assert "# DUL Ontology Agent Guide" in guide
    assert "## Core Classes" in guide
    assert "## Key Properties" in guide
    assert "## Query Patterns" in guide


def test_load_agent_guide_prov():
    """Test loading AGENT_GUIDE.md for PROV ontology."""
    guide = load_rich_sense_card(
        Path("ontology/prov/prov.ttl"),
        "prov",
        fallback_to_generated=False
    )

    assert len(guide) > 1000
    assert "PROV" in guide or "prov" in guide


def test_fallback_to_generated():
    """Test fallback to generated sense card when AGENT_GUIDE missing."""
    # Use a test ontology that doesn't have AGENT_GUIDE.md
    # This should fallback to generated sense card
    guide = load_rich_sense_card(
        Path("ontology/prov.ttl"),  # Top-level file, no AGENT_GUIDE sibling
        "prov",
        fallback_to_generated=True
    )

    # Should get something (either AGENT_GUIDE or generated)
    assert len(guide) > 100
    assert "prov" in guide.lower() or "PROV" in guide


def test_require_agent_guide_error():
    """Test that requiring AGENT_GUIDE raises error when missing."""
    # Create a path that definitely won't have AGENT_GUIDE.md
    fake_path = Path("ontology/nonexistent/fake.ttl")

    with pytest.raises(FileNotFoundError) as exc_info:
        load_rich_sense_card(
            fake_path,
            "fake",
            fallback_to_generated=False
        )

    assert "No AGENT_GUIDE.md found" in str(exc_info.value)
    assert "fake" in str(exc_info.value)


def test_agent_guide_content_quality_dul():
    """Test that loaded AGENT_GUIDE has expected sections."""
    guide = load_rich_sense_card(
        Path("ontology/dul/DUL.owl"),
        "dul",
        fallback_to_generated=False
    )

    # Check for key sections
    expected_sections = [
        "## Overview",
        "## Core Classes",
        "## Key Properties",
        "## Query Patterns",
        "## Important Considerations",
        "## Quick Reference",
    ]

    for section in expected_sections:
        assert section in guide, f"Missing section: {section}"
