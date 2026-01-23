# Tool Usage Inefficiency Analysis - Trial 2 Deep Dive

**Date:** 2026-01-22
**Trial:** Trial 2 (10 iterations, with 2 memories retrieved)
**Task:** Select all bacterial taxa and their scientific names

---

## Executive Summary

Even with ReasoningBank memories, **Trial 2 still shows significant tool usage inefficiencies:**

- **6 remote queries** made (iterations 4-9)
- Only iteration 9's query produced the final answer
- **Iterations 5-8 were exploratory** when execution should have started
- **Excessive Python boilerplate** in every iteration (print statements, for loops)
- **Redundant describe_entity/probe_relationships** calls after remote queries working

**Net result:** 10 iterations when 5-6 would suffice with better tool discipline.

---

## Iteration-by-Iteration Analysis

### Iterations 1-3: Local Schema Exploration (GOOD ✓)
**What happened:**
- Iteration 1: query(local) → Found classes
- Iteration 2: query(local) → Found properties
- Iteration 3: query(local) → Found name-related properties

**Assessment:** **Efficient.** These 3 iterations accomplished what they needed to.

---

### Iteration 4: First Remote Query (MIXED ±)
**Tools:** query(local), sparql_query(remote), search_entity(), res_head()

**Code:**
```python
test_query = """
PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?taxon ?scientificName
WHERE {
  ?taxon a up:Taxon .
  ?taxon up:scientificName ?scientificName .
}
LIMIT 10
"""
test_result = sparql_query(test_query, "test_taxa")
sample = res_head("test_taxa", 10)
```

**Assessment:** **Good start, but:**
- Got 10 taxa successfully
- Should have immediately tried hierarchical query here
- Instead continued exploring in next iterations

---

### Iteration 5: Bacteria Taxon Exploration (INEFFICIENT ❌)
**Tools:** describe_entity(), sparql_query(), res_head()

**Code:**
```python
bacteria_uri = "http://purl.uniprot.org/taxonomy/2"
bacteria_info = describe_entity(bacteria_uri, limit=20)

lineage_test_query = """
SELECT ?taxon ?scientificName
WHERE {
  ?taxon a up:Taxon .
  ?taxon up:scientificName ?scientificName .
  ?taxon up:partOfLineage <http://purl.uniprot.org/taxonomy/2> .
}
LIMIT 20
"""
```

**Problems:**
1. **describe_entity() on Bacteria taxon** - exploratory when we already know what we need
2. **Tried up:partOfLineage** - wrong property (doesn't exist or isn't used)
3. **Still exploring instead of executing**

**Better approach:**
```python
# Skip describe_entity, go straight to hierarchy query
query = """
SELECT ?taxon ?scientificName
WHERE {
  ?taxon a up:Taxon .
  ?taxon rdfs:subClassOf+ <http://purl.uniprot.org/taxonomy/2> .
  ?taxon up:scientificName ?scientificName .
}
"""
```

---

### Iteration 6: Exploratory Taxa Query (INEFFICIENT ❌)
**Tools:** sparql_query(), res_head()

**Code:**
```python
explore_query = """
SELECT ?taxon ?scientificName ?rank ?lineage
WHERE {
  ?taxon a up:Taxon .
  ?taxon up:scientificName ?scientificName .
  OPTIONAL { ?taxon up:rank ?rank }
  OPTIONAL { ?taxon up:partOfLineage ?lineage }
}
LIMIT 50
"""
```

**Problems:**
1. **Pure exploration** - getting 50 random taxa
2. **Checking optional properties** that aren't helping find bacteria
3. **Should be testing hierarchy predicates instead**

---

### Iteration 7: Single Taxon Lineage Check (INEFFICIENT ❌)
**Tools:** sparql_query(), res_head()

**Code:**
```python
test_taxon_uri = "http://purl.uniprot.org/taxonomy/10"
lineage_detail_query = f"""
SELECT ?lineageTaxon
WHERE {{
  <{test_taxon_uri}> up:partOfLineage ?lineageTaxon .
}}
"""
```

**Problems:**
1. **Deep dive on ONE taxon** - not helping find ALL bacteria
2. **Still trying up:partOfLineage** - should have abandoned this property
3. **Says "now let's construct final query"** - but doesn't finish!

---

### Iteration 8: Existence Check + More Exploration (INEFFICIENT ❌)
**Tools:** sparql_query(), probe_relationships(), res_head()

**Code:**
```python
bacteria_exists_query = """
SELECT ?p ?o
WHERE {
  <http://purl.uniprot.org/taxonomy/2> ?p ?o .
}
"""

relationships = probe_relationships(test_taxon, predicate="", direction="outgoing", limit=20)
```

**Problems:**
1. **Checking if Bacteria exists** - we already know it does!
2. **probe_relationships() on test taxon** - more deep exploration
3. **Not testing hierarchical properties** (rdfs:subClassOf, skos:narrower)

---

### Iteration 9: SKOS Discovery (FINALLY! ✓)
**Tools:** sparql_query(), res_head()

**Code:**
```python
final_query = """
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?taxon ?scientificName
WHERE {
  ?taxon a up:Taxon .
  ?taxon up:scientificName ?scientificName .
  <http://purl.uniprot.org/taxonomy/2> skos:narrowerTransitive+ ?taxon .
}
"""
```

**Assessment:** **Success!** Found the right property (skos:narrowerTransitive) and got all bacteria.

---

### Iteration 10: SUBMIT (GOOD ✓)
**Tools:** res_head(), SUBMIT()

**Assessment:** Correctly submitted with evidence.

---

## Root Cause Analysis

### Issue 1: Over-Exploration After Remote Connection Works

**Pattern:** Iterations 5-8 keep making exploratory queries after iteration 4 proved remote connection works.

**Why it happens:**
- Agent doesn't recognize "exploration → execution" phase transition
- No feedback saying "you have connectivity, now query for the answer"
- ReasoningBank memories say "explore systematically" but don't say "STOP exploring once you have schema"

**Proposed feedback mechanism:**
```
If remote query succeeds (returns results), you are ready to execute.
Stop exploring individual entities or properties.
Construct a hierarchical query using rdfs:subClassOf or skos:narrower.
```

---

### Issue 2: Testing Wrong Properties Instead of Systematic Search

**Pattern:** Iterations 5-7 repeatedly try `up:partOfLineage` which doesn't work.

**Why it happens:**
- Agent fixates on one property without testing alternatives
- No feedback loop saying "this property returns no results, try others"
- Should systematically test: rdfs:subClassOf, skos:narrower, up:parent, etc.

**Proposed feedback mechanism:**
```
If a hierarchical property returns 0 results after 2 attempts:
  1. List alternative hierarchy properties to test
  2. Use probe_relationships() to discover actual properties
  3. Query local ontology for property definitions
```

---

### Issue 3: Deep Exploration of Individual Entities

**Pattern:** Iteration 7 checks lineage for ONE taxon instead of querying for ALL bacteria.

**Why it happens:**
- Agent treats this like a "find one example" task instead of "find all instances"
- No reminder that task requires ALL bacteria, not just verifying one

**Proposed feedback mechanism:**
```
Your task is to find ALL bacterial taxa, not inspect individual examples.
Use queries with transitive properties (?taxon subClassOf+ bacteria)
Avoid LIMIT clauses when building the final answer query.
```

---

### Issue 4: Excessive Python Boilerplate

**Pattern:** Every iteration has ~15-45 lines of code, mostly print() and for loops.

**Example from iteration 2:**
```python
properties_query = """..."""
props_result = query(properties_query)
props = res_head("props", 100)

print("Properties in ontology (first 30):")
for i, row in enumerate(props[:30]):
    print(f"  {i+1}. {row}")
```

**Why it happens:**
- Agent prints everything to "see" the data
- Results are already logged/available - printing is redundant
- Tool outputs should be trusted without manual inspection

**Proposed feedback mechanism:**
```
Tool results are automatically logged. Do NOT print them.
Use res_head/res_sample to inspect, but trust the output without printing.
Focus code on QUERIES and LOGIC, not display.

Good: sparql_query(query, name)
Bad:  result = sparql_query(...); for row in result: print(row)
```

---

### Issue 5: No Utilization of Local Ontology After Iteration 3

**Pattern:** Iterations 4-10 never use query(local) again, even though it could help.

**Why it happens:**
- Agent switches to remote-only mode
- Local ontology could show property definitions (rdfs:subClassOf, skos:narrower)
- Could use describe_entity on local ontology classes

**Proposed feedback mechanism:**
```
If stuck finding the right property:
  1. Use query(local) to check property definitions
  2. Use describe_entity(class_uri) on local ontology
  3. Test properties found locally on remote endpoint
```

---

### Issue 6: describe_entity/probe_relationships Used After Remote Works

**Pattern:** Iteration 5 uses describe_entity, iteration 8 uses probe_relationships.

**Why it happens:**
- These tools are for exploring unknown structures
- Once remote queries return data, schema is validated
- Continuing to explore individual entities wastes iterations

**Proposed feedback mechanism:**
```
describe_entity() and probe_relationships() are for schema discovery.
Once remote queries return results, stop entity-level exploration.
Switch to query construction and execution.
```

---

## Comparison: What Optimal Tool Use Would Look Like

### Current (10 iterations):
1. query(local) - explore classes ✓
2. query(local) - explore properties ✓
3. query(local) - find taxonomy props ✓
4. sparql_query(remote) - test connection ✓
5. ❌ describe_entity + sparql_query - explore bacteria taxon
6. ❌ sparql_query - explore random taxa
7. ❌ sparql_query - check one taxon lineage
8. ❌ sparql_query + probe_relationships - existence check
9. sparql_query - **SKOS query works!** ✓
10. SUBMIT ✓

### Optimal (5-6 iterations):
1. query(local) - explore classes ✓
2. query(local) - explore properties including hierarchical ✓
3. sparql_query(remote) - test connection + test rdfs:subClassOf ✓
4. sparql_query(remote) - try skos:narrower if rdfs fails ✓
5. sparql_query(remote) - refine query if needed
6. SUBMIT ✓

**Savings: 4-5 iterations (40-50% reduction)**

---

## Proposed Feedback Mechanisms

### 1. Phase Transition Guidance (In Context)

Add to task context after memories:
```markdown
## Execution Phases

**Phase 1: Schema Discovery (1-3 iterations)**
- Use query(local) to find classes and properties
- Identify target class (e.g., up:Taxon) and hierarchical properties
- **Exit condition:** Found target class + hierarchical property

**Phase 2: Connection Test (1 iteration)**
- Use sparql_query(remote) to test connectivity
- Verify target class exists on remote endpoint
- **Exit condition:** Remote query returns results

**Phase 3: Query Construction (1-2 iterations)**
- Test hierarchical queries (rdfs:subClassOf+, skos:narrower+)
- Refine query based on results
- **Exit condition:** Query returns expected results

**Phase 4: Submit (1 iteration)**
- Use SUBMIT with final query, answer, and evidence
```

### 2. Tool Usage Rules (In Context)

```markdown
## Tool Usage Guidelines

**After remote connection succeeds:**
- ❌ STOP using describe_entity() on individual entities
- ❌ STOP making exploratory queries for random samples
- ✅ START testing hierarchical predicates systematically
- ✅ Use query(local) if stuck finding properties

**If a property returns 0 results twice:**
- Try alternative properties (rdfs:subClassOf, skos:narrower, etc.)
- Use probe_relationships() to discover actual properties
- Don't repeat the same failing property

**Minimize Python boilerplate:**
- Tool outputs are logged automatically
- Don't print() results - trust the tools
- Focus on queries, not display formatting
```

### 3. Result-Based Feedback (Tool Output Enhancement)

Enhance tool outputs with feedback:

**Current:**
```
SELECT result with 10 rows, columns: ['taxon', 'scientificName'], stored in 'test_taxa'
```

**Enhanced:**
```
SELECT result with 10 rows, columns: ['taxon', 'scientificName'], stored in 'test_taxa'

✓ Remote connection working! Schema validated.
→ Next: Test hierarchical query (rdfs:subClassOf+, skos:narrower+) to find all bacteria.
```

**On empty results:**
```
SELECT result with 0 rows, columns: ['taxon'], stored in 'lineage_test'

✗ Property 'up:partOfLineage' returned no results (attempt 2/3).
→ Consider alternative properties: rdfs:subClassOf, skos:narrower, skos:broader
→ Use probe_relationships() to discover actual hierarchy properties
```

### 4. Iteration Budget Awareness

Add iteration counter to context:
```
Iteration 5 of 15
You have used 4 iterations for exploration.
Consider moving to query construction phase.
```

---

## Impact Analysis: If Feedback Applied

**Current trajectory:**
- Iterations 1-3: Schema exploration (necessary)
- Iterations 4-8: Mixed exploration/execution (wasteful)
- Iteration 9: Correct query (success)
- Iteration 10: Submit

**With feedback:**
- Iterations 1-2: Schema exploration (phase 1)
- Iteration 3: Connection test (phase 2)
- Iteration 4-5: Hierarchical queries (phase 3)
- Iteration 6: Submit (phase 4)

**Expected savings: 40-50% iteration reduction (10 → 5-6)**

---

## Recommendations Priority

### High Priority (Immediate Impact)
1. **Phase transition guidance in context** - helps agent know when to stop exploring
2. **Tool usage rules after remote success** - prevents describe_entity/probe_relationships waste
3. **Property failure feedback** - stops repeated attempts with wrong properties

### Medium Priority (Incremental Improvement)
4. **Minimize boilerplate reminder** - reduces code size, may speed up generation
5. **Iteration budget awareness** - provides urgency signal

### Low Priority (Nice to Have)
6. **Enhanced tool output feedback** - richer but may add noise
7. **Systematic property testing** - helpful but agent should learn this from memories

---

## Next Steps

1. **Implement phase transition guidance** in task context
2. **Add tool usage rules** after memory retrieval
3. **Run 3 new trials** with feedback to measure impact
4. **Compare:** 10 avg iterations (current) vs expected 6-7 (with feedback)
5. **Iterate on feedback wording** based on agent response

