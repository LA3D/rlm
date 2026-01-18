"""Unit tests for Session ID tracking in DatasetMeta and MemoryItem.

Tests session ID generation, format validation, and persistence.
"""

import pytest
from rdflib import Dataset
import uuid

from rlm.dataset import DatasetMeta, snapshot_dataset, load_snapshot
from rlm.procedural_memory import MemoryItem


class TestSessionIDGeneration:
    """Tests for session ID generation in DatasetMeta."""

    def test_dataset_meta_generates_session_id(self):
        """DatasetMeta automatically generates a session ID."""
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')

        assert ds_meta.session_id is not None
        assert isinstance(ds_meta.session_id, str)
        assert len(ds_meta.session_id) > 0

    def test_session_id_8_char_uuid_format(self):
        """Session ID is exactly 8 characters from UUID."""
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')

        # Should be 8 chars
        assert len(ds_meta.session_id) == 8

        # Should be valid hex (from UUID)
        try:
            int(ds_meta.session_id, 16)
            valid_hex = True
        except ValueError:
            valid_hex = False

        assert valid_hex

    def test_session_id_uniqueness(self):
        """Each DatasetMeta gets a unique session ID."""
        sessions = []
        for i in range(10):
            ds = Dataset()
            ds_meta = DatasetMeta(dataset=ds, name=f'test{i}')
            sessions.append(ds_meta.session_id)

        # All should be unique
        assert len(sessions) == len(set(sessions))

    def test_session_id_can_be_set_explicitly(self):
        """Session ID can be provided during creation."""
        custom_id = "abc12345"
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test', session_id=custom_id)

        assert ds_meta.session_id == custom_id


class TestSessionIDPersistence:
    """Tests for session ID persistence through snapshots."""

    def test_session_id_persistence_through_snapshot(self, tmp_test_dir):
        """Session ID persists through snapshot/load cycle."""
        from rdflib import Namespace, Literal

        # Create dataset with data
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')
        original_session = ds_meta.session_id

        # Add some data
        EX = Namespace("http://example.org/")
        ds_meta.mem.add((EX.Test, EX.prop, Literal("value")))

        # Save snapshot
        snap_path = tmp_test_dir / "session_test.trig"
        snapshot_dataset(ds_meta, snap_path)

        # Load into new dataset
        ns = {}
        load_snapshot(str(snap_path), ns, name='test')
        loaded_meta = ns['test_meta']

        # Session ID should match
        assert loaded_meta.session_id == original_session

    def test_session_id_in_dataset_summary(self):
        """Session ID appears in dataset summary."""
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')

        summary = ds_meta.summary()

        assert ds_meta.session_id in summary
        assert "session" in summary.lower()

    def test_multiple_snapshots_preserve_session(self, tmp_test_dir):
        """Multiple snapshot/load cycles preserve same session ID."""
        from rdflib import Namespace, Literal

        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')
        original_session = ds_meta.session_id

        EX = Namespace("http://example.org/")
        snap_path = tmp_test_dir / "multi_snap.trig"

        # Cycle 1
        ds_meta.mem.add((EX.Step1, EX.value, Literal(1)))
        snapshot_dataset(ds_meta, snap_path)

        ns1 = {}
        load_snapshot(str(snap_path), ns1, name='test')
        meta1 = ns1['test_meta']
        assert meta1.session_id == original_session

        # Cycle 2
        meta1.mem.add((EX.Step2, EX.value, Literal(2)))
        snapshot_dataset(meta1, snap_path)

        ns2 = {}
        load_snapshot(str(snap_path), ns2, name='test')
        meta2 = ns2['test_meta']
        assert meta2.session_id == original_session


class TestMemoryItemSessionID:
    """Tests for session_id field in MemoryItem."""

    def test_memory_item_captures_session_id(self):
        """MemoryItem can be created with session_id."""
        session_id = "test1234"

        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test",
            description="Test",
            content="Test",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id
        )

        assert mem.session_id == session_id

    def test_memory_item_optional_session_id(self):
        """MemoryItem works without session_id (backward compat)."""
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test",
            description="Test",
            content="Test",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z"
        )

        assert mem.session_id is None

    def test_memory_item_to_dict_includes_session_id(self):
        """to_dict() includes session_id field."""
        session_id = "xyz98765"

        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test",
            description="Test",
            content="Test",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id
        )

        data = mem.to_dict()

        assert 'session_id' in data
        assert data['session_id'] == session_id

    def test_memory_item_from_dict_with_session_id(self):
        """from_dict() reconstructs session_id."""
        data = {
            'id': str(uuid.uuid4()),
            'title': "Test",
            'description': "Test",
            'content': "Test",
            'source_type': "success",
            'task_query': "Test",
            'created_at': "2026-01-18T10:00:00Z",
            'access_count': 0,
            'tags': ['test'],
            'session_id': "sess1234"
        }

        mem = MemoryItem.from_dict(data)

        assert mem.session_id == "sess1234"

    def test_memory_item_from_dict_without_session_id(self):
        """from_dict() works with old data without session_id."""
        data = {
            'id': str(uuid.uuid4()),
            'title': "Test",
            'description': "Test",
            'content': "Test",
            'source_type': "success",
            'task_query': "Test",
            'created_at': "2026-01-18T10:00:00Z",
            'access_count': 0,
            'tags': ['test']
            # No session_id
        }

        # Should not raise error, session_id defaults to None
        try:
            mem = MemoryItem.from_dict(data)
            assert mem.session_id is None
            success = True
        except TypeError:
            success = False

        assert success


class TestSessionIDLinkage:
    """Tests for linking session IDs between Dataset and Memory."""

    def test_session_id_captured_from_dataset(self):
        """Memory can capture session_id from DatasetMeta."""
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')

        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test",
            description="Test",
            content="Test",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            session_id=ds_meta.session_id
        )

        assert mem.session_id == ds_meta.session_id

    def test_multiple_memories_same_session(self):
        """Multiple memories can share same session ID."""
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='test')
        session_id = ds_meta.session_id

        mem1 = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory 1",
            description="First",
            content="Content 1",
            source_type="success",
            task_query="Task 1",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id
        )

        mem2 = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory 2",
            description="Second",
            content="Content 2",
            source_type="success",
            task_query="Task 2",
            created_at="2026-01-18T10:01:00Z",
            session_id=session_id
        )

        assert mem1.session_id == mem2.session_id == session_id

    def test_memories_from_different_sessions(self):
        """Memories from different sessions have different IDs."""
        ds1 = Dataset()
        ds_meta1 = DatasetMeta(dataset=ds1, name='test1')

        ds2 = Dataset()
        ds_meta2 = DatasetMeta(dataset=ds2, name='test2')

        mem1 = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory 1",
            description="From session 1",
            content="Content 1",
            source_type="success",
            task_query="Task 1",
            created_at="2026-01-18T10:00:00Z",
            session_id=ds_meta1.session_id
        )

        mem2 = MemoryItem(
            id=str(uuid.uuid4()),
            title="Memory 2",
            description="From session 2",
            content="Content 2",
            source_type="success",
            task_query="Task 2",
            created_at="2026-01-18T10:01:00Z",
            session_id=ds_meta2.session_id
        )

        assert mem1.session_id != mem2.session_id
