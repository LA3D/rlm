"""Shared test fixtures for RLM test suite."""

import pytest
from pathlib import Path
from rdflib import Dataset, Graph, Namespace, URIRef, Literal
from tempfile import TemporaryDirectory
import uuid

# Import RLM components
from rlm.dataset import DatasetMeta
from rlm.procedural_memory import MemoryItem, MemoryStore
from rlm.sparql_handles import SPARQLResultHandle


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def tmp_test_dir():
    """Create a temporary directory for test artifacts."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Dataset Fixtures
# ============================================================================

@pytest.fixture
def empty_dataset():
    """Create an empty RDF Dataset."""
    return Dataset()


@pytest.fixture
def dataset_meta(empty_dataset):
    """Create a DatasetMeta with empty dataset."""
    return DatasetMeta(dataset=empty_dataset, name='test_ds')


@pytest.fixture
def dataset_with_data(empty_dataset):
    """Create a dataset with some test data in mem graph."""
    ds_meta = DatasetMeta(dataset=empty_dataset, name='test_ds')

    # Add some test triples
    EX = Namespace("http://example.org/")
    ds_meta.mem.add((EX.Alice, EX.knows, EX.Bob))
    ds_meta.mem.add((EX.Bob, EX.age, Literal(30)))
    ds_meta.mem.add((EX.Alice, EX.age, Literal(25)))

    return ds_meta


# ============================================================================
# SPARQL Result Handle Fixtures
# ============================================================================

@pytest.fixture
def select_result_handle():
    """Create a SELECT result handle with sample data."""
    rows = [
        {'name': 'Alice', 'age': 25},
        {'name': 'Bob', 'age': 30},
        {'name': 'Charlie', 'age': 35}
    ]
    return SPARQLResultHandle(
        rows=rows,
        result_type='select',
        query='SELECT ?name ?age WHERE { ?s ?p ?o }',
        endpoint='local',
        columns=['name', 'age'],
        total_rows=3
    )


@pytest.fixture
def ask_result_handle():
    """Create an ASK result handle."""
    return SPARQLResultHandle(
        rows=True,
        result_type='ask',
        query='ASK { ?s ?p ?o }',
        endpoint='local'
    )


@pytest.fixture
def construct_result_handle():
    """Create a CONSTRUCT result handle with a small graph."""
    g = Graph()
    EX = Namespace("http://example.org/")
    g.add((EX.Alice, EX.knows, EX.Bob))
    g.add((EX.Bob, EX.knows, EX.Charlie))

    return SPARQLResultHandle(
        rows=g,
        result_type='construct',
        query='CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }',
        endpoint='local',
        triple_count=2
    )


# ============================================================================
# Memory Store Fixtures
# ============================================================================

@pytest.fixture
def empty_memory_store():
    """Create an empty memory store."""
    return MemoryStore()


@pytest.fixture
def memory_store_with_items():
    """Create a memory store with sample memories."""
    store = MemoryStore()

    # Add a success memory
    success_item = MemoryItem(
        id=str(uuid.uuid4()),
        title="SPARQL pattern: search then describe",
        description="For entity queries, first search by name then describe the URI",
        content="1. Use search_entity() to find URIs\n2. Use describe_entity() on the URI\n3. Parse results",
        source_type="success",
        task_query="What is InstantaneousEvent?",
        created_at="2026-01-18T10:00:00Z",
        tags=["sparql", "entity", "search"],
        session_id="abc12345"
    )
    store.add(success_item)

    # Add a failure memory
    failure_item = MemoryItem(
        id=str(uuid.uuid4()),
        title="Avoid: direct URI without search",
        description="Don't assume URI structure, always search first",
        content="## What went wrong\nAssumed prov:Activity existed without checking\n\n## Solution\nAlways use search_entity() first",
        source_type="failure",
        task_query="Describe prov:Activity",
        created_at="2026-01-18T11:00:00Z",
        tags=["sparql", "error-recovery"],
        session_id="def67890"
    )
    store.add(failure_item)

    return store


@pytest.fixture
def memory_item_sample():
    """Create a single MemoryItem for testing."""
    return MemoryItem(
        id=str(uuid.uuid4()),
        title="Test memory",
        description="A sample memory for testing",
        content="Test content",
        source_type="success",
        task_query="Test query",
        created_at="2026-01-18T12:00:00Z",
        tags=["test"],
        session_id="test1234"
    )


# ============================================================================
# PROV Ontology Fixture
# ============================================================================

@pytest.fixture
def prov_ontology_path():
    """Return path to PROV ontology file."""
    # Assuming ontology files are in ontology/ directory
    ontology_dir = Path(__file__).parent.parent / "ontology"
    prov_file = ontology_dir / "prov.ttl"

    if prov_file.exists():
        return prov_file
    else:
        # Return None if not found - tests can skip if needed
        return None


# ============================================================================
# Namespace Fixtures
# ============================================================================

@pytest.fixture
def test_namespace():
    """Create a test namespace dict for REPL simulation."""
    return {}


# ============================================================================
# Session ID Fixtures
# ============================================================================

@pytest.fixture
def valid_session_id():
    """Generate a valid 8-character session ID."""
    return str(uuid.uuid4())[:8]
