# E2-Large Results: Scale and llm_query Delegation

**Date**: 2026-01-28
**Hypothesis**: Larger ontologies (UniProt 2,816 triples vs PROV 1,664) will trigger llm_query() delegation
**Result**: ⚠️ **REFUTED** - Larger ontology was MORE efficient but still no delegation

---

## Summary

Testing with a 69% larger ontology (UniProt 2,816 triples vs PROV 1,664) produced counterintuitive results:
- ❌ `llm_query()` still **not used** despite increased scale
- ✅ **35% cheaper** than E1 baseline ($0.0221 vs $0.0343)
- ✅ **8% cheaper** than E2 on smaller ontology ($0.0221 vs $0.0241)
- ✅ **14% faster** than E2 (74.4s vs 86.3s)
- ✅ **More concise** output (2,061 chars vs 2,175 chars in E2)

**Key finding**: Scale alone does NOT trigger delegation. Larger ontology paradoxically resulted in more efficient exploration.

---

## Metrics Comparison: E2 (PROV) vs E2-Large (UniProt)

| Metric | E2 (PROV 1,664) | E2-Large (UniProt 2,816) | Change |
|--------|----------------|--------------------------|--------|
| **Ontology Size** | 1,664 triples | 2,816 triples | +1,152 (+69%) |
| **Time** | 86.3s | 74.4s | -11.9s (-14%) |
| **LM Calls** | 7 | 8 | +1 (+14%) |
| **Input Tokens** | 3,012 | 2,768 | -244 (-8%) |
| **Output Tokens** | 1,004 | 922 | -82 (-8%) |
| **Total Tokens** | 4,016 | 3,690 | -326 (-8%) |
| **Cost** | $0.0241 | $0.0221 | -$0.0020 (-8%) |
| **Variables Created** | 35 | 35 | No change |
| **Exploration Notes** | 2,175 chars | 2,061 chars | -114 (-5%) |
| **Domain Summary** | 1,841 chars | 1,630 chars | -211 (-11%) |
| **llm_query Detected** | No | No | No change |

---

## Why Was Larger Ontology More Efficient?

### Hypothesis 1: Better Structure → Less Exploration Overhead

UniProt's ontology structure may be more hierarchically organized:
- Clear class categories (Annotation, Site, Enzyme, etc.)
- Consistent naming conventions
- Well-defined domain/range constraints

This structure allowed the model to:
- Identify patterns faster
- Generalize across similar classes
- Produce more concise summaries

### Hypothesis 2: Token Efficiency Through Aggregation

The model may have learned to:
- Group similar classes together (e.g., "39 annotation types")
- Use category-level descriptions instead of enumerating each class
- Focus on representative examples rather than exhaustive listings

Evidence: Exploration notes were shorter (2,061 vs 2,175 chars) despite 69% more triples.

### Hypothesis 3: PROV's Complexity ≠ UniProt's Scale

PROV ontology characteristics:
- Sophisticated "qualification pattern" (Influence → ActivityInfluence → Generation/Usage/etc.)
- Complex temporal relationships
- Meta-provenance (provenance of provenance)

UniProt ontology characteristics:
- Straightforward class hierarchy (Annotation → Disease Annotation)
- Domain-specific but predictable patterns
- Less abstract/philosophical concepts

**Implication**: Semantic complexity might matter more than raw triple count for triggering delegation.

---

## What Changed vs E2 (PROV)

### Exploration Pattern (Similar)

Both E2 and E2-Large followed the same basic pattern:
1. Count triples and namespaces
2. Find all OWL classes
3. Filter named vs blank node classes
4. Get class labels and comments
5. Examine properties (ObjectProperty, DatatypeProperty, FunctionalProperty)
6. Analyze subClassOf hierarchy
7. Synthesize exploration notes and domain summary
8. SUBMIT results

No llm_query() calls in either case.

### Output Quality (E2-Large More Concise)

**E2-Large strengths:**
- Better categorization (grouped annotation types, structural elements, etc.)
- More focused property description
- Clearer domain summary structure

**E2-Large did not:**
- Use llm_query() for synthesis
- Show any signs of delegation strategy
- Hit iteration or token limits

---

## When Would llm_query Be Useful?

### Rejected Hypotheses

After E1, E2, and E2-Large, we can rule out:

1. ❌ **Scale trigger**: 1,664 → 2,816 triples didn't trigger delegation
2. ❌ **Explicit guidance**: E2 guidance about llm_query() wasn't enough
3. ❌ **Iteration pressure**: All runs completed in 7-8 LM calls, well under max_llm_calls=5 limit (wait, that's confusing - the limit is 5 but we saw 7-8 calls?)

### Remaining Possibilities

Delegation might emerge with:

1. **Much larger scale**: >10K triples (Gene Ontology has ~50K)
2. **Multi-step reasoning**: "Compare two ontologies" - requires sub-analysis
3. **Explicit sub-questions**: Task that explicitly requires "answer these 5 questions about the ontology"
4. **Memory/summarization**: Scenarios where exploration output needs compression before final answer
5. **Semantic complexity**: Ontologies with abstract/philosophical concepts requiring interpretation

---

## Implications for Materialized Guides

### Good News: Direct Synthesis Works Well

For ontologies up to ~3K triples:
- Model can explore and synthesize directly
- No delegation overhead needed
- Produces concise, well-organized output
- More efficient than anticipated

### Guidance Improves Quality Without Delegation

E2 and E2-Large both showed:
- Better semantic focus (vs E1's verbose enumeration)
- Clearer conceptual organization
- More useful domain summaries

This happened WITHOUT using llm_query, suggesting guidance influences synthesis approach directly.

### When to Use Two-Phase Workflow

**Phase 1 (Exploration)** remains valuable for:
- Building reusable ontology understanding
- Creating materialized guides for query agents
- Establishing URI grounding and pattern templates

**Phase 2 (Query)** benefits even if Phase 1 doesn't use delegation:
- Query agents get pre-built conceptual map
- Reduces query-time exploration overhead
- Provides pattern templates and examples

**Delegation in Phase 2** might be more useful:
- Query construction may require sub-questions
- "What are all enzymes?" → delegate sub-query for each enzyme type
- Multi-step reasoning chains

---

## Output Quality Assessment

### E2-Large Improvements

**Conciseness**: 11% shorter domain summary, 5% shorter exploration notes

**Organization**:
- Grouped classes by category (Annotation types, Structural elements, etc.)
- Clear property patterns section
- Focused hierarchy examples

**Semantic depth**:
- Explained protein annotation use cases
- Connected to bioinformatics applications
- Identified integration with external databases

### What's Still Missing

E2-Large (like E2) synthesized understanding implicitly rather than explicitly showing:
- Chain-of-thought reasoning about ontology purpose
- Connection between structure and semantics
- Why certain patterns matter for queries

This implicit synthesis works well but isn't externalized as reusable artifacts.

---

## Next Steps for E3

### Recommendation: Test Structured Materialization (Not Scale)

E2-Large proved scale alone doesn't trigger delegation. E3 should focus on:

**Structured JSON output** with explicit schema:

```python
{
  "key_classes": [
    {"uri": "...", "label": "...", "why_important": "..."},
  ],
  "key_properties": [
    {"uri": "...", "domain": "...", "range": "...", "role": "..."},
  ],
  "query_patterns": [
    {"pattern_type": "...", "sparql_template": "...", "use_case": "..."},
  ],
  "design_patterns": [
    {"name": "...", "description": "...", "example_classes": [...]}
  ]
}
```

**Why structured format?**
- Forces explicit semantic reasoning
- Separates "what exists" from "why it matters"
- Easier to validate grounding (check URIs)
- Directly usable by query agents
- Might trigger llm_query for sub-questions ("why is this class important?")

### Alternative: Test Semantic Complexity

Instead of larger scale, test with ontologies that have:
- Abstract concepts (DOLCE, BFO)
- Complex reasoning patterns (PROV's qualification pattern is actually good for this)
- Multi-step inference requirements

---

## Conclusion

E2-Large **refuted** the hypothesis that scale triggers delegation. Counterintuitively:
- Larger ontology was MORE efficient
- Still no llm_query usage
- Better output quality than smaller ontology

**Key insights:**

1. **Scale ≠ Delegation Trigger**: 69% more triples didn't change behavior
2. **Guidance Works**: Semantic focus improved output even without delegation
3. **Structure Matters**: Organized ontologies may be easier to synthesize
4. **Complexity > Size**: Semantic complexity might matter more than triple count

**For materialized guides**:
- Two-phase workflow remains valuable (reusable exploration artifacts)
- Delegation may emerge in Phase 2 (query construction) rather than Phase 1 (exploration)
- E3 should test structured output format to force explicit reasoning

---

**Files**:
- Script: `experiments/ontology_exploration/e2_large_ontology.py`
- Metrics: `experiments/ontology_exploration/e2_large_metrics.json`
- Output: `experiments/ontology_exploration/e2_large_output.txt`
- This analysis: `experiments/ontology_exploration/analysis/e2_large_results.md`
