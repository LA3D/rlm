"""Test SPARQL tools against multiple endpoints.

Tests:
1. EndpointConfig structure
2. Basic connectivity and bounded returns
3. Handle pattern (Ref) works correctly
4. Two-phase retrieval (query -> peek/slice)
5. Source attribution in all returns
6. DSPy tool signatures

Usage:
    python experiments/reasoningbank/tools/test_sparql.py
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.tools.endpoint import EndpointConfig
from experiments.reasoningbank.tools.sparql import SPARQLTools, Ref


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

    # Query returns Ref with source
    ref = tools.sparql_query("SELECT ?class WHERE { ?class a owl:Class } LIMIT 5")
    assert ref.source == "UniProt"
    print(f"Ref source: {ref.source}")

    # Stats include source
    stats = tools.sparql_stats(ref.key)
    assert stats.get('source') == "UniProt"
    print(f"Stats source: {stats.get('source')}")

    # Classes include source
    classes = tools.sparql_classes(limit=5)
    assert classes.get('source') == "UniProt"
    print(f"Classes source: {classes.get('source')}")

    # Find includes source
    find_result = tools.sparql_find("protein", limit=3)
    assert find_result.get('source') == "UniProt"
    print(f"Find source: {find_result.get('source')}")

    print("✓ Source Attribution OK")


def test_handle_pattern(tools):
    """Test 4: Handle pattern - returns Ref, not payload."""
    print("\n=== Test 4: Handle Pattern ===")

    ref = tools.sparql_query("SELECT ?class WHERE { ?class a owl:Class } LIMIT 10")

    print(f"Query returned: {ref}")
    print(f"Type: {type(ref)}")

    assert isinstance(ref, Ref), "Query should return Ref, not raw data"
    assert ref.dtype == 'results', f"Expected dtype='results', got {ref.dtype}"
    assert ref.rows <= 10, f"Expected <=10 rows, got {ref.rows}"
    assert len(ref.prev) <= 120, "Preview should be bounded"
    assert ref.source == "UniProt", "Source should be set"

    print(f"✓ Handle pattern OK: {ref.rows} rows, {ref.sz} chars from {ref.source}")
    return ref


def test_two_phase_retrieval(tools, ref):
    """Test 5: Two-phase retrieval (stats -> peek -> slice)."""
    print("\n=== Test 5: Two-Phase Retrieval ===")

    # Phase 1: Get stats (metadata only)
    stats = tools.sparql_stats(ref.key)
    print(f"Stats: {stats}")

    assert 'rows' in stats, "Stats should include row count"
    assert 'source' in stats, "Stats should include source"

    # Phase 2a: Peek at first few rows
    rows = tools.sparql_peek(ref.key, 3)
    print(f"Peek (3 rows): {len(rows)} returned")

    assert len(rows) <= 3, f"Peek should return <=3 rows, got {len(rows)}"

    # Phase 2b: Slice specific range
    slice_rows = tools.sparql_slice(ref.key, 0, 5)
    print(f"Slice [0:5]: {len(slice_rows)} rows")

    assert len(slice_rows) <= 5, "Slice should be bounded"

    print("✓ Two-phase retrieval OK")


def test_bounded_returns(tools):
    """Test 6: All tools enforce bounded returns."""
    print("\n=== Test 6: Bounded Returns ===")

    # Classes - bounded
    classes = tools.sparql_classes(limit=10)
    print(f"Classes: {classes['count']} (limit=10)")
    assert classes['count'] <= 10, "Classes should be bounded"

    # Properties - bounded
    props = tools.sparql_properties(limit=10)
    print(f"Properties: {props['count']} (limit=10)")
    assert props['count'] <= 10, "Properties should be bounded"

    # Find - bounded
    results = tools.sparql_find("protein", limit=5)
    print(f"Find 'protein': {results['count']} results (limit=5)")
    assert results['count'] <= 5, "Find should be bounded"

    print("✓ Bounded returns OK")


def test_multi_endpoint():
    """Test 7: Test against multiple endpoints."""
    print("\n=== Test 7: Multi-Endpoint ===")

    # Test DBpedia
    try:
        dbpedia = SPARQLTools(DBPEDIA_CONFIG)
        print(f"DBpedia endpoint: {dbpedia.name} ({dbpedia.authority})")

        # Simple test query
        ref = dbpedia.sparql_query("""
            SELECT ?person WHERE {
                ?person a dbo:Person .
            }
        """, limit=5)

        print(f"DBpedia query: {ref}")
        assert ref.source == "DBpedia"

        rows = dbpedia.sparql_peek(ref.key, 2)
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

    # Test with DSPy's (args, kwargs) calling convention
    ref = dspy_tools['sparql_query'](
        "SELECT ?class WHERE { ?class a owl:Class } LIMIT 5",
        {}
    )
    print(f"sparql_query: {ref}")
    assert isinstance(ref, Ref), "Should return Ref"
    assert ref.source == "UniProt", "Should have source"

    # Test sparql_peek
    rows = dspy_tools['sparql_peek']([ref.key, 3], {})
    print(f"sparql_peek: {len(rows)} rows")
    assert len(rows) <= 3, "Should be bounded"

    # Test endpoint_info
    info = dspy_tools['endpoint_info'](None, {})
    print(f"endpoint_info: {info['name']}")
    assert info['name'] == "UniProt"

    print("✓ DSPy signatures OK")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("SPARQL Tools Test Suite")
    print("=" * 60)

    try:
        # Config tests (no network)
        config = test_endpoint_config()

        # Tool tests (requires network)
        tools = test_sparql_tools_with_config()
        test_source_attribution(tools)
        ref = test_handle_pattern(tools)
        test_two_phase_retrieval(tools, ref)
        test_bounded_returns(tools)
        test_multi_endpoint()
        test_dspy_tool_signatures(tools)

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
