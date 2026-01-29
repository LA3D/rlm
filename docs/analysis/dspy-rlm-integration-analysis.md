# DSPy RLM Integration Analysis

**Date**: 2026-01-28
**Status**: Analysis Complete
**Purpose**: Understand how DSPy signatures/predict integrate with RLM recursive decomposition

---

## Executive Summary

DSPy RLM **does provide** the infrastructure for recursive decomposition via `llm_query()`. The gap is not in DSPy's implementation but in **how we guide the model to use delegation strategically** for ontology exploration.

**Key findings:**

1. ✅ DSPy RLM has built-in `llm_query()` and `llm_query_batched()` with ThreadPoolExecutor
2. ✅ Generic prompt includes "USE llm_query FOR SEMANTICS" guidance (line 59)
3. ❌ Our model never uses it - defaults to tool-first pattern
4. ❌ AGENT_GUIDE.md doesn't teach WHEN to delegate vs search
5. 💡 **Fix**: Add explicit delegation guidance to domain context

---

## How DSPy RLM Works

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DSPy RLM Module                          │
├─────────────────────────────────────────────────────────────────┤
│  Signature (QueryConstructionSig)                               │
│    Inputs: query, context                                       │
│    Outputs: thinking, verification, reflection, answer, sparql  │
├─────────────────────────────────────────────────────────────────┤
│  Built-in Tools (auto-injected by DSPy):                        │
│    - llm_query(prompt) → str                                    │
│    - llm_query_batched([prompts]) → [str] (ThreadPoolExecutor)  │
│    - SUBMIT(**outputs)                                          │
│    - print()                                                    │
├─────────────────────────────────────────────────────────────────┤
│  User Tools (passed by us):                                     │
│    - search_entity(term) → matched entities                     │
│    - sparql_select(query) → results                             │
├─────────────────────────────────────────────────────────────────┤
│  Interpreter: NamespaceCodeInterpreter                          │
│    - Persistent namespace (ns dict)                             │
│    - result_truncation_limit=10000                              │
│    - Verification feedback (optional)                           │
└─────────────────────────────────────────────────────────────────┘
```

### DSPy's Generic Prompt (ACTION_INSTRUCTIONS_TEMPLATE)

```python
"""You are tasked with producing the following outputs...

Available:
- Variables: {inputs} (your input data)
- `llm_query(prompt)` - query a sub-LLM (~500K char capacity) for semantic analysis
- `llm_query_batched(prompts)` - query multiple prompts concurrently
- `print()` - ALWAYS print to see results
- `SUBMIT({final_output_names})` - submit final output when done

IMPORTANT: This is ITERATIVE...

4. USE llm_query FOR SEMANTICS - String matching finds WHERE things are;
   llm_query understands WHAT things mean.
"""
```

**The guidance is there** (line 4: "USE llm_query FOR SEMANTICS") but it's:
- Generic, not domain-specific
- Doesn't explain WHEN to use it for ontology exploration
- Doesn't show examples of delegation patterns

---

## The Integration Gap

### What DSPy RLM Expects

From Prime Intellect's RLM philosophy and DSPy's design:

```
Parent Model (Orchestrator)                Sub-LLM (Focused Analysis)
      │                                           │
      │  llm_query("What is kinase activity      │
      │   in GO terms? Just the ID.")             │
      │ ────────────────────────────────────────► │
      │                                           │
      │            "GO:0016301"                   │
      │ ◄──────────────────────────────────────── │
      │                                           │
      ▼
Use GO:0016301 in SPARQL query
```

**Recursive decomposition pattern:**
1. Parent model encounters semantic ambiguity
2. Delegates to sub-LLM with focused prompt
3. Sub-LLM returns specific answer (GO ID, URI, etc.)
4. Parent model uses answer in structured query

### What Our Model Actually Does

```
Model (Tool-First Pattern)
      │
      │ search_entity("kinase activity")  → 0 results
      │ search_entity("kinase")           → try again
      │ search_entity("activity")         → try again
      │ search_entity("protein")          → try again
      │ search_entity("GO_")              → try again
      │ ...12 search calls total...
      │
      ▼
Eventually finds GO:0016301 through brute-force
```

**Cost comparison:**
- 12 search calls: ~$0.10 wasted exploration
- 1 llm_query call: ~$0.01 (Haiku)
- **Delegation would save 90% of exploration cost**

---

## Why Delegation Doesn't Happen

### Hypothesis 1: Tool-First Bias ✅

Modern LLMs (especially code-trained ones like Sonnet) default to:
- Direct tool calls over delegation
- Structured function calls over natural language queries
- Brute-force exploration over strategic decomposition

**Evidence**: 0 delegation on ANY query (L1, L2, L3) despite llm_query being available.

### Hypothesis 2: Generic Guidance Insufficient ✅

DSPy's prompt says "USE llm_query FOR SEMANTICS" but:
- Doesn't define what "semantics" means for ontology exploration
- Doesn't show when search fails and delegation helps
- Doesn't provide domain-specific examples

### Hypothesis 3: AGENT_GUIDE.md Not Teaching Delegation ✅

Our 11K char AGENT_GUIDE.md contains:
- Ontology schema information
- Example SPARQL patterns
- URI conventions

But it **doesn't teach**:
- "When search fails 2+ times, use llm_query"
- "For GO/taxon/location concepts, delegate to sub-LLM"
- Examples showing delegation patterns

---

## Solution: Domain-Specific Delegation Guidance

### Option 1: Extend AGENT_GUIDE.md

Add a "Delegation Strategies" section:

```markdown
## When to Use llm_query()

Use `llm_query()` for semantic disambiguation when:
1. **Search returns 0 results** after 2 attempts
2. **Mapping natural language to URIs** (GO terms, taxon IDs, locations)
3. **Understanding relationships** between concepts

### Examples

```python
# Instead of multiple searches for "kinase activity":
go_term = llm_query("What is the GO term for kinase activity? Just answer with GO ID.")
# Returns: "GO:0016301"

# Instead of searching for "human":
taxon_id = llm_query("What is the NCBI taxon ID for Homo sapiens? Just the number.")
# Returns: "9606"

# Instead of searching for "mitochondria":
location = llm_query("What is the UniProt subcellular location ID for mitochondria? Just the ID.")
# Returns: "SL-0173"
```
```

### Option 2: Modify Context Injection

Add delegation guidance to the context_parts before RLM runs:

```python
delegation_guide = """
## Delegation Strategies

When exploring unfamiliar concepts:
1. First check examples in AGENT_GUIDE.md
2. Try search_entity (max 2 attempts per concept)
3. If not found, delegate to llm_query:

   # Get GO term for a concept
   go_id = llm_query("What is the GO term for [concept]? Answer with just the GO ID like GO:0016301")

   # Get taxon ID
   taxon = llm_query("What is the NCBI taxon ID for [organism]? Just the number.")

This saves iterations and reduces cost vs brute-force search.
"""
context_parts.append(delegation_guide)
```

### Option 3: Search-Then-Delegate Wrapper

Create a smart search tool that delegates after failures:

```python
def smart_search(term: str, max_attempts: int = 2) -> str:
    """Search with automatic delegation fallback."""
    for attempt in range(max_attempts):
        results = search_entity(term)
        if results:
            return results

    # Delegate after search fails
    return llm_query(f"""
        I'm searching a biomedical ontology for "{term}" but getting no results.
        What is the standard identifier (GO term, taxon ID, or URI) for this concept?
        Answer with just the identifier.
    """)
```

---

## DSPy Signature Integration

DSPy signatures define the **contract** for RLM execution:

```python
class QueryConstructionSig(dspy.Signature):
    """Construct answer using bounded ontology tools."""

    query: str = dspy.InputField(desc="User question")
    context: str = dspy.InputField(desc="Ontology context and examples")

    thinking: str = dspy.OutputField(desc="Step-by-step reasoning")
    verification: str = dspy.OutputField(desc="Verification checks")
    reflection: str = dspy.OutputField(desc="Self-critique")
    answer: str = dspy.OutputField(desc="Final answer")
    sparql: str = dspy.OutputField(desc="SPARQL query used")
    evidence: dict = dspy.OutputField(desc="Grounding evidence")
```

**How signatures work with RLM:**
1. Signature defines input/output contract
2. RLM module wraps signature with REPL execution loop
3. Each iteration: reasoning → code → output → next iteration
4. Final SUBMIT extracts outputs matching signature fields

**This is the "chainable prediction steps" from TDS article:**
- Query decomposition as signature input
- Sub-LLM responses as intermediate outputs
- Final answer as signature output

---

## Recommended Implementation

### Phase 1: Add Delegation Guidance (Quick Fix)

Modify `run_dspy_rlm()` to inject delegation strategies:

```python
# In context_parts construction:
delegation_guide = """
## Delegation Strategies

When search_entity returns no results after 2 attempts:
- Use llm_query() for semantic disambiguation
- Example: llm_query("What is the GO term for kinase activity? Just the GO ID.")
- This is faster and cheaper than brute-force search
"""
context_parts.append(delegation_guide)
```

### Phase 2: Test Delegation Behavior

Re-run L3 queries with delegation guidance:
- Does llm_query get used?
- Does cost decrease?
- Does quality improve?

### Phase 3: Measure and Iterate

Compare metrics:
- Search calls before/after
- Cost per query
- Convergence rate
- Answer quality

---

## Alignment with Anthropic Patterns

From the three Anthropic articles, RLM should support:

| Pattern | RLM Implementation |
|---------|-------------------|
| **Orchestrator + Subagents** | Parent model + llm_query to sub-LLM |
| **Just-in-Time Retrieval** | llm_query for semantic disambiguation |
| **Response Format Control** | SUBMIT with typed signature outputs |
| **Parallel Execution** | llm_query_batched with ThreadPoolExecutor |
| **Structured Memory** | NamespaceCodeInterpreter + ns dict |

**Current gap**: Orchestrator pattern exists but model doesn't use it.

**Fix**: Explicit delegation guidance in domain context.

---

## Conclusion

DSPy RLM and our implementation **are** designed to work together. The infrastructure is correct:

- ✅ `llm_query()` available
- ✅ Sub-model configured (Haiku)
- ✅ ThreadPoolExecutor for batched queries
- ✅ Typed signature for structured output

The gap is **guidance**, not architecture. Adding domain-specific delegation strategies to AGENT_GUIDE.md or context injection should trigger the intended recursive decomposition behavior.

---

## Experimental Validation

### Delegation Guidance Test (2026-01-28)

**Setup**: Added delegation strategies section to context injection in `dspy_rlm.py`

**Test Query**: L3-1 "Find reviewed human proteins with kinase activity"

**Results**:
| Metric | Before Guidance | After Guidance | Change |
|--------|-----------------|----------------|--------|
| llm_query calls | 0 | 2 | ✅ +2 |
| search_entity calls | 12 | 0 | ✅ -12 |
| Iterations | 9 | 9 | Same |
| Cost | $0.27 | $0.27 | Same |
| Converged | Yes | Yes | Same |

**How llm_query was used**:
1. **Semantic verification**: "Is this protein a kinase? Answer yes/no with brief explanation."
2. **GO term understanding**: "What does GO:0016301 represent?"

**Key insight**: The model found GO:0016301 in AGENT_GUIDE.md examples, then used `llm_query` for verification rather than exploration. This is better than brute-force search but different from the expected "delegation for concept discovery" pattern.

**Interpretation**:
- When context already contains the answer, llm_query is used for verification
- When context doesn't contain the answer, brute-force search may still occur
- Full delegation (asking llm_query for unknown concepts) may require stronger prompting

### Unknown Concept Test (2026-01-28)

**Query**: "Find human proteins involved in apoptosis" (NOT in AGENT_GUIDE.md)

**Expected**: Model delegates to llm_query: "What is the GO term for apoptosis?"

**Actual**: Model used SPARQL text filter instead:
```sparql
FILTER(CONTAINS(LCASE(?goLabel), "apoptosis"))
```

**Results**:
| Metric | Value |
|--------|-------|
| llm_query calls | 0 |
| search_entity calls | 0 |
| SPARQL queries | 3 |
| Iterations | 5 |
| Time | 66.5s |

**Key finding**: Model found a clever workaround using text search in SPARQL rather than semantic delegation. This is actually efficient but means:

1. ✅ **SPARQL-first pattern** - Model leverages structured query capabilities
2. ⚪ **No concept discovery delegation** - Prefers filters over asking llm_query
3. 💡 **Delegation used for verification, not discovery**

**Implication**: The current delegation guidance triggers `llm_query` for:
- Verification ("Is this protein a kinase?")
- Understanding ("What does GO:0016301 represent?")

But NOT for:
- Concept discovery ("What is the GO term for apoptosis?")

This may actually be the right behavior - when you have SPARQL access, text filters are more reliable than LLM hallucination. Delegation is best for semantic verification, not identifier lookup.

---

## Files Referenced

- `/Users/cvardema/uvws/.venv/lib/python3.12/site-packages/dspy/predict/rlm.py`
- `/Users/cvardema/dev/git/LA3D/rlm/rlm_runtime/engine/dspy_rlm.py`
- `/Users/cvardema/dev/git/LA3D/rlm/docs/analysis/reasoning-test-results-partial.md`

**Last Updated**: 2026-01-28
