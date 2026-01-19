"""Quick end-to-end test to verify core notebooks work with real API calls.

This test exercises main functionality from each notebook with protocol assertions.
Provides a fast sanity check that the entire pipeline works.
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone
import uuid

from rlm.core import rlm_run, llm_query
from rlm.ontology import setup_ontology_context
from rlm.dataset import setup_dataset_context
from rlm.sparql_handles import SPARQLResultHandle
from rlm.procedural_memory import MemoryStore, MemoryItem, retrieve_memories
from rlm.shacl_examples import detect_shacl, build_shacl_index
from rlm._rlmpaper_compat import RLMIteration, CodeBlock, REPLResult
from rlm.procedural_memory import extract_trajectory_artifact

from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
    assert_bounded_views,
)

from rdflib import Graph


@pytest.mark.live
class TestQuickE2E:
    """Quick end-to-end tests for core functionality."""

    def test_core_llm_query(self):
        """Test llm_query from 00_core.ipynb."""
        ns = {}
        result = llm_query("What is 2+2?", ns, name='math_test')

        assert 'math_test' in ns
        assert '4' in result
        assert ns['math_test'] == result

    def test_ontology_loading(self):
        """Test ontology loading from 01_ontology.ipynb."""
        ns = {}
        result = setup_ontology_context('ontology/prov.ttl', ns, name='prov')

        assert 'prov' in ns
        assert 'prov_meta' in ns
        assert 'search_by_label' in ns
        assert len(ns['prov_meta'].classes) > 0

    def test_dataset_memory(self):
        """Test dataset memory from 02_dataset_memory.ipynb."""
        ns = {}
        result = setup_dataset_context(ns)

        assert 'ds' in ns
        assert 'ds_meta' in ns
        assert 'mem_add' in ns
        assert callable(ns['mem_add'])
        assert callable(ns['dataset_stats'])

    def test_sparql_handles(self):
        """Test SPARQL handles from 03_sparql_handles.ipynb."""
        handle = SPARQLResultHandle(
            rows=[{'x': 1}, {'x': 2}],
            result_type='select',
            query='SELECT ?x WHERE { }',
            endpoint='local',
            columns=['x'],
            total_rows=2
        )

        assert handle.summary() == "SELECT: 2 rows, columns=['x']"
        assert len(handle) == 2
        assert handle.rows[0]['x'] == 1

    def test_procedural_memory(self):
        """Test procedural memory from 05_procedural_memory.ipynb."""
        store = MemoryStore()
        item = MemoryItem(
            id=str(uuid.uuid4()),
            title='Test memory',
            description='A test memory item',
            content='- Step 1\n- Step 2',
            source_type='success',
            task_query='test',
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=['test']
        )
        store.add(item)
        retrieved = retrieve_memories(store, 'test query', k=1)

        assert len(retrieved) == 1
        assert retrieved[0].title == 'Test memory'

    def test_shacl_indexing(self):
        """Test SHACL indexing from 06_shacl_examples.ipynb."""
        dcat_path = Path('ontology/dcat-ap/dcat-ap-SHACL.ttl')

        if not dcat_path.exists():
            pytest.skip("DCAT-AP shapes not available")

        g = Graph()
        g.parse(dcat_path)

        detection = detect_shacl(g)
        assert detection['node_shapes'] > 0

        index = build_shacl_index(g)
        assert len(index.shapes) > 0

    def test_rlm_ontology_integration(self):
        """Test RLM + ontology integration with protocol assertions."""
        ns = {}
        setup_ontology_context('ontology/prov.ttl', ns, name='prov')

        query = "What is prov:Activity?"
        context = ns['prov_meta'].summary()

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=3,
            verbose=False
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Basic checks
        assert len(iterations) > 0
        assert len(answer) > 0

    def test_memory_closed_loop_components(self):
        """Test memory closed loop components work."""
        # Create mock trajectory
        block = CodeBlock(
            code="result = 'prov:Activity is a class'",
            result=REPLResult(stdout="Success", stderr=None, locals={})
        )
        iteration = RLMIteration(
            prompt="test",
            response="test",
            code_blocks=[block],
            final_answer="prov:Activity is a class",
            iteration_time=0.1
        )

        artifact = extract_trajectory_artifact(
            task="What is prov:Activity?",
            answer="prov:Activity is a class",
            iterations=[iteration],
            ns={'result': 'success'}
        )

        assert artifact['converged']
        assert len(artifact['key_steps']) > 0
        assert 'task' in artifact
        assert 'answer' in artifact
