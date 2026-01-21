# UniProt Affordance-Guided SPARQL Test Results

**Date:** 2026-01-21
**Test:** Real UniProt multi-graph query with minimal tool surface + sense card affordances
**Task:** "List UniProtKB proteins related to a genetic disease, including disease comment and optional MIM cross-reference"
**Result:** ✓ **SUCCESS** - LLM correctly discovered and used multi-graph architecture

## Executive Summary

The test validates that **affordance-guided SPARQL construction works** for production-scale remote endpoints. The LLM successfully:
- Discovered UniProt's multi-graph architecture from context guidance
- Constructed correct GRAPH clauses on first attempt (iteration 2)
- Iteratively refined query through progressive disclosure (11 iterations total)
- Converged to correct solution with 100% pattern match

## Key Metrics

| Metric | Value | Assessment |
|--------|-------|------------|
| **Convergence** | True | ✓ Success |
| **Iterations** | 11 | Reasonable for multi-graph discovery |
| **Multi-graph SPARQL** | ✓ Both graphs | Correctly used uniprot + diseases graphs |
| **Query correctness** | 100% | All required patterns present |
| **Progressive disclosure** | ✓ | Explored schema via bounded tools |
| **Tool surface** | Minimal (6 tools) | sparql_query + 5 view functions |

## Affordance Analysis

### What Worked

#### 1. Multi-Graph Architecture Guidance (Immediate Success)

**Context provided:**
```
1. **Multi-Graph Architecture**: UniProt uses named graphs to organize data:
   - `<http://sparql.uniprot.org/uniprot>` - Core protein data
   - `<http://sparql.uniprot.org/diseases>` - Disease annotations
   - `<http://sparql.uniprot.org/taxonomy>` - Taxonomy data

2. **Cross-Graph Queries**: When querying data from multiple graphs, use GRAPH clauses:
   GRAPH <http://sparql.uniprot.org/uniprot> { ... }
   GRAPH <http://sparql.uniprot.org/diseases> { ... }
```

**LLM response (iteration 2):**
> "From the context, I know:
> - UniProt uses multi-graph architecture
> - Disease data is in `<http://sparql.uniprot.org/diseases>` graph
> - Core protein data is in `<http://sparql.uniprot.org/uniprot>` graph
> - I should use GRAPH clauses for cross-graph queries"

**First SPARQL query (iteration 2) already included GRAPH clauses:**
```sparql
GRAPH <http://sparql.uniprot.org/uniprot> {
  ?protein a up:Protein ;
           up:annotation ?annotation .
  ?annotation a up:Disease_Annotation ;
              up:disease ?disease .
}
GRAPH <http://sparql.uniprot.org/diseases> {
  ?disease a up:Disease .
}
```

**Verdict:** ✓ Context guidance was immediately effective. No trial-and-error needed.

#### 2. Progressive Disclosure via Bounded Tools

The LLM explored the schema incrementally:
- **Iteration 2:** Basic structure with GRAPH clauses
- **Iteration 3-4:** Added disease names, discovered multiple name predicates
- **Iteration 5-9:** Investigated which predicate to use (rdfs:label, skos:altLabel, skos:prefLabel)
- **Iteration 10:** Settled on skos:prefLabel for single preferred name
- **Iteration 11:** Final SUBMIT with complete query

**Tool usage pattern:**
```
sparql_query() → res_head() → examine results → refine query → repeat
```

This follows the RLM handles-not-dumps philosophy: results stored as handles, inspected via bounded views.

#### 3. Sense Card with SPARQL Templates

**Sense card provided:**
- UniProt core ontology metadata
- 214 classes, 163 properties
- Primary label property: rdfs:label
- Primary description property: rdfs:comment
- **SPARQL templates showing:**
  - How to query for entity descriptions
  - How to find relationships
  - How to construct WHERE clauses

**LLM consulted sense card for:**
- Understanding available predicates (up:annotation, up:disease)
- Knowing rdfs:comment is used for annotations
- Schema organization (Protein → Disease_Annotation → Disease)

**Verdict:** ✓ Sense card provided structural guidance without prescribing exact query.

### What Could Be Improved

#### 1. Disease Name Discovery Took 7 Iterations

**Issue:** LLM explored multiple predicates to find disease names:
- Tried rdfs:label (returned None)
- Tried both rdfs:label and skos:altLabel (returned multiple names)
- Investigated what properties diseases have
- Discovered skos:prefLabel is the preferred single name

**Root cause:** Sense card was for UniProt *core* ontology, not the diseases graph. The diseases graph uses SKOS vocabulary conventions which weren't documented in the sense card.

**Potential improvement:**
- Multi-ontology sense cards for federated/multi-graph scenarios
- Or: Include common vocabulary patterns (SKOS, Dublin Core) in base context
- Or: Procedural memory with "disease name discovery" patterns

**Impact:** Low severity - system still converged correctly, just took longer.

#### 2. ORDER BY Syntax Error (Iteration 4)

**Issue:** LLM tried to use ORDER BY clause, got parse error, removed it and continued.

**Root cause:** Minor syntax issue, possibly UniProt endpoint doesn't support ORDER BY without LIMIT, or needed different syntax.

**Handling:** ✓ LLM recovered gracefully, removed ORDER BY, query succeeded.

**Impact:** Minimal - added 1 iteration but no fundamental issue.

## Trajectory Highlights

### Iteration 1: Context Examination
```python
print("=== QUERY ===")
print(query)
print("\n=== CONTEXT (full) ===")
print(context)
```
**Observation:** LLM first reads full context to understand task.

### Iteration 2: First SPARQL with GRAPH Clauses ✓
```sparql
SELECT ?protein ?disease ?comment ?mim
WHERE {
  GRAPH <http://sparql.uniprot.org/uniprot> {
    ?protein a up:Protein ;
             up:annotation ?annotation .
    ?annotation a up:Disease_Annotation ;
                up:disease ?disease .
    OPTIONAL { ?annotation rdfs:comment ?comment }
  }
  GRAPH <http://sparql.uniprot.org/diseases> {
    ?disease a up:Disease .
    OPTIONAL { ?disease rdfs:seeAlso ?mim .
               FILTER(CONTAINS(STR(?mim), "mim")) }
  }
}
```
**Success:** All structural elements correct from first query!

### Iterations 3-10: Schema Exploration
- Added protein mnemonics (up:mnemonic)
- Discovered disease naming: skos:prefLabel vs rdfs:label vs skos:altLabel
- Counted total results (7,173 protein-disease associations)
- Extracted MIM IDs from URIs using STRAFTER

**Observation:** This is *genuine schema discovery* - LLM wasn't told which predicates to use for names, it explored and found them.

### Iteration 11: Final SUBMIT
```python
SUBMIT(
    answer=answer_text,
    sparql=final_sparql,
    evidence=evidence_dict
)
```

**Final SPARQL:**
```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?protein ?diseaseName ?comment ?mim
WHERE {
  GRAPH <http://sparql.uniprot.org/uniprot> {
    ?protein a up:Protein ;
             up:annotation ?annotation .
    ?annotation a up:Disease_Annotation ;
                rdfs:comment ?comment ;
                up:disease ?disease .
  }
  GRAPH <http://sparql.uniprot.org/diseases> {
    ?disease a up:Disease ;
             skos:prefLabel ?diseaseName .
    OPTIONAL {
      ?disease rdfs:seeAlso ?mim .
      FILTER(CONTAINS(STR(?mim), "mim"))
    }
  }
}
```

**Pattern match:** ✓ Matches exemplar structure from eval task (lines 17-29 of genetic_disease_related_proteins.ttl)

## Comparison to Previous Tests

### Local Ontology Tests (PROV, SKOS, SystemsLite, VOID)
- **Iterations:** 4.5 average (55% faster than original 10)
- **Tool surface:** search_entity + sparql_select (minimal, local graph)
- **Success rate:** 100% convergence

### Remote UniProt Test (This Test)
- **Iterations:** 11 (higher due to schema exploration)
- **Tool surface:** sparql_query + 5 view functions (minimal, remote endpoint)
- **Success rate:** 100% convergence + correct multi-graph pattern
- **Additional complexity:** Multi-graph architecture, remote endpoint latency, larger schema (214 classes vs ~30 in test ontologies)

**Conclusion:** Minimal tool surface + affordance guidance scales to production complexity.

## Implications for Phase 4 Eval Harness

### What to Measure

Based on this test, Phase 4 eval harness should measure:

#### 1. Structural Operator Usage (HIGH PRIORITY)
- **GRAPH clause usage:** Did query include correct named graphs?
- **SERVICE federation:** For federated queries (ChEMBL, OrthoDB)
- **Property paths:** For hierarchy/transitive queries
- **OPTIONAL patterns:** For optional fields like MIM

**Grading criteria:**
```yaml
- type: evidence_pattern
  required:
    - function: "GRAPH <http://sparql.uniprot.org/uniprot>"
    - function: "GRAPH <http://sparql.uniprot.org/diseases>"
    - function: "up:Disease"
    - function: "up:disease"
```

#### 2. Progressive Disclosure Behavior (MEDIUM PRIORITY)
- **Iteration count:** Should converge within reasonable bounds (< 15 for complex queries)
- **Tool usage patterns:** Should use res_head/res_sample before constructing final query
- **Exploration efficiency:** Should not re-query same information multiple times

**Grading criteria:**
```yaml
- type: convergence
  max_iterations: 15
- type: tool_called
  required: ["sparql_query"]
  sequence: ["sparql_query", "res_head"]  # Should inspect before refining
```

#### 3. Affordance Value (RESEARCH QUESTION)
**RQ1:** Does sense card reduce errors?
**Measurement:** Compare runs with/without sense card SPARQL templates

**RQ2:** Does procedural memory help?
**Measurement:** Track iteration count with/without memory retrieval

**RQ3:** Do affordances enable bootstrapping?
**Measurement:** Can system handle novel ontologies without pre-training?

### What NOT to Measure (Yet)

- **Exact SPARQL match:** Schema exploration means queries won't match exemplar exactly (different variable names, predicate ordering)
- **Iteration count minimization:** 11 iterations for schema discovery is reasonable
- **Tool usage minimization:** Progressive disclosure requires exploration

### Recommended Phase 4 Implementation

1. **TaskRunner DSPy integration:**
   - Use `run_dspy_rlm_with_tools()` for remote SPARQL tasks
   - Build sense cards from local ontology files
   - Create remote tools via `make_sparql_tools(endpoint, ns)`

2. **Grading enhancements:**
   - New grader: `structural_sparql` - checks for GRAPH/SERVICE/property paths
   - Enhanced `evidence_pattern` - supports regex for flexible matching
   - New metric: `schema_exploration_efficiency` - tool calls per unique discovery

3. **Test categorization:**
   ```
   uniprot/multigraph/    - GRAPH clause tests (like this one)
   uniprot/federated/     - SERVICE clause tests (ChEMBL, OrthoDB)
   uniprot/taxonomy/      - Property path tests (rdfs:subClassOf+)
   uniprot/complex/       - Multi-hop reasoning (dopamine metabolism)
   ```

4. **Sense card enhancements:**
   - Include common vocab guidance (SKOS, DCTERMS, FOAF)
   - Multi-ontology sense cards for federated scenarios
   - Named graph architecture documentation

## Files Generated

1. **Test script:** `examples/test_uniprot_genetic_disease.py` (308 lines)
2. **Trajectory log:** `test_uniprot_genetic_disease.jsonl` (50+ log events)
3. **This report:** `docs/findings/uniprot-affordance-test-results.md`

## Next Steps

### Immediate (Phase 4 Preparation)
1. ✓ Test current system with real UniProt query (COMPLETED)
2. Implement TaskRunner DSPy backend integration
3. Create structural_sparql grader for GRAPH/SERVICE patterns
4. Run full UniProt eval suite with DSPy backend

### Near-term (Phase 4 Execution)
1. Measure affordance value empirically (with/without sense cards)
2. Test procedural memory retrieval for multi-graph patterns
3. Validate across all 8 UniProt task categories
4. Establish baseline metrics for Phase 5 (human feedback)

### Research Questions to Answer
- **RQ1 (Sense card value):** Does SPARQL template inclusion reduce iterations?
- **RQ2 (Memory value):** Do retrieved patterns accelerate convergence?
- **RQ3 (Bootstrapping):** Can system handle novel ontologies without examples?
- **RQ4 (Tool surface):** Is minimal tool set sufficient for all structural operators?

## Conclusion

This test **validates the core hypothesis** of trajectory_v3: ontology affordances (sense cards + context guidance + minimal tools) enable LLMs to discover and construct correct SPARQL queries for production-scale knowledge graphs.

**Key evidence:**
- ✓ Multi-graph architecture discovered from context (iteration 2)
- ✓ Correct GRAPH clauses on first SPARQL attempt
- ✓ Progressive schema exploration via bounded tools
- ✓ 100% convergence with all required patterns
- ✓ Minimal tool surface (6 tools) sufficient for complex queries

**Critical finding:** The LLM did not need pre-programmed knowledge of UniProt's multi-graph structure. The context guidance was sufficient for discovery.

This demonstrates the **self-bootstrapping ontology navigation** philosophy described in trajectory_v3 (lines 28-56): the system learns the graph structure through exploration, guided by affordances, rather than relying on hardcoded domain knowledge.

**Recommendation:** Proceed with Phase 4 eval harness implementation using this affordance-guided approach as the baseline architecture.
