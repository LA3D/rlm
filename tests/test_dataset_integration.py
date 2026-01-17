"""Integration tests for dataset memory with RLM."""

from rlm.dataset import setup_dataset_context, mem_add, mem_query, mem_describe
from rlm.ontology import setup_ontology_context


def test_dataset_integration_basic():
    """Test basic dataset integration."""
    ns = {}
    setup_dataset_context(ns)

    # Verify namespace setup
    assert 'ds' in ns
    assert 'ds_meta' in ns
    assert 'mem_add' in ns
    assert 'mem_query' in ns
    assert callable(ns['mem_add'])

    # Test adding data
    ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30')

    # Test querying
    results = ns['mem_query']('SELECT ?s ?age WHERE { ?s <http://ex.org/age> ?age }')
    assert len(results) == 1
    assert results[0]['age'] == '30'


def test_dataset_with_ontology():
    """Test dataset integration with ontology context."""
    import tempfile
    import os

    # Create a simple test ontology
    test_ont = """
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix ex: <http://example.org/> .

    ex:Person a owl:Class ;
        rdfs:label "Person" .

    ex:name a owl:DatatypeProperty ;
        rdfs:domain ex:Person ;
        rdfs:range rdfs:Literal .
    """

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False) as f:
        f.write(test_ont)
        ont_path = f.name

    try:
        # Setup both dataset and ontology
        ns = {}
        setup_dataset_context(ns)
        setup_ontology_context(ont_path, ns, name='test_ont')

        # Verify both are in namespace
        assert 'ds' in ns
        assert 'test_ont' in ns
        assert 'test_ont_meta' in ns

        # Can use ontology to guide memory operations
        # Find Person class from ontology
        classes = ns['test_ont_meta'].classes
        assert any('Person' in c for c in classes)

        # Add instance to memory based on ontology
        ns['mem_add']('http://example.org/alice',
                      'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
                      'http://example.org/Person')
        ns['mem_add']('http://example.org/alice',
                      'http://example.org/name',
                      'Alice')

        # Query memory
        results = ns['mem_query']('SELECT ?s ?name WHERE { ?s <http://example.org/name> ?name }')
        assert len(results) == 1
        assert results[0]['name'] == 'Alice'

    finally:
        os.unlink(ont_path)


def test_dataset_provenance():
    """Test that provenance is properly tracked."""
    ns = {}
    setup_dataset_context(ns)

    # Add with provenance
    ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30',
                  source='test', reason='Initial data')

    # Check provenance was recorded
    ds_meta = ns['ds_meta']
    assert len(ds_meta.prov) > 0

    # Provenance should include event type, timestamp, source, reason
    prov_triples = list(ds_meta.prov.triples((None, None, None)))
    assert any('AddEvent' in str(t) for t in prov_triples)
    assert any('test' in str(t) for t in prov_triples)
    assert any('Initial data' in str(t) for t in prov_triples)


def test_work_graph_workflow():
    """Test work graph creation and promotion workflow."""
    ns = {}
    setup_dataset_context(ns)

    # Create work graph
    uri, graph = ns['work_create']('analysis')
    assert 'work/analysis' in uri

    # Add results to work graph
    from rdflib import URIRef, Literal
    graph.add((URIRef('http://ex.org/result'),
               URIRef('http://ex.org/value'),
               Literal('42')))

    # Promote to mem
    result = ns['work_to_mem']('analysis', reason='Analysis complete')
    assert 'Promoted 1 triples' in result

    # Verify in mem
    ds_meta = ns['ds_meta']
    assert len(ds_meta.mem) == 1

    # Cleanup
    ns['work_cleanup'](task_id='analysis')
    assert len(ds_meta.work_graphs) == 0


if __name__ == '__main__':
    test_dataset_integration_basic()
    test_dataset_with_ontology()
    test_dataset_provenance()
    test_work_graph_workflow()
    print("✓ All integration tests passed")
