"""Unit tests for structured sense data."""

import pytest


def test_sense_card_schema_validation():
    """Sense card matches expected schema."""
    # Mock minimal sense
    sense = {
        'sense_card': {
            'ontology_id': 'test',
            'domain_scope': 'Test domain',
            'triple_count': 100,
            'class_count': 10,
            'property_count': 5,
            'key_classes': [],
            'key_properties': [],
            'label_predicates': ['rdfs:label'],
            'description_predicates': ['rdfs:comment'],
            'available_indexes': {},
            'quick_hints': [],
            'uri_pattern': 'http://test.org/'
        }
    }

    # Validate required fields exist
    card = sense['sense_card']
    assert 'ontology_id' in card
    assert 'domain_scope' in card
    assert 'key_classes' in card
    assert 'key_properties' in card
    assert 'label_predicates' in card
    assert isinstance(card['triple_count'], int)
    assert isinstance(card['class_count'], int)


def test_sense_card_size_bounded():
    """Sense card formatting stays under reasonable size."""
    from rlm.ontology import build_sense_structured, format_sense_card

    # Build sense from real PROV ontology
    sense = build_sense_structured('ontology/prov.ttl', name='prov_sense')

    # Format sense card
    card_text = format_sense_card(sense['sense_card'])

    # Should be under 800 chars (target is ~600, allow some buffer)
    assert len(card_text) <= 800, \
        f"Sense card too large: {len(card_text)} chars (max 800)"

    # Should be reasonable size (not too small either)
    assert len(card_text) >= 400, \
        f"Sense card too small: {len(card_text)} chars (min 400)"
