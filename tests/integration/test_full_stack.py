"""Full Stack Integration Tests (P0 Critical Path).

End-to-end smoke tests validating all components work together.

Risk: Components work in isolation but fail together
Blocks: Release confidence
"""

import pytest
from pathlib import Path
from rdflib import Dataset, Graph, Namespace, URIRef, Literal, RDF
import uuid

from rlm.dataset import (
    DatasetMeta, mem_add, mem_query, work_create, work_to_mem,
    snapshot_dataset, load_snapshot, dataset_stats
)
from rlm.sparql_handles import sparql_local, SPARQLResultHandle
from rlm.procedural_memory import MemoryItem, MemoryStore


class TestFullStackIntegration:
    """P0: End-to-end integration smoke tests."""

    def test_end_to_end_minimal(self, tmp_test_dir):
        """Minimal RLM run with dataset + SPARQL + memory extraction.

        Flow:
        1. Create dataset with session ID
        2. Add data to mem
        3. Query with SPARQL (local)
        4. Store CONSTRUCT result in work graph
        5. Promote work graph to mem
        6. Create memory item with session ID
        7. Save snapshot
        8. Load snapshot and verify state

        Validates: session_id propagation, data flow, persistence
        """
        # Step 1: Create dataset
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='e2e_test')
        original_session = ds_meta.session_id

        # Step 2: Add data to mem
        EX = Namespace("http://example.org/")
        mem_add(ds_meta, EX.Alice, EX.knows, EX.Bob, source="test", reason="Setup test data")
        mem_add(ds_meta, EX.Bob, EX.age, Literal(30), source="test")

        assert len(ds_meta.mem) == 2
        assert len(ds_meta.prov) > 0  # Provenance recorded

        # Step 3: Query with SPARQL
        query = """
        SELECT ?s ?p ?o WHERE {
            ?s ?p ?o
        }
        """
        ns = {}
        result = sparql_local(query, ds_meta.mem, name='query_res', ns=ns)

        assert 'query_res' in ns
        handle = ns['query_res']
        assert isinstance(handle, SPARQLResultHandle)
        assert len(handle.rows) == 2

        # Step 4: Store CONSTRUCT result in work graph
        construct_query = """
        CONSTRUCT { ?s ?p ?o }
        WHERE { ?s ?p ?o }
        """
        # Create work graph and add results
        task_id = f"test_{uuid.uuid4().hex[:8]}"
        graph_uri, work_graph = work_create(ds_meta, task_id)

        # Execute construct locally and add to work graph
        construct_result = ds_meta.mem.query(construct_query)
        for row in construct_result:
            work_graph.add(row)

        assert len(work_graph) == 2

        # Step 5: Promote work graph to mem
        work_to_mem(ds_meta, task_id, reason="Test promotion")

        # Mem should now have original + promoted (but they're duplicates, so still 2)
        # Actually, RDFLib won't add duplicate triples, so still 2
        assert len(ds_meta.mem) == 2

        # Step 6: Create memory item with session ID
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            title="Test workflow",
            description="Added and queried data",
            content="1. mem_add()\n2. Query\n3. Promote",
            source_type="success",
            task_query="Test e2e",
            created_at="2026-01-18T10:00:00Z",
            session_id=original_session
        )

        mem_store = MemoryStore(path=tmp_test_dir / "memories.json")
        mem_store.add(memory)
        mem_store.save()

        # Step 7: Save snapshot
        snapshot_path = tmp_test_dir / "snapshot.trig"
        snapshot_dataset(ds_meta, snapshot_path)

        assert snapshot_path.exists()

        # Step 8: Load snapshot and verify state
        ns = {}
        load_snapshot(str(snapshot_path), ns, name='e2e_test')
        loaded_meta = ns['e2e_test_meta']

        # Verify session ID
        assert loaded_meta.session_id == original_session

        # Verify data
        assert len(loaded_meta.mem) == 2
        assert (EX.Alice, EX.knows, EX.Bob) in loaded_meta.mem

        # Verify provenance
        assert len(loaded_meta.prov) > 0

        # Load memory store and verify
        loaded_mem_store = MemoryStore.load(tmp_test_dir / "memories.json")
        assert len(loaded_mem_store.memories) == 1
        assert loaded_mem_store.memories[0].session_id == original_session

        # SUCCESS: All components work together!

    def test_multi_graph_dataset_state(self, tmp_test_dir):
        """Dataset with mem + prov + work + onto graphs maintains consistency."""
        # Create dataset
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='multi_graph')

        # Add to mem
        EX = Namespace("http://example.org/")
        mem_add(ds_meta, EX.Test, EX.prop, Literal("value"))

        # Create work graph
        task_id = "work1"
        work_uri, work_graph = work_create(ds_meta, task_id)
        work_graph.add((EX.Work, EX.status, Literal("active")))

        # Create onto graph (simulate mounting)
        onto_uri = URIRef(f"urn:rlm:{ds_meta.name}:onto/test")
        onto_graph = ds_meta.dataset.graph(onto_uri)
        onto_graph.add((EX.Ontology, EX.version, Literal("1.0")))

        # Verify all graphs exist
        stats = dataset_stats(ds_meta)

        assert "mem" in str(stats) or "3 graphs" in str(stats)
        assert len(ds_meta.mem) == 1
        assert len(ds_meta.prov) > 0
        assert len(work_graph) == 1
        assert len(onto_graph) == 1

        # Verify work_graphs property
        assert str(work_uri) in ds_meta.work_graphs

        # Mutate mem and verify cache invalidation
        old_version = ds_meta._version
        mem_add(ds_meta, EX.Another, EX.prop, Literal("value2"))
        assert ds_meta._version > old_version

    def test_snapshot_roundtrip_all_graphs(self, tmp_test_dir):
        """Snapshot → reload preserves mem, prov, work, onto with correct counts."""
        # Create complex dataset
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='complex')

        EX = Namespace("http://example.org/")

        # Populate mem
        mem_add(ds_meta, EX.Entity1, EX.prop1, Literal("A"))
        mem_add(ds_meta, EX.Entity2, EX.prop2, Literal("B"))
        mem_add(ds_meta, EX.Entity3, EX.prop3, Literal("C"))

        # Create work graph
        work_uri, work_graph = work_create(ds_meta, "task1")
        work_graph.add((EX.Work1, EX.status, Literal("processing")))
        work_graph.add((EX.Work2, EX.status, Literal("done")))

        # Create onto graph
        onto_uri = URIRef(f"urn:rlm:{ds_meta.name}:onto/test")
        onto_graph = ds_meta.dataset.graph(onto_uri)
        onto_graph.add((EX.Class1, RDF.type, EX.OntologyClass))

        # Record counts
        original_mem_count = len(ds_meta.mem)
        original_prov_count = len(ds_meta.prov)
        original_work_count = len(work_graph)
        original_onto_count = len(onto_graph)

        # Snapshot
        snap_path = tmp_test_dir / "complex_snapshot.trig"
        snapshot_dataset(ds_meta, snap_path)

        # Load
        ns = {}
        load_snapshot(str(snap_path), ns, name='complex')
        loaded_meta = ns['complex_meta']

        # Verify counts
        assert len(loaded_meta.mem) == original_mem_count
        # Prov may have +1 triple for session_id storage
        assert len(loaded_meta.prov) >= original_prov_count
        assert len(loaded_meta.prov) <= original_prov_count + 1

        # Verify work graph
        loaded_work_uri = URIRef(str(work_uri))
        loaded_work_graph = loaded_meta.dataset.graph(loaded_work_uri)
        assert len(loaded_work_graph) == original_work_count

        # Verify onto graph
        loaded_onto_graph = loaded_meta.dataset.graph(onto_uri)
        assert len(loaded_onto_graph) == original_onto_count

        # Verify specific triples
        assert (EX.Entity1, EX.prop1, Literal("A")) in loaded_meta.mem
        assert (EX.Work1, EX.status, Literal("processing")) in loaded_work_graph
        assert (EX.Class1, RDF.type, EX.OntologyClass) in loaded_onto_graph


class TestCrossComponentDataFlow:
    """Tests for data flowing correctly between components."""

    def test_dataset_to_memory_flow(self, tmp_test_dir):
        """Data + session flows: Dataset → Memory → JSON → Reload."""
        # Create dataset
        ds = Dataset()
        ds_meta = DatasetMeta(dataset=ds, name='flow_test')
        session_id = ds_meta.session_id

        # Add data
        EX = Namespace("http://example.org/")
        mem_add(ds_meta, EX.Test, EX.prop, Literal("value"))

        # Create memory linked to session
        mem = MemoryItem(
            id=str(uuid.uuid4()),
            title="Flow test",
            description="Testing data flow",
            content="Steps",
            source_type="success",
            task_query="Test",
            created_at="2026-01-18T10:00:00Z",
            session_id=session_id
        )

        # Save both
        snap_path = tmp_test_dir / "dataset.trig"
        mem_path = tmp_test_dir / "memories.json"

        snapshot_dataset(ds_meta, snap_path)

        store = MemoryStore(path=mem_path)
        store.add(mem)
        store.save()

        # Load both
        ns = {}
        load_snapshot(str(snap_path), ns, name='flow_test')
        loaded_meta = ns['flow_test_meta']
        loaded_store = MemoryStore.load(mem_path)

        # Verify linkage
        assert loaded_meta.session_id == session_id
        assert loaded_store.memories[0].session_id == session_id
        assert loaded_meta.session_id == loaded_store.memories[0].session_id

    def test_sparql_to_dataset_flow(self, dataset_meta):
        """SPARQL results → work graph → mem promotion."""
        EX = Namespace("http://example.org/")

        # Source data
        source_graph = Graph()
        source_graph.add((EX.Source1, EX.value, Literal("A")))
        source_graph.add((EX.Source2, EX.value, Literal("B")))

        # Execute SPARQL CONSTRUCT
        query = """
        CONSTRUCT { ?s ?p ?o }
        WHERE { ?s ?p ?o }
        """

        # Create work graph for results
        task_id = "sparql_test"
        work_uri, work_graph = work_create(dataset_meta, task_id)

        # Simulate CONSTRUCT result
        result = source_graph.query(query)
        for row in result:
            work_graph.add(row)

        assert len(work_graph) == 2

        # Promote to mem
        work_to_mem(dataset_meta, task_id, reason="Promotion test")

        # Verify in mem
        assert (EX.Source1, EX.value, Literal("A")) in dataset_meta.mem
        assert (EX.Source2, EX.value, Literal("B")) in dataset_meta.mem

        # Verify provenance
        assert len(dataset_meta.prov) > 0


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_load_nonexistent_snapshot(self, tmp_test_dir):
        """Loading nonexistent snapshot raises appropriate error."""
        fake_path = tmp_test_dir / "nonexistent.trig"

        with pytest.raises((FileNotFoundError, Exception)):
            ns = {}
            load_snapshot(str(fake_path), ns, name='test')

    def test_empty_dataset_operations(self, empty_dataset):
        """Operations on empty dataset don't crash."""
        ds_meta = DatasetMeta(dataset=empty_dataset, name='empty')

        # Query empty mem
        results = mem_query(ds_meta, "SELECT ?s ?p ?o WHERE { ?s ?p ?o }")
        assert results == []

        # Stats on empty
        stats = dataset_stats(ds_meta)
        assert "0 triples" in stats or "empty" in stats.lower()

    def test_invalid_work_graph_cleanup(self, dataset_meta):
        """Cleaning up nonexistent work graph handles gracefully."""
        from rlm.dataset import work_cleanup

        # Try to cleanup non-existent task
        result = work_cleanup(dataset_meta, "nonexistent_task")

        # Should not crash, should return informative message
        assert isinstance(result, str)
        # work_cleanup returns "Removed 0 work graph(s)" when not found
        assert "removed" in result.lower()
