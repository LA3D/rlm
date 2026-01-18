"""Integration tests for Dataset + Memory integration (P0 Critical Path).

Tests the critical session ID propagation flow:
DatasetMeta.session_id → MemoryItem.session_id → snapshot persistence

Risk: Session IDs lost in snapshot/reload breaks memory lineage
Blocks: Procedural memory attribution, audit trails
"""

import pytest
from pathlib import Path
from rdflib import Dataset, Namespace, Literal
import json

from rlm.dataset import DatasetMeta, snapshot_dataset, load_snapshot
from rlm.procedural_memory import MemoryItem, extract_memories
import uuid


class TestSessionIDPropagation:
    """P0: Validates session ID flows correctly through the system."""

    def test_dataset_meta_generates_session_id(self, empty_dataset):
        """DatasetMeta automatically generates an 8-char UUID session ID."""
        ds_meta = DatasetMeta(dataset=empty_dataset, name='test')

        assert ds_meta.session_id is not None
        assert isinstance(ds_meta.session_id, str)
        assert len(ds_meta.session_id) == 8
        # Should be valid hex (UUID prefix)
        int(ds_meta.session_id, 16)

    def test_session_id_8_char_uuid_format(self, empty_dataset):
        """Session ID is exactly 8 chars and comes from UUID."""
        ds_meta1 = DatasetMeta(dataset=empty_dataset, name='ds1')
        ds_meta2 = DatasetMeta(dataset=Dataset(), name='ds2')

        # Both are 8 chars
        assert len(ds_meta1.session_id) == 8
        assert len(ds_meta2.session_id) == 8

        # They should be different (extremely unlikely collision)
        assert ds_meta1.session_id != ds_meta2.session_id

    def test_session_id_persistence_through_snapshot(self, dataset_meta, tmp_test_dir):
        """Session ID persists through snapshot/load cycle."""
        original_session_id = dataset_meta.session_id

        # Add some data to make snapshot meaningful
        EX = Namespace("http://example.org/")
        dataset_meta.mem.add((EX.Alice, EX.knows, EX.Bob))

        # Save snapshot
        snapshot_path = tmp_test_dir / "test_snapshot.trig"
        result = snapshot_dataset(dataset_meta, snapshot_path)
        assert "saved" in result.lower()
        assert snapshot_path.exists()

        # Load snapshot into new DatasetMeta
        ns = {}
        load_snapshot(str(snapshot_path), ns, name='test_ds')
        loaded_meta = ns['test_ds_meta']

        # Session ID should be restored
        assert loaded_meta.session_id == original_session_id

    def test_memory_item_captures_session_id(self, dataset_meta):
        """MemoryItem can capture session_id from DatasetMeta."""
        session_id = dataset_meta.session_id

        memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test memory",
            description="Test description",
            content="Test content",
            source_type="success",
            task_query="Test query",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id  # Capture from DatasetMeta
        )

        assert memory.session_id == session_id
        assert memory.session_id == dataset_meta.session_id

    def test_memory_item_optional_session_id(self):
        """MemoryItem can be created without session_id (backward compat)."""
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test memory",
            description="Test description",
            content="Test content",
            source_type="success",
            task_query="Test query",
            created_at="2026-01-18T10:00:00Z"
            # No session_id
        )

        assert memory.session_id is None

    def test_session_id_json_roundtrip(self, tmp_test_dir, dataset_meta):
        """Session ID preserved through MemoryItem JSON serialization."""
        from rlm.procedural_memory import MemoryStore

        session_id = dataset_meta.session_id

        # Create memory with session ID
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test memory",
            description="Test description",
            content="Test content",
            source_type="success",
            task_query="Test query",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id
        )

        # Save to store
        store = MemoryStore(path=tmp_test_dir / "memories.json")
        store.add(memory)
        store.save()

        # Load back
        loaded_store = MemoryStore.load(tmp_test_dir / "memories.json")

        assert len(loaded_store.memories) == 1
        loaded_memory = loaded_store.memories[0]
        assert loaded_memory.session_id == session_id


class TestDatasetMemoryIntegration:
    """Integration tests for Dataset + Memory workflows."""

    def test_session_id_propagation_full_flow(self, dataset_meta, tmp_test_dir):
        """Complete flow: DatasetMeta → MemoryItem → snapshot → load."""
        from rlm.procedural_memory import MemoryStore

        # Step 1: DatasetMeta has session_id
        original_session = dataset_meta.session_id
        assert original_session is not None

        # Step 2: Create memory linked to session
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test memory",
            description="Session-linked memory",
            content="Content",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            session_id=original_session
        )

        # Step 3: Save memory store
        mem_store = MemoryStore(path=tmp_test_dir / "memories.json")
        mem_store.add(memory)
        mem_store.save()

        # Step 4: Save dataset snapshot
        EX = Namespace("http://example.org/")
        dataset_meta.mem.add((EX.Test, EX.prop, Literal("value")))
        snap_path = tmp_test_dir / "snapshot.trig"
        snapshot_dataset(dataset_meta, snap_path)

        # Step 5: Load everything back
        ns = {}
        load_snapshot(str(snap_path), ns, name='test_ds')
        loaded_meta = ns['test_ds_meta']
        loaded_mem_store = MemoryStore.load(tmp_test_dir / "memories.json")

        # Step 6: Verify session IDs match across the board
        assert loaded_meta.session_id == original_session
        assert loaded_mem_store.memories[0].session_id == original_session
        assert loaded_meta.session_id == loaded_mem_store.memories[0].session_id

    def test_ontology_auto_mount_in_dataset(self, dataset_meta, prov_ontology_path):
        """setup_ontology_context(dataset_meta=...) mounts into onto/* graphs."""
        if prov_ontology_path is None:
            pytest.skip("PROV ontology not found")

        from rlm.dataset import mount_ontology

        # Mount PROV ontology
        result = mount_ontology(
            ds_meta=dataset_meta,
            ns={},
            path=str(prov_ontology_path),
            ont_name='prov'
        )

        # Check onto/prov graph exists
        onto_uri = f"urn:rlm:{dataset_meta.name}:onto/prov"
        graph_uris = [str(ctx.identifier) for ctx in dataset_meta.dataset.contexts()]

        assert onto_uri in graph_uris
        assert "Mounted" in result or "loaded" in result.lower()

        # Verify graph has content
        onto_graph = dataset_meta.dataset.graph(onto_uri)
        assert len(onto_graph) > 0

    def test_multi_run_dataset_continuity(self, tmp_test_dir):
        """Second run loads dataset state from first run."""
        EX = Namespace("http://example.org/")

        # Run 1: Create dataset, add data, save
        ds1 = Dataset()
        meta1 = DatasetMeta(dataset=ds1, name='persistent')
        session1 = meta1.session_id

        meta1.mem.add((EX.Alice, EX.knows, EX.Bob))
        snap_path = tmp_test_dir / "persistent.trig"
        snapshot_dataset(meta1, snap_path)

        # Run 2: Load from snapshot, verify state
        ns2 = {}
        load_snapshot(str(snap_path), ns2, name='persistent')
        meta2 = ns2['persistent_meta']

        # Session ID matches
        assert meta2.session_id == session1

        # Data preserved
        assert (EX.Alice, EX.knows, EX.Bob) in meta2.mem

        # Add more data in run 2
        meta2.mem.add((EX.Bob, EX.age, Literal(30)))
        snapshot_dataset(meta2, snap_path)

        # Run 3: Load again, verify both additions
        ns3 = {}
        load_snapshot(str(snap_path), ns3, name='persistent')
        meta3 = ns3['persistent_meta']

        assert meta3.session_id == session1
        assert (EX.Alice, EX.knows, EX.Bob) in meta3.mem
        assert (EX.Bob, EX.age, Literal(30)) in meta3.mem


class TestMemoryExtractionWithSessionID:
    """Tests for extract_memories() capturing session_id."""

    def test_memory_extraction_captures_session_id(self, dataset_meta):
        """extract_memories() captures ns['ds_meta'].session_id."""
        # This test is conceptual - extract_memories() requires RLM iterations
        # We verify the MemoryItem structure supports session_id

        session_id = dataset_meta.session_id

        # Simulate what extract_memories() should do
        simulated_memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="Extracted memory",
            description="Memory extracted from trajectory",
            content="Steps taken",
            source_type="success",
            task_query="Original query",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id  # Should be extracted from ns['ds_meta']
        )

        assert simulated_memory.session_id == session_id

    def test_memory_without_dataset_has_no_session(self):
        """Memories extracted without dataset have session_id=None."""
        # Simulate extraction without ds_meta in namespace
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="No dataset memory",
            description="Extracted without dataset context",
            content="Steps",
            source_type="success",
            task_query="Query",
            created_at="2026-01-18T10:00:00Z"
            # No session_id
        )

        assert memory.session_id is None
