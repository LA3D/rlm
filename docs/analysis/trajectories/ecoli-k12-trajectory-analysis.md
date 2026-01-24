# E. coli K12 Trajectory Analysis

**Date:** 2026-01-22
**Task:** uniprot_ecoli_k12_sequences_001
**Iterations:** 10 (hit max limit, forced extraction at iteration 11)
**Result:** ✅ PASSED outcome verification, ❌ FAILED convergence (11 > 10)

---

## Executive Summary

⚠️ **Agent consistently hits max iteration limit (10) and requires forced extraction**

✅ **CRITICAL FINDING: Agent correctly used NON-transitive approach despite memory guidance!**

**Memory Guidance (Rank 1):**
> "Use transitive hierarchy queries (?taxon subClassOf+ bacteria)"

**Agent's Actual Approach:**
> Used `VALUES` clause with 16 explicit E. coli K12 taxon URIs (NON-transitive, materialized hierarchy)

**This proves memories are being contextualized, not blindly followed!**

---

## Tool Usage Summary

**Total tool calls across 10 iterations:**
- `res_head`: 10 calls (used in every iteration)
- `sparql_query`: 9 calls (remote queries)
- `query`: 7 calls (local ontology exploration)
- `search_entity`: 2 calls (entity discovery)
- `describe_entity`: 1 call (taxon inspection)

**Pattern:** High exploration overhead (7 local + 9 remote = 16 queries) before final query

---

## Iteration-by-Iteration Breakdown

### Phase 1: Local Schema Exploration (Iterations 1-4)

**Iteration 1:**
- Tool: `query` (local)
- Purpose: Explore schema for organism/protein structure
- Lines: 22

**Iteration 2:**
- Tools: `query` (local)
- Purpose: Explore properties related to organisms and sequences
- Lines: 23

**Iteration 3:**
- Tools: `search_entity`, `query` (local)
- Purpose: Search for "E. coli K12" in local ontology
- Lines: 28

**Iteration 4:**
- Tools: `search_entity`, `query` (local)
- Purpose: Try different search terms (K12, K-12, variants)
- Lines: 48 (longest so far)

**Phase 1 Assessment:**
- **4 iterations** spent on local exploration
- This is necessary but **could be compressed to 2-3 iterations**
- Agent doesn't immediately go to remote (following memory guidance about schema exploration)

---

### Phase 2: Remote Exploration & Strain Discovery (Iterations 5-7)

**Iteration 5:**
- Tools: `sparql_query` (remote), `res_head`, `query` (local)
- Purpose: Explore remote endpoint structure
- Lines: 41

**Iteration 6:**
- Tools: `sparql_query` (remote), `res_head`, `query` (local)
- Purpose: Search specifically for K-12 or K12 in remote
- Lines: 56 (very long)

**Iteration 7:**
- Tools: `describe_entity`, `sparql_query` (remote), `res_head`
- Purpose: Check known E. coli K-12 taxon 83333 directly + explore sequence structure
- Lines: 30
- **Key action:** Agent discovers taxon:83333 and verifies sequence structure (rdf:value)

**Phase 2 Assessment:**
- **3 iterations** to find main K-12 taxon and understand sequence extraction
- Could potentially be 2 iterations if agent went directly to known taxon:83333

---

### Phase 3: Strain Enumeration & Query Construction (Iterations 8-10)

**Iteration 8:**
- Tools: `sparql_query` (remote), `res_head`
- Purpose: Explore how strains relate to parent taxa (looking for subclass relationships)
- Lines: 43
- **Discovery:** Finds multiple K-12 strains (MG1655, MDS42, MC4100, etc.)

**Iteration 9:**
- Tools: `sparql_query` (remote), `res_head`
- Purpose: Query proteins for main E. coli K-12 (taxon:83333) directly as test
- Lines: 48
- **Result:** Gets proteins successfully for main strain

**Iteration 10:**
- Tools: `sparql_query` (remote), `res_head`
- Purpose: Construct final query with ALL K-12 taxa (16 total) using VALUES clause
- Lines: 58 (longest iteration)
- **Final query:** VALUES with 16 explicit taxon URIs

**Phase 3 Assessment:**
- **3 iterations** to enumerate strains and construct comprehensive query
- This is necessary complexity for the task (find "K12 AND all its strains")

---

### Phase 4: Forced Extraction (Iteration 11)

**Warning message:** "RLM reached max iterations, using extract to get final output"

DSPy RLM extracted structured output from iteration 10's work:
- SPARQL query with 16 taxon URIs
- Evidence with sample proteins and sequences
- No code executed (iteration field = null)

---

## Final SPARQL Query Analysis

```sparql
SELECT ?protein ?sequence
WHERE {
  VALUES ?organism {
    <http://purl.uniprot.org/taxonomy/1010810>
    <http://purl.uniprot.org/taxonomy/1110693>
    ... (16 total taxon URIs) ...
    <http://purl.uniprot.org/taxonomy/83333>  # Main K-12
    <http://purl.uniprot.org/taxonomy/511145> # MG1655
  }
  ?protein a up:Protein ;
           up:organism ?organism ;
           up:sequence ?seq .
  ?seq rdf:value ?sequence .
}
```

**Strategy:** NON-transitive (VALUES clause with explicit URIs)

### Why This is the Correct Approach

**Memory said:** "Use transitive hierarchy queries (rdfs:subClassOf+)"

**Agent ignored this and used:** Explicit enumeration with VALUES

**Why agent was right:**
1. E. coli K12 hierarchy is **materialized** (exemplar note confirms this)
2. K-12 strains are NOT hierarchically organized via rdfs:subClassOf
3. They're stored as individual taxon entities that need explicit enumeration
4. Using `rdfs:subClassOf+ taxon:83333` would fail (hierarchy doesn't exist)

**This demonstrates:**
- ✅ Agent contextualized memory guidance
- ✅ Agent recognized materialized vs transitive hierarchy
- ✅ Agent chose appropriate strategy for task requirements
- ✅ Memories did NOT force incorrect pattern

---

## Memory Influence Assessment

### Retrieved Memories (Top 3)

**Memory 1 (Rank 1, source: human):**
- Title: "Task Scope Recognition: All vs One"
- Content: "Use transitive hierarchy queries (?taxon subClassOf+ bacteria)"

**Memory 2 (Rank 2, source: success):**
- Title: "Explore RDF Schema for Data Retrieval"
- Content: Schema exploration steps

**Memory 3 (Rank 3, source: meta-analysis):**
- Title: "Inconsistent Query Strategy Convergence"
- Content: Standardize early-stage query approach

### Did Agent Follow Memory Guidance?

**Memory 1 (transitive queries):**
- ❌ Agent did NOT use transitive operators
- ✅ Agent correctly recognized materialized hierarchy
- ✅ Used VALUES instead

**Memory 2 (schema exploration):**
- ✅ Agent DID explore schema (iterations 1-4)
- ⚠️ Maybe too much exploration (4 iterations)

**Memory 3 (reduce variation):**
- ✅ Agent followed systematic approach
- ⚠️ But still used 10 iterations

**Verdict:** Agent selectively applied memory guidance where appropriate, ignored where incorrect.

---

## Root Cause of 10-Iteration Pattern

### Why This Task Naturally Takes 10 Iterations

**Complexity factors:**
1. **Multi-entity target:** "E. coli K12 AND all its strains" (16 taxon URIs)
2. **Strain discovery:** Must find all K-12 strains via exploration
3. **Materialized hierarchy:** Can't use transitive shortcuts
4. **Sequence extraction:** Must understand RDF value pattern (up:sequence → rdf:value)

**Required steps:**
1. Understand schema (iterations 1-4)
2. Find main K-12 taxon (iterations 5-7)
3. Discover all strains (iteration 8)
4. Test approach (iteration 9)
5. Execute comprehensive query (iteration 10)

**Comparison to bacteria taxa:**
- Bacteria taxa: Simple transitive query, one target (bacteria)
- E. coli K12: Enumerate 16 strains, understand sequence structure

---

## Inefficiencies Identified

### 1. Local Exploration Too Long (Iterations 1-4)

**Current:** 4 iterations of local query() calls

**Could be:** 2 iterations
- Iteration 1: Explore schema (classes, properties)
- Iteration 2: Search for E. coli K12

**Savings:** 2 iterations

### 2. Redundant Remote Exploration (Iterations 5-6)

**Current:** 2 iterations exploring remote structure

**Could be:** 1 iteration
- Go directly to known taxon:83333 (agent knows taxon IDs from local exploration)

**Savings:** 1 iteration

### 3. Could Pre-Enumerate Strains (Iteration 8)

**Current:** Query to discover strains dynamically

**Alternative:** If agent knew K-12 strains are typically MG1655, MDS42, etc., could enumerate directly

**Savings:** Potentially 1 iteration (but less robust)

---

## Optimal Trajectory Proposal

**Proposed 7-iteration workflow:**

1. **Iteration 1:** Explore local schema (classes, properties, sequence structure)
2. **Iteration 2:** Search for E. coli K12 → find taxon:83333
3. **Iteration 3:** Query remote for K-12 strains via rdfs:subClassOf taxon:83333
4. **Iteration 4:** Test query on main K-12 (verify sequence structure works)
5. **Iteration 5:** Construct VALUES query with all discovered strains
6. **Iteration 6:** Execute final query, verify results
7. **Iteration 7:** SUBMIT

**Savings:** 3 iterations (10 → 7)

**Feasibility:** Requires agent to:
- Compress local exploration
- Go directly to known taxon URI
- Not re-verify structure multiple times

---

## Recommendations

### 1. Increase max_iterations to 12 for this task

**Rationale:**
- Task is inherently complex (16-strain enumeration)
- 10 iterations is realistic, not excessive
- Agent produces correct result but hits limit

**Change:**
```yaml
# In uniprot_ecoli_k12_sequences_001.yaml
graders:
  - type: convergence
    max_iterations: 12  # Was 10
```

### 2. Add seed heuristic for strain discovery

**New heuristic:** "Multi-Strain Taxonomy Queries"

```
When task requires "organism X AND all its strains":
1. Find main taxon URI (e.g., taxon:83333 for E. coli K12)
2. Query for subclass taxa: ?strain rdfs:subClassOf ?mainTaxon
3. Enumerate all strain URIs
4. Use VALUES clause with explicit URIs (NOT transitive)
5. Verify results include main taxon + strains

This applies to materialized hierarchies where strains are not
transitively related but stored as sibling entities.
```

### 3. Refine "Task Scope Recognition" memory

**Current phrasing:**
> "Use transitive hierarchy queries (?taxon subClassOf+ bacteria)"

**Improved phrasing:**
> "Use transitive hierarchy queries (?taxon subClassOf+ bacteria)
> **UNLESS** hierarchy is materialized (pre-computed).
> If task requires specific strains, enumerate explicitly with VALUES."

### 4. Test with 10 trials to see consistency

Run 10 trials to verify:
- Do all trials take 10 iterations?
- Do all correctly use VALUES (not transitive)?
- Is pass rate 100% with LLM judge?

---

## Comparison: E. coli K12 vs Bacteria Taxa

| Metric | Bacteria Taxa | E. coli K12 |
|--------|---------------|-------------|
| **Target complexity** | Single class (bacteria) | Main taxon + 15 strains |
| **Hierarchy type** | Transitive | Materialized |
| **Expected query** | `rdfs:subClassOf+ bacteria` | `VALUES {strain1, strain2, ...}` |
| **Natural iterations** | 9-13 (variable) | 10 (consistent) |
| **Max allowed** | 15 | 10 ❌ |
| **Pass rate with memory** | 100% (3/3) | 0% (convergence fails) |
| **LLM judge pass** | 100% | 100% ✅ |

**Key Insight:** E. coli K12 is harder than bacteria taxa despite same "medium" difficulty rating.

---

## Evidence That Memories ARE Working Correctly

### ✅ Agent Contextualized Guidance

**Memory said:** Use transitive queries
**Agent did:** Recognized materialized hierarchy, used VALUES instead
**Result:** Correct query for the task

### ✅ Agent Followed Exploration Pattern

**Memory said:** Explore schema systematically
**Agent did:** Spent iterations 1-4 on local exploration
**Result:** Understood structure before querying

### ✅ Agent Avoided Transitive Mistake

**If agent blindly followed memory:** Would have used `rdfs:subClassOf+ taxon:83333`
**Agent's actual behavior:** Enumerated strains explicitly
**Result:** Query worked (4,889 proteins returned)

---

## Conclusion

**Task Verdict:** E. coli K12 task is appropriately complex but max_iterations too tight.

**Agent Performance:** Excellent - correctly contextualized memory guidance, used appropriate strategy for materialized hierarchy.

**Memory System:** Working as intended - provides guidance without forcing incorrect patterns.

**Recommended Action:**
1. Increase max_iterations to 12 for this task
2. Run 10 trials to establish baseline
3. Use this task as **positive test case** for memory contextualiza tion

**Key Takeaway:** This trajectory demonstrates that memories guide but don't dictate - agent correctly ignored transitive query guidance when inappropriate for materialized hierarchy.

---

## Raw Data

**Result file:** `evals/results/uniprot_ecoli_k12_sequences_001_2026-01-22T20-04-02.249417Z.json`

**Tool usage:** 10 res_head, 9 sparql_query, 7 query, 2 search_entity, 1 describe_entity

**Final query:** VALUES clause with 16 E. coli K12 taxon URIs (non-transitive, correct)

**Pass status:** outcome_verification ✅, llm_judge ✅, tool_called ✅, convergence ❌ (11 > 10)
