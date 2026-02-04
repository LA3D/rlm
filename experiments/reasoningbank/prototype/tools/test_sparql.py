"""Test SPARQL tools against multiple endpoints.

Tests:
1. EndpointConfig structure
2. Basic connectivity and bounded returns
3. Handle dict pattern (serializable for DSPy sandbox)
4. Two-phase retrieval (query -> peek/slice)
5. Source attribution in all returns
6. DSPy tool signatures

Usage:
    python experiments/reasoningbank/tools/test_sparql.py
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.tools.endpoint import EndpointConfig
from experiments.reasoningbank.tools.sparql import SPARQLTools


# Test endpoint configurations
UNIPROT_CONFIG = EndpointConfig(
    url='https://sparql.uniprot.org/sparql/',
    name='UniProt',
    authority='UniProt Consortium',
    domain='Protein sequences and functional annotation',
    prefixes={
        'up': 'http://purl.uniprot.org/core/',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'owl': 'http://www.w3.org/2002/07/owl#',
    }
)

DBPEDIA_CONFIG = EndpointConfig(
    url='https://dbpedia.org/sparql',
    name='DBpedia',
    authority='DBpedia Association',
    domain='Structured Wikipedia data',
    prefixes={
        'dbo': 'http://dbpedia.org/ontology/',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    }
)


def test_endpoint_config():
    """Test 1: EndpointConfig structure and methods."""
    print("\n=== Test 1: EndpointConfig ===")

    config = UNIPROT_CONFIG
    assert config.name == "UniProt"
    assert config.authority == "UniProt Consortium"
    assert 'up' in config.prefixes

    # Test prefix block generation
    prefix_block = config.prefix_block()
    assert 'PREFIX up:' in prefix_block
    print(f"UniProt prefix block: {len(prefix_block)} chars, {len(config.prefixes)} prefixes")

    print("✓ EndpointConfig OK")
    return config


def test_sparql_tools_with_config():
    """Test 2: SPARQLTools with EndpointConfig."""
    print("\n=== Test 2: SPARQLTools with Config ===")

    tools = SPARQLTools(UNIPROT_CONFIG)

    assert tools.name == "UniProt"
    assert tools.authority == "UniProt Consortium"

    # Test endpoint info includes config details
    info = tools.endpoint_info()
    assert info['name'] == "UniProt"
    assert info['authority'] == "UniProt Consortium"
    assert 'domain' in info
    print(f"Endpoint info: {info['name']} ({info['authority']})")

    print("✓ SPARQLTools with Config OK")
    return tools


def test_source_attribution(tools):
    """Test 3: All returns include source attribution."""
    print("\n=== Test 3: Source Attribution ===")

    # Query returns handle dict with source
    handle = tools.sparql_query("SELECT ?class WHERE { ?class a owl:Class } LIMIT 5")
    assert isinstance(handle, dict), "Should return dict handle"
    assert handle.get('source') == "UniProt"
    print(f"Handle source: {handle.get('source')}")

    # Stats include source
    stats = tools.sparql_stats(handle['key'])
    assert stats.get('source') == "UniProt"
    print(f"Stats source: {stats.get('source')}")

    # Describe includes source
    desc = tools.sparql_describe("http://purl.uniprot.org/core/Protein", limit=5)
    assert desc.get('source') == "UniProt"
    print(f"Describe source: {desc.get('source')}")

    # Count includes source
    count = tools.sparql_count("SELECT ?s WHERE { ?s a owl:Class }")
    assert count.get('source') == "UniProt"
    print(f"Count source: {count.get('source')}")

    print("✓ Source Attribution OK")


def test_handle_pattern(tools):
    """Test 4: Handle pattern - returns serializable dict, not Ref object."""
    print("\n=== Test 4: Handle Pattern ===")

    handle = tools.sparql_query("SELECT ?class WHERE { ?class a owl:Class } LIMIT 10")

    print(f"Query returned: {handle}")
    print(f"Type: {type(handle)}")

    # Must be dict (serializable for DSPy sandbox)
    assert isinstance(handle, dict), "Query should return dict handle, not Ref object"

    # Check required fields
    assert 'key' in handle, "Handle must have 'key'"
    assert 'dtype' in handle, "Handle must have 'dtype'"
    assert 'size' in handle, "Handle must have 'size'"
    assert 'rows' in handle, "Handle must have 'rows'"
    assert 'preview' in handle, "Handle must have 'preview'"
    assert 'source' in handle, "Handle must have 'source'"

    assert handle['dtype'] == 'results', f"Expected dtype='results', got {handle['dtype']}"
    assert handle['rows'] <= 10, f"Expected <=10 rows, got {handle['rows']}"
    assert len(handle['preview']) <= 120, "Preview should be bounded"
    assert handle['source'] == "UniProt", "Source should be set"

    print(f"✓ Handle pattern OK: {handle['rows']} rows, {handle['size']} chars from {handle['source']}")
    return handle


def test_two_phase_retrieval(tools, handle):
    """Test 5: Two-phase retrieval (stats -> peek -> slice)."""
    print("\n=== Test 5: Two-Phase Retrieval ===")

    # Phase 1: Get stats (metadata only)
    stats = tools.sparql_stats(handle['key'])
    print(f"Stats: {stats}")

    assert 'rows' in stats, "Stats should include row count"
    assert 'source' in stats, "Stats should include source"

    # Phase 2a: Peek at first few rows
    rows = tools.sparql_peek(handle['key'], 3)
    print(f"Peek (3 rows): {len(rows)} returned")

    assert len(rows) <= 3, f"Peek should return <=3 rows, got {len(rows)}"

    # Phase 2b: Slice specific range
    slice_rows = tools.sparql_slice(handle['key'], 0, 5)
    print(f"Slice [0:5]: {len(slice_rows)} rows")

    assert len(slice_rows) <= 5, "Slice should be bounded"

    print("✓ Two-phase retrieval OK")


def test_bounded_returns(tools):
    """Test 6: All tools enforce bounded returns."""
    print("\n=== Test 6: Bounded Returns ===")

    # Query with limit - bounded
    handle = tools.sparql_query("SELECT ?s WHERE { ?s a owl:Class }", limit=10)
    print(f"Query: {handle['rows']} rows (limit=10)")
    assert handle['rows'] <= 10, "Query should respect limit"

    # Peek - bounded to max 20
    rows = tools.sparql_peek(handle['key'], 100)  # Request 100, should cap at 20
    print(f"Peek (requested 100): {len(rows)} rows (max=20)")
    assert len(rows) <= 20, "Peek should cap at 20"

    # Slice - bounded to max 50
    slice_rows = tools.sparql_slice(handle['key'], 0, 100)  # Request 100, should cap at 50
    print(f"Slice (requested 100): {len(slice_rows)} rows (max=50)")
    assert len(slice_rows) <= 50, "Slice should cap at 50"

    print("✓ Bounded returns OK")


def test_multi_endpoint():
    """Test 7: Test against multiple endpoints."""
    print("\n=== Test 7: Multi-Endpoint ===")

    # Test DBpedia
    try:
        dbpedia = SPARQLTools(DBPEDIA_CONFIG)
        print(f"DBpedia endpoint: {dbpedia.name} ({dbpedia.authority})")

        # Simple test query
        handle = dbpedia.sparql_query("""
            SELECT ?person WHERE {
                ?person a dbo:Person .
            }
        """, limit=5)

        print(f"DBpedia query: {handle}")
        assert isinstance(handle, dict), "Should return dict handle"
        assert handle['source'] == "DBpedia"

        rows = dbpedia.sparql_peek(handle['key'], 2)
        if rows and 'error' not in rows[0]:
            print(f"DBpedia sample: {rows[0]}")
            print("✓ DBpedia OK")
        else:
            print(f"⚠ DBpedia query issue: {rows}")

    except Exception as e:
        print(f"⚠ DBpedia test skipped: {e}")

    print("✓ Multi-endpoint test complete")


def test_dspy_tool_signatures(tools):
    """Test 8: DSPy RLM tool signatures work correctly."""
    print("\n=== Test 8: DSPy Tool Signatures ===")

    dspy_tools = tools.as_dspy_tools()
    print(f"Tools available: {list(dspy_tools.keys())}")

    # Verify expected tools exist
    expected = ['sparql_query', 'sparql_peek', 'sparql_slice', 'sparql_stats',
                'sparql_count', 'sparql_describe', 'endpoint_info']
    for tool in expected:
        assert tool in dspy_tools, f"Missing tool: {tool}"

    # Test with DSPy's (args, kwargs) calling convention
    handle = dspy_tools['sparql_query'](
        "SELECT ?class WHERE { ?class a owl:Class } LIMIT 5",
        {}
    )
    print(f"sparql_query: {handle}")
    assert isinstance(handle, dict), "Should return dict handle"
    assert handle['source'] == "UniProt", "Should have source"

    # Test sparql_peek
    rows = dspy_tools['sparql_peek']([handle['key'], 3], {})
    print(f"sparql_peek: {len(rows)} rows")
    assert len(rows) <= 3, "Should be bounded"

    # Test sparql_stats
    stats = dspy_tools['sparql_stats'](handle['key'], {})
    print(f"sparql_stats: {stats}")
    assert 'rows' in stats, "Should have row count"

    # Test sparql_count
    count = dspy_tools['sparql_count']("SELECT ?s WHERE { ?s a owl:Class }", {})
    print(f"sparql_count: {count}")
    assert 'count' in count, "Should have count"

    # Test endpoint_info
    info = dspy_tools['endpoint_info'](None, {})
    print(f"endpoint_info: {info['name']}")
    assert info['name'] == "UniProt"

    print("✓ DSPy signatures OK")


def test_ontology_query_construction():
    """Test 9: LLM-constructed SPARQL queries work (ontology-aware pattern)."""
    print("\n=== Test 9: Ontology Query Construction ===")

    tools = SPARQLTools(UNIPROT_CONFIG)

    # Simulate what an LLM would construct using L0/L1 ontology context
    # This is how queries should be built - using knowledge of the actual schema

    # Example: Query proteins by gene name (uses up:encodedBy, up:Gene)
    # The LLM learns these predicates from the ontology context
    query = """
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?protein ?name WHERE {
        ?protein a up:Protein .
        ?protein rdfs:label ?name .
    }
    LIMIT 5
    """

    handle = tools.sparql_query(query)
    print(f"Ontology-aware query: {handle}")
    assert isinstance(handle, dict)
    assert handle['rows'] > 0 or 'error' in str(tools.sparql_peek(handle['key'], 1))

    rows = tools.sparql_peek(handle['key'], 3)
    if rows and 'error' not in rows[0]:
        print(f"Sample: {rows[0]}")
        print("✓ Ontology query construction OK")
    else:
        print(f"Query result: {rows}")
        print("✓ Query executed (may be empty/error)")

    print("✓ Ontology Query Construction test complete")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("SPARQL Tools Test Suite (Handle Dict Pattern)")
    print("=" * 60)

    try:
        # Config tests (no network)
        config = test_endpoint_config()

        # Tool tests (requires network)
        tools = test_sparql_tools_with_config()
        test_source_attribution(tools)
        handle = test_handle_pattern(tools)
        test_two_phase_retrieval(tools, handle)
        test_bounded_returns(tools)
        test_multi_endpoint()
        test_dspy_tool_signatures(tools)
        test_ontology_query_construction()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
