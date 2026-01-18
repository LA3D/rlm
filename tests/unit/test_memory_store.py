"""Unit tests for MemoryStore class.

Tests CRUD operations, JSON persistence, BM25 corpus generation.
"""

import pytest
from pathlib import Path
import json
import uuid

from rlm.procedural_memory import MemoryItem, MemoryStore


class TestMemoryStoreCreation:
    """Tests for MemoryStore initialization."""

    def test_memory_store_empty_creation(self):
        """MemoryStore can be created empty."""
        store = MemoryStore()

        assert isinstance(store.memories, list)
        assert len(store.memories) == 0
        assert store.path is None

    def test_memory_store_with_path(self, tmp_test_dir):
        """MemoryStore can be created with path."""
        path = tmp_test_dir / "test.json"
        store = MemoryStore(path=path)

        assert store.path == path
        assert len(store.memories) == 0

    def test_memory_store_with_memories(self, memory_item_sample):
        """MemoryStore can be created with initial memories."""
        store = MemoryStore(memories=[memory_item_sample])

        assert len(store.memories) == 1
        assert store.memories[0] == memory_item_sample


class TestMemoryStoreAdd:
    """Tests for adding memories to store."""

    def test_add_memory_item(self, empty_memory_store, memory_item_sample):
        """add() appends memory to store."""
        initial_count = len(empty_memory_store.memories)

        result = empty_memory_store.add(memory_item_sample)

        assert len(empty_memory_store.memories) == initial_count + 1
        assert memory_item_sample in empty_memory_store.memories
        assert isinstance(result, str)
        assert "added" in result.lower()
        assert memory_item_sample.title.lower() in result.lower()

    def test_add_multiple_memories(self, empty_memory_store):
        """Multiple memories can be added."""
        mem1 = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory 1",
            description="First",
            content="Content 1",
            source_type="success",
            task_query="Task 1",
            created_at="2026-01-18T10:00:00Z"
        )

        mem2 = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory 2",
            description="Second",
            content="Content 2",
            source_type="failure",
            task_query="Task 2",
            created_at="2026-01-18T10:01:00Z"
        )

        empty_memory_store.add(mem1)
        empty_memory_store.add(mem2)

        assert len(empty_memory_store.memories) == 2
        assert mem1 in empty_memory_store.memories
        assert mem2 in empty_memory_store.memories

    def test_add_returns_id_in_message(self, empty_memory_store, memory_item_sample):
        """add() return message includes memory ID."""
        result = empty_memory_store.add(memory_item_sample)

        assert memory_item_sample.id in result


class TestMemoryStoreSave:
    """Tests for saving store to JSON."""

    def test_save_to_json(self, tmp_test_dir, memory_store_with_items):
        """save() writes JSON file with correct structure."""
        json_path = tmp_test_dir / "memories.json"
        memory_store_with_items.path = json_path

        result = memory_store_with_items.save()

        # Verify file created
        assert json_path.exists()

        # Verify result message
        assert "saved" in result.lower()
        assert str(len(memory_store_with_items.memories)) in result
        assert str(json_path) in result

        # Verify JSON structure
        with open(json_path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == len(memory_store_with_items.memories)
        assert all('id' in item for item in data)
        assert all('title' in item for item in data)

    def test_save_without_path_returns_message(self, memory_store_with_items):
        """save() without path returns informative message."""
        memory_store_with_items.path = None

        result = memory_store_with_items.save()

        assert "no path" in result.lower()
        assert "not saving" in result.lower()

    def test_save_creates_parent_directory(self, tmp_test_dir, memory_store_with_items):
        """save() creates parent directories if needed."""
        json_path = tmp_test_dir / "subdir" / "nested" / "memories.json"
        memory_store_with_items.path = json_path

        result = memory_store_with_items.save()

        assert json_path.exists()
        assert json_path.parent.exists()

    def test_save_empty_store(self, tmp_test_dir, empty_memory_store):
        """save() works with empty store."""
        json_path = tmp_test_dir / "empty.json"
        empty_memory_store.path = json_path

        result = empty_memory_store.save()

        assert json_path.exists()

        with open(json_path) as f:
            data = json.load(f)

        assert data == []


class TestMemoryStoreLoad:
    """Tests for loading store from JSON."""

    def test_load_from_json(self, tmp_test_dir, memory_store_with_items):
        """load() restores memories from JSON."""
        json_path = tmp_test_dir / "test_load.json"
        memory_store_with_items.path = json_path
        memory_store_with_items.save()

        # Load into new store
        loaded_store = MemoryStore.load(json_path)

        assert len(loaded_store.memories) == len(memory_store_with_items.memories)
        assert loaded_store.path == json_path

        # Verify first memory
        original_mem = memory_store_with_items.memories[0]
        loaded_mem = loaded_store.memories[0]

        assert loaded_mem.id == original_mem.id
        assert loaded_mem.title == original_mem.title
        assert loaded_mem.description == original_mem.description
        assert loaded_mem.session_id == original_mem.session_id

    def test_load_nonexistent_file(self, tmp_test_dir):
        """load() returns empty store for nonexistent file."""
        fake_path = tmp_test_dir / "nonexistent.json"

        loaded_store = MemoryStore.load(fake_path)

        assert len(loaded_store.memories) == 0
        assert loaded_store.path == fake_path

    def test_json_roundtrip_with_session_id(self, tmp_test_dir):
        """Session ID preserved through save/load cycle."""
        session_id = "test_sess_123"
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test",
            description="Test desc",
            content="Test content",
            source_type="success",
            task_query="Test query",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id,
            tags=["test", "roundtrip"]
        )

        json_path = tmp_test_dir / "roundtrip.json"
        store = MemoryStore(path=json_path)
        store.add(mem)
        store.save()

        loaded = MemoryStore.load(json_path)

        assert len(loaded.memories) == 1
        assert loaded.memories[0].session_id == session_id
        assert loaded.memories[0].tags == ["test", "roundtrip"]

    def test_json_roundtrip_preserves_all_fields(self, tmp_test_dir):
        """All MemoryItem fields preserved through save/load."""
        mem = MemoryItem(
            id="test-id-123",
            title="Test Memory",
            description="A test memory",
            content="# Content\n\nSteps to take",
            source_type="failure",
            task_query="Original task",
            created_at="2026-01-18T12:00:00Z",
            access_count=5,
            tags=["tag1", "tag2"],
            session_id="sess_abc"
        )

        json_path = tmp_test_dir / "all_fields.json"
        store = MemoryStore(path=json_path)
        store.add(mem)
        store.save()

        loaded = MemoryStore.load(json_path)
        loaded_mem = loaded.memories[0]

        assert loaded_mem.id == mem.id
        assert loaded_mem.title == mem.title
        assert loaded_mem.description == mem.description
        assert loaded_mem.content == mem.content
        assert loaded_mem.source_type == mem.source_type
        assert loaded_mem.task_query == mem.task_query
        assert loaded_mem.created_at == mem.created_at
        assert loaded_mem.access_count == mem.access_count
        assert loaded_mem.tags == mem.tags
        assert loaded_mem.session_id == mem.session_id


class TestMemoryStoreBM25Corpus:
    """Tests for BM25 corpus generation."""

    def test_corpus_for_bm25(self, memory_store_with_items):
        """get_corpus_for_bm25() builds tokenized corpus."""
        corpus = memory_store_with_items.get_corpus_for_bm25()

        assert isinstance(corpus, list)
        assert len(corpus) == len(memory_store_with_items.memories)

        # Each document is a list of tokens
        for doc in corpus:
            assert isinstance(doc, list)
            assert all(isinstance(token, str) for token in doc)

    def test_corpus_includes_title_description_tags(self):
        """Corpus includes title, description, and tags."""
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="SPARQL Query",
            description="How to query entities",
            content="Content here",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            tags=["sparql", "entity", "search"]
        )

        store = MemoryStore(memories=[mem])
        corpus = store.get_corpus_for_bm25()

        # Should be 1 document
        assert len(corpus) == 1

        # Document should contain words from title, description, tags
        doc_text = " ".join(corpus[0])
        assert "sparql" in doc_text.lower()
        assert "query" in doc_text.lower()
        assert "entities" in doc_text.lower()
        assert "entity" in doc_text.lower()
        assert "search" in doc_text.lower()

    def test_corpus_handles_missing_tags(self):
        """Corpus generation works when tags are None."""
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory without tags",
            description="Description",
            content="Content",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            tags=None
        )

        store = MemoryStore(memories=[mem])
        corpus = store.get_corpus_for_bm25()

        assert len(corpus) == 1
        assert isinstance(corpus[0], list)

    def test_empty_store_corpus(self, empty_memory_store):
        """Empty store produces empty corpus."""
        corpus = empty_memory_store.get_corpus_for_bm25()

        assert corpus == []

    def test_corpus_tokenization(self):
        """Corpus is properly tokenized by spaces."""
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Multi Word Title",
            description="This is a longer description",
            content="Content",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            tags=["tag1", "tag2"]
        )

        store = MemoryStore(memories=[mem])
        corpus = store.get_corpus_for_bm25()

        # Should be split into individual words
        assert "multi" in corpus[0]
        assert "word" in corpus[0]
        assert "title" in corpus[0]
        assert "longer" in corpus[0]
        assert "description" in corpus[0]
        assert "tag1" in corpus[0]
        assert "tag2" in corpus[0]


class TestMemoryStoreEdgeCases:
    """Tests for edge cases and error handling."""

    def test_add_same_memory_twice(self, empty_memory_store, memory_item_sample):
        """Same memory object can be added twice (no deduplication)."""
        empty_memory_store.add(memory_item_sample)
        empty_memory_store.add(memory_item_sample)

        # Should have 2 entries (no automatic deduplication)
        assert len(empty_memory_store.memories) == 2

    def test_save_overwrites_existing_file(self, tmp_test_dir, memory_store_with_items):
        """save() overwrites existing file."""
        json_path = tmp_test_dir / "overwrite.json"

        # First save
        memory_store_with_items.path = json_path
        memory_store_with_items.save()

        original_count = len(memory_store_with_items.memories)

        # Add more memories
        new_mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="New",
            description="New",
            content="New",
            source_type="success",
            task_query="New",
            created_at="2026-01-18T10:00:00Z"
        )
        memory_store_with_items.add(new_mem)

        # Save again
        memory_store_with_items.save()

        # Load and verify new count
        loaded = MemoryStore.load(json_path)
        assert len(loaded.memories) == original_count + 1

    def test_load_invalid_json(self, tmp_test_dir):
        """load() handles invalid JSON gracefully."""
        json_path = tmp_test_dir / "invalid.json"

        # Write invalid JSON
        with open(json_path, 'w') as f:
            f.write("{ invalid json")

        # Should raise an error
        with pytest.raises(json.JSONDecodeError):
            MemoryStore.load(json_path)

    def test_memory_with_unicode_content(self, tmp_test_dir):
        """MemoryStore handles Unicode content correctly."""
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Unicode 测试",
            description="Description with émojis 🎉",
            content="Content with über special ñ characters",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z"
        )

        json_path = tmp_test_dir / "unicode.json"
        store = MemoryStore(path=json_path)
        store.add(mem)
        store.save()

        loaded = MemoryStore.load(json_path)
        loaded_mem = loaded.memories[0]

        assert loaded_mem.title == "Unicode 测试"
        assert "🎉" in loaded_mem.description
        assert "über" in loaded_mem.content
