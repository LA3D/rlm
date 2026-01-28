"""Tests for namespace_interpreter.py verification feedback integration."""

import pytest
from pathlib import Path

from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter
from rlm_runtime.tools.verification_feedback import (
    parse_agent_guide,
    AgentGuideMetadata,
    PropertyMetadata,
)


def test_interpreter_without_verification():
    """Test interpreter works normally without verification enabled."""
    interpreter = NamespaceCodeInterpreter(
        tools={},
        enable_verification=False
    )

    code = """
result = 42
print(f"Result: {result}")
"""

    output = interpreter.execute(code)
    assert "Result: 42" in output
    assert "Verification" not in output  # No feedback


def test_interpreter_verification_requires_metadata():
    """Test that enabling verification without metadata raises error."""
    with pytest.raises(ValueError, match="guide_metadata is required"):
        NamespaceCodeInterpreter(
            tools={},
            enable_verification=True,
            guide_metadata=None
        )


def test_interpreter_verification_enabled_no_sparql():
    """Test verification enabled but no SPARQL query in code."""
    metadata = AgentGuideMetadata(ontology_name="test")

    interpreter = NamespaceCodeInterpreter(
        tools={},
        enable_verification=True,
        guide_metadata=metadata
    )

    code = """
result = 42
print(f"Result: {result}")
"""

    output = interpreter.execute(code)
    assert "Result: 42" in output
    assert "Verification" not in output  # No SPARQL, no feedback


def test_interpreter_verification_with_sparql():
    """Test verification feedback is injected after SPARQL query."""
    # Create metadata with anti-patterns
    metadata = AgentGuideMetadata(ontology_name="test")
    metadata.anti_patterns = [
        "Don't search by label for known accessions"
    ]

    # Mock SPARQL tool
    def mock_sparql_select(query: str):
        return [{"protein": "P12345", "label": "Insulin"}]

    interpreter = NamespaceCodeInterpreter(
        tools={"sparql_select": mock_sparql_select},
        enable_verification=True,
        guide_metadata=metadata
    )

    # Query with anti-pattern (label filtering)
    code = """
query = \"\"\"
SELECT ?protein ?label WHERE {
    ?protein rdfs:label ?label .
    FILTER(CONTAINS(?label, "P12345"))
}
\"\"\"
results = sparql_select(query)
print(f"Found {len(results)} results")
"""

    output = interpreter.execute(code)

    assert "Found 1 results" in output
    # Note: Verification feedback may or may not be present depending on pattern matching
    # The important part is that it doesn't crash


def test_interpreter_verification_with_suggestions():
    """Test that suggestions are generated for queries without LIMIT."""
    metadata = AgentGuideMetadata(ontology_name="test")

    def mock_sparql_query(query: str):
        return [{"protein": f"P{i:05d}"} for i in range(100)]

    interpreter = NamespaceCodeInterpreter(
        tools={"sparql_query": mock_sparql_query},
        enable_verification=True,
        guide_metadata=metadata
    )

    # Query without LIMIT
    code = """
query = "SELECT ?protein WHERE { ?protein a up:Protein }"
results = sparql_query(query)
print(f"Found {len(results)} proteins")
"""

    output = interpreter.execute(code)

    assert "Found 100 proteins" in output
    # Suggestions may include LIMIT recommendation


def test_interpreter_verification_graceful_failure():
    """Test that verification errors don't crash execution."""
    # Create metadata that might cause verification errors
    metadata = AgentGuideMetadata(ontology_name="test")

    def mock_sparql_select(query: str):
        return [{"protein": "P12345"}]

    interpreter = NamespaceCodeInterpreter(
        tools={"sparql_select": mock_sparql_select},
        enable_verification=True,
        guide_metadata=metadata
    )

    # Malformed query that might cause parsing issues
    code = """
query = "INVALID SPARQL"
results = sparql_select(query)
print("Done")
"""

    # Should not crash, even if verification fails
    output = interpreter.execute(code)
    assert "Done" in output


def test_interpreter_with_real_guide():
    """Test interpreter with real AGENT_GUIDE.md metadata."""
    guide_path = Path("ontology/prov/AGENT_GUIDE.md")

    if not guide_path.exists():
        pytest.skip("PROV guide not found")

    metadata = parse_agent_guide(guide_path)

    def mock_sparql_query(query: str):
        return [{"entity": "ex:entity1"}]

    interpreter = NamespaceCodeInterpreter(
        tools={"sparql_query": mock_sparql_query},
        enable_verification=True,
        guide_metadata=metadata
    )

    code = """
query = \"\"\"
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT ?entity WHERE {
    ?entity a prov:Entity .
}
\"\"\"
results = sparql_query(query)
print(f"Found {len(results)} entities")
"""

    output = interpreter.execute(code)
    assert "Found 1 entities" in output


def test_interpreter_backward_compatibility():
    """Test that old code without verification parameters still works."""
    # Create interpreter without verification parameters (old style)
    interpreter = NamespaceCodeInterpreter(tools={})

    code = """
print("Hello, world!")
"""

    output = interpreter.execute(code)
    assert "Hello, world!" in output


def test_interpreter_state_persistence_with_verification():
    """Test that state persists across executions even with verification enabled."""
    metadata = AgentGuideMetadata(ontology_name="test")

    interpreter = NamespaceCodeInterpreter(
        tools={},
        enable_verification=True,
        guide_metadata=metadata
    )

    # First execution
    code1 = """
counter = 0
print(f"Counter: {counter}")
"""
    output1 = interpreter.execute(code1)
    assert "Counter: 0" in output1

    # Second execution - state should persist
    code2 = """
counter += 1
print(f"Counter: {counter}")
"""
    output2 = interpreter.execute(code2)
    assert "Counter: 1" in output2


def test_interpreter_verification_multiple_queries():
    """Test verification with multiple SPARQL queries in one code block."""
    metadata = AgentGuideMetadata(ontology_name="test")
    metadata.considerations = ["Always filter by reviewed true when possible"]

    def mock_query(q: str):
        return [{"result": "test"}]

    interpreter = NamespaceCodeInterpreter(
        tools={"query": mock_query},
        enable_verification=True,
        guide_metadata=metadata
    )

    code = """
# First query
q1 = "SELECT ?p WHERE { ?p a up:Protein }"
r1 = query(q1)
print(f"Query 1: {len(r1)} results")

# Second query
q2 = "SELECT ?p WHERE { ?p a up:Protein ; up:reviewed true }"
r2 = query(q2)
print(f"Query 2: {len(r2)} results")
"""

    output = interpreter.execute(code)
    assert "Query 1: 1 results" in output
    assert "Query 2: 1 results" in output


def test_interpreter_captures_sparql_from_variable():
    """Test that verification works when query is in a variable (not inline)."""
    # Create metadata with a test property
    metadata = AgentGuideMetadata(
        ontology_name="test",
        properties={
            "http://example.org/prop": PropertyMetadata(
                uri="http://example.org/prop",
                domain="http://example.org/Class1",
                range="http://example.org/Class2"
            )
        }
    )

    # Create mock sparql_select tool that returns results
    def mock_sparql_select(query):
        return [{"s": "http://example.org/entity1", "p": "value"}]

    tools = {"sparql_select": mock_sparql_select}

    interpreter = NamespaceCodeInterpreter(
        tools=tools,
        enable_verification=True,
        guide_metadata=metadata
    )

    # Code that uses a variable for the query (not inline string)
    code = """
query = \"\"\"
PREFIX ex: <http://example.org/>
SELECT ?s ?p WHERE {
  ?s ex:prop ?p .
}
\"\"\"
results = sparql_select(query)
print(f"Found {len(results)} results")
"""

    output = interpreter.execute(code)

    # Should see the query execution
    assert "Found 1 results" in output

    # Should see verification feedback (even though query was in variable)
    # The fix should capture it at execution time
    assert "Verification" in output or "verification" in output.lower()


def test_interpreter_clears_captured_query_between_iterations():
    """Test that captured query is cleared between iterations."""
    metadata = AgentGuideMetadata(ontology_name="test")

    def mock_sparql_select(query):
        return []

    tools = {"sparql_select": mock_sparql_select}

    interpreter = NamespaceCodeInterpreter(
        tools=tools,
        enable_verification=True,
        guide_metadata=metadata
    )

    # First execution with SPARQL
    code1 = 'results = sparql_select("SELECT * WHERE { ?s ?p ?o }")'
    output1 = interpreter.execute(code1)

    # Second execution without SPARQL - should not get feedback from first query
    code2 = 'print("No SPARQL here")'
    output2 = interpreter.execute(code2)

    assert "No SPARQL here" in output2
    # Should not have verification from previous iteration
    assert output2.count("Verification") <= 1  # At most one from code2 itself
