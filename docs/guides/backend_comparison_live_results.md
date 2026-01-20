# Backend Comparison: Live Results

Comparison of DSPy RLM vs Claudette backend executing the same query.

**Query:** "What properties have Activity as their domain?"

**Test Date:** 2026-01-20

---

## DSPy RLM Backend

### Execution Profile
- **Iterations:** 5
- **Max Iterations:** 6
- **Converged:** Yes (via SUBMIT)
- **Model:** Sonnet 4.5 (root) + Haiku (sub)
- **Execution Time:** ~17s

### Behavior Characteristics

**Reasoning Pattern:**
- Explicit step-by-step reasoning before each code block
- Self-correcting: Fixed `json` import error, fixed SUBMIT syntax
- Progressive tool usage: search_entity → sparql_select → SUBMIT

**Tool Usage:**
1. `search_entity("Activity")` - Found Activity class URI
2. `sparql_select(query)` - Constructed and executed SPARQL query
3. `SUBMIT(answer=..., sparql=..., evidence=...)` - Structured output

**SPARQL Query Constructed:**
```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?property ?label
WHERE {
  ?property rdfs:domain prov:Activity .
  OPTIONAL { ?property rdfs:label ?label }
}
```

**Output Structure (Typed):**
- **Answer:** List of 14 property labels
- **SPARQL:** Full query with prefixes
- **Evidence:** Dict with activity_uri, properties_found (full results), count

**Strengths:**
- Typed structured outputs (enforced by QueryConstructionSig)
- Explicit reasoning traces visible
- Captures SPARQL query used
- Error recovery and self-correction
- Evidence explicitly structured

**Issues Observed:**
- Some warnings about reaching max_iters on simpler queries (tuning needed)
- Had to iterate to fix import and SUBMIT syntax errors

---

## Claudette Backend

### Execution Profile
- **Iterations:** 4
- **Max Iterations:** 6
- **Converged:** Yes (via FINAL_VAR)
- **Model:** Sonnet 4.5
- **Execution Time:** ~19s

### Behavior Characteristics

**Reasoning Pattern:**
- Natural language reasoning integrated with code
- Direct graph access (uses `prov_graph` directly)
- More exploratory: checks context first, then queries

**Tool Usage:**
1. Examined `context` and `prov_graph` variables
2. Direct `prov_graph.query()` call (rdflib Graph method)
3. Formatted results into numbered list
4. `FINAL_VAR(final_answer)` - Variable-based convergence

**SPARQL Query Constructed:**
```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?property WHERE {
    ?property rdfs:domain prov:Activity .
}
```

**Output Structure:**
- **Answer:** Formatted text with numbered list (14 properties)
- Narrative style: "The following 14 properties have Activity as their domain..."

**Strengths:**
- More direct: accesses `prov_graph` variable immediately
- Clean convergence (fewer iterations)
- Natural language answer formatting
- No syntax errors (stable)

**Differences:**
- No typed output structure (plain string answer)
- SPARQL query not captured separately
- Evidence not structured
- Uses REPL variables directly instead of tool surface

---

## Key Differences Summary

| Aspect | DSPy RLM | Claudette |
|--------|----------|-----------|
| **Output Type** | Typed (answer, sparql, evidence) | Untyped (string) |
| **Tool Surface** | Bounded tools only | Direct graph access |
| **Reasoning** | Explicit before-code reasoning | Integrated with code |
| **Convergence** | SUBMIT(kwargs) | FINAL_VAR(variable) |
| **Error Handling** | Self-correcting (visible) | Stable (no errors) |
| **SPARQL Capture** | Stored separately | Not captured |
| **Evidence** | Structured dict | Not provided |
| **Iterations** | 5 (with 2 corrections) | 4 (clean) |
| **Sub-model** | Haiku for delegation | No sub-model |

---

## Protocol Compliance

Both backends comply with RLM protocol invariants:
- ✅ Code blocks present and executed
- ✅ Converged properly (not max_iters fallback)
- ✅ Bounded views (no graph dumps)
- ✅ Grounded answers (entities from REPL)
- ✅ Expected tools used

---

## Recommendations

**Use DSPy RLM when:**
- You need typed, structured outputs
- SPARQL query capture is important
- Evidence tracking is required
- Building pipelines that process results programmatically
- Want explicit reasoning traces

**Use Claudette when:**
- You need natural language formatted answers
- Prefer direct graph access patterns
- Want stable, proven behavior
- Working interactively with simpler queries

**Both backends:**
- Produce correct answers
- Use progressive disclosure
- Follow RLM protocol
- Handle the same ontology tools

---

## Future Work

1. **DSPy Tuning:** Reduce max_iters warnings on simple queries
2. **Convergence Optimization:** DSPy sometimes needs correction iterations
3. **Backend Selection:** Add auto-selection based on query type
4. **Hybrid Mode:** Use Claudette for exploration, DSPy for structured output
5. **Memory Integration:** Add ReasoningBank to both backends (Phase 5+)
