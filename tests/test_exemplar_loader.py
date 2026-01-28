"""Tests for exemplar_loader.py"""

import pytest
from pathlib import Path
from datetime import datetime

from rlm_runtime.memory.exemplar_loader import (
    parse_markdown_exemplar,
    exemplar_to_memory_item,
    load_exemplars_from_directory,
)
from rlm_runtime.memory.sqlite_backend import SQLiteMemoryBackend


# Sample exemplar content for testing
SAMPLE_EXEMPLAR = """# Reasoning Chain Exemplar: Level 1 - Basic Entity Query

**Question**: "What is the protein with accession P12345?"

**Complexity**: L1 (single entity retrieval)

---

## Reasoning Chain

### Step 1: Understand the Query

**State Before**:
```
classes_discovered: []
properties_discovered: []
query_patterns: []
```

**Action**: Identify what information is needed
- Type: `analyze_question`
- Target: "protein with accession P12345"

**Result**:
- Query type: Entity retrieval by identifier

**Verification**: This is a basic lookup query

**State After**:
```
classes_discovered: []
properties_discovered: []
query_patterns: ["lookup by accession"]
```

---

## Final Query

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX uniprot: <http://purl.uniprot.org/uniprot/>

SELECT ?label ?mnemonic WHERE {
  uniprot:P12345 a up:Protein ;
                  rdfs:label ?label ;
                  up:mnemonic ?mnemonic .
}
```

---

## Anti-Patterns Avoided

1. **Don't search by label for known accessions**: If you have the accession, construct the URI directly

2. **Don't forget type verification**: Adding `a up:Protein` confirms the URI is actually a protein

---

## Key Learnings

- **URI construction**: UniProt accessions can be directly converted to URIs
- **Type verification**: Always good to verify `a up:Protein` for safety
"""


def test_parse_markdown_exemplar():
    """Test parsing of markdown exemplar."""
    result = parse_markdown_exemplar(SAMPLE_EXEMPLAR)

    assert result['title'] == "Level 1 - Basic Entity Query"
    assert result['question'] == "What is the protein with accession P12345?"
    assert result['level'] == 1
    assert "State Before" in result['reasoning_chain']
    assert "PREFIX up:" in result['query']
    assert "Don't search by label" in result['anti_patterns']
    assert "URI construction" in result['key_learnings']


def test_parse_exemplar_missing_question():
    """Test error handling for missing question."""
    bad_exemplar = "# Reasoning Chain Exemplar: Test\n\n**Complexity**: L1"

    with pytest.raises(ValueError, match="Missing \\*\\*Question\\*\\*"):
        parse_markdown_exemplar(bad_exemplar)


def test_parse_exemplar_missing_complexity():
    """Test error handling for missing complexity."""
    bad_exemplar = '# Reasoning Chain Exemplar: Test\n\n**Question**: "Test?"'

    with pytest.raises(ValueError, match="Missing \\*\\*Complexity\\*\\*"):
        parse_markdown_exemplar(bad_exemplar)


def test_exemplar_to_memory_item():
    """Test conversion of exemplar dict to MemoryItem."""
    exemplar_dict = parse_markdown_exemplar(SAMPLE_EXEMPLAR)
    memory_item = exemplar_to_memory_item(
        exemplar_dict,
        ontology_name='uniprot',
        source_file='test.md'
    )

    # Check basic fields
    assert memory_item.source_type == 'exemplar'
    assert memory_item.task_query == "What is the protein with accession P12345?"
    assert "Level 1 - Basic Entity Query" in memory_item.title

    # Check tags
    assert 'level-1' in memory_item.tags
    assert 'uniprot' in memory_item.tags
    assert 'exemplar' in memory_item.tags

    # Check scope
    assert memory_item.scope['ontology'] == ['uniprot']
    assert memory_item.scope['curriculum_level'] == 1
    assert memory_item.scope['transferable'] is False

    # Check provenance
    assert memory_item.provenance['source'] == 'curriculum'
    assert memory_item.provenance['exemplar_level'] == 1
    assert memory_item.provenance['source_file'] == 'test.md'

    # Check content includes key sections
    assert "## Reasoning Chain" in memory_item.content
    assert "## Final Query" in memory_item.content
    assert "PREFIX up:" in memory_item.content


def test_memory_id_stable():
    """Test that memory IDs are stable for same content."""
    exemplar_dict = parse_markdown_exemplar(SAMPLE_EXEMPLAR)

    item1 = exemplar_to_memory_item(exemplar_dict, 'uniprot')
    item2 = exemplar_to_memory_item(exemplar_dict, 'uniprot')

    assert item1.memory_id == item2.memory_id


def test_load_exemplars_from_directory(tmp_path):
    """Test loading multiple exemplars from directory."""
    # Create test exemplar files
    exemplar_dir = tmp_path / "exemplars"
    exemplar_dir.mkdir()

    # Write L1 exemplar
    (exemplar_dir / "uniprot_l1_basic.md").write_text(SAMPLE_EXEMPLAR)

    # Write L2 exemplar (modified)
    l2_exemplar = SAMPLE_EXEMPLAR.replace("Level 1", "Level 2").replace("L1", "L2")
    (exemplar_dir / "uniprot_l2_crossref.md").write_text(l2_exemplar)

    # Create in-memory backend
    backend = SQLiteMemoryBackend(":memory:")

    # Load exemplars
    loaded_ids = load_exemplars_from_directory(
        exemplar_dir,
        backend,
        ontology_name='uniprot'
    )

    assert len(loaded_ids) == 2

    # Verify they're in the backend
    memories = backend.get_all_memories()
    assert len(memories) == 2

    # Check levels
    levels = [m.scope['curriculum_level'] for m in memories]
    assert 1 in levels
    assert 2 in levels


def test_load_exemplars_duplicate_handling(tmp_path):
    """Test that duplicate exemplars are skipped."""
    exemplar_dir = tmp_path / "exemplars"
    exemplar_dir.mkdir()

    (exemplar_dir / "test.md").write_text(SAMPLE_EXEMPLAR)

    backend = SQLiteMemoryBackend(":memory:")

    # Load once
    loaded_ids_1 = load_exemplars_from_directory(exemplar_dir, backend, 'uniprot')
    assert len(loaded_ids_1) == 1

    # Load again - should skip duplicate
    loaded_ids_2 = load_exemplars_from_directory(exemplar_dir, backend, 'uniprot')
    assert len(loaded_ids_2) == 0  # No new exemplars loaded

    # Total should still be 1
    memories = backend.get_all_memories()
    assert len(memories) == 1


def test_load_exemplars_nonexistent_directory():
    """Test error handling for nonexistent directory."""
    backend = SQLiteMemoryBackend(":memory:")

    with pytest.raises(FileNotFoundError):
        load_exemplars_from_directory(
            Path("/nonexistent/path"),
            backend,
            'uniprot'
        )


def test_load_exemplars_empty_directory(tmp_path):
    """Test error handling for directory with no exemplars."""
    exemplar_dir = tmp_path / "empty"
    exemplar_dir.mkdir()

    backend = SQLiteMemoryBackend(":memory:")

    with pytest.raises(ValueError, match="No exemplar files found"):
        load_exemplars_from_directory(exemplar_dir, backend, 'uniprot')


# Integration test with real exemplars (if available)
def test_load_real_exemplars_if_available():
    """Test loading real exemplars if they exist."""
    exemplar_dir = Path("experiments/reasoning_chain_validation/exemplars")

    if not exemplar_dir.exists():
        pytest.skip("Real exemplar directory not found")

    backend = SQLiteMemoryBackend(":memory:")

    loaded_ids = load_exemplars_from_directory(
        exemplar_dir,
        backend,
        ontology_name='uniprot'
    )

    assert len(loaded_ids) > 0

    # Verify structure
    for memory_id in loaded_ids:
        memory = backend.get_memory(memory_id)
        assert memory is not None
        assert memory.source_type == 'exemplar'
        assert 'level-' in ' '.join(memory.tags)
        assert 'curriculum_level' in memory.scope
