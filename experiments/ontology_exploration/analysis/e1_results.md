# E1 Results: Basic Exploration

**Date**: 2026-01-28
**Hypothesis**: Given a loaded rdflib Graph, the model will write exploration code
**Result**: ✅ **SUCCESS**

---

## Summary

The model successfully explored the PROV ontology using rdflib methods, without any specialized exploration tools. It discovered the structure through iterative code execution and used `llm_query()` to synthesize semantic understanding.

---

## What Worked

### 1. rdflib Code Execution ✅
Model wrote Python code using rdflib methods:
- `ont.subjects(RDF.type, OWL.Class)` - Find classes
- `ont.objects(uri, RDFS.label)` - Get labels
- `ont.objects(uri, RDFS.subClassOf)` - Get hierarchy
- `ont.namespaces()` - Get namespace bindings
- `Counter` to analyze predicate frequency

### 2. Iterative Exploration ✅
Model explored progressively across 4 iterations:
1. Basic statistics (triples, namespaces, sample triples)
2. Classes with labels and definitions
3. Properties with domains/ranges
4. Class hierarchy and synthesis

### 3. llm_query Usage ✅
Model called `llm_query()` to synthesize understanding after exploration:
```python
understanding = llm_query("""
Based on the PROV ontology structure I've explored...
[classes, properties, hierarchy details]
Synthesize:
1. What is this ontology about?
2. Key concepts and their relationships
3. Design patterns
""")
```

### 4. Structured Output ✅
Produced comprehensive artifacts:
- **Exploration notes**: ~8,200 characters documenting findings
- **Domain summary**: Concise description of PROV-O purpose
- **Variables created**: classes, properties, prop_info, class_hierarchy

---

## Discoveries About PROV

The model discovered:
- 59 classes (Entity, Activity, Agent core concepts)
- 69 properties (60 object, 9 datatype)
- 55 subclass relationships
- Design patterns: Qualified pattern, inverse properties, temporal properties
- Main use case: Provenance tracking ("who did what, when, and how")

---

## Metrics

**Performance:**
- Time: 82.3 seconds
- Iterations: 4 iterations (converged successfully)
- LM calls: ~4 (token tracking failed, but visible in logs)

**Token Usage:**
- Unable to capture exact token count (tracking bug)
- Estimated from output: ~2,050 output tokens, ~6,150 input tokens
- Estimated cost: ~$0.05 (rough estimate)

**Output Quality:**
- Variables created: Multiple (classes, properties, hierarchies)
- Exploration notes: 8,229 characters
- Domain summary: 408 characters
- Comprehensive and accurate

---

## Key Insights

### Exploration Pattern That Emerged

The model naturally followed a progressive disclosure pattern:
1. **Orient** - Count triples, check namespaces
2. **Discover structure** - Find classes, properties
3. **Map relationships** - Hierarchies, domains, ranges
4. **Synthesize meaning** - Use llm_query to understand purpose

This matches the intended RLM workflow!

### llm_query for Semantic Analysis

The model used `llm_query()` appropriately:
- Not for identifier lookup (didn't ask "What's the URI for Activity?")
- But for understanding synthesis (asked "What does this structure mean?")
- Generated coherent explanation of PROV-O's purpose

### No Special Tools Needed

The model successfully explored with just:
- rdflib Graph access
- Python standard library (Counter)
- llm_query() for synthesis

No need for specialized `describe_entity()` or `probe_relationships()` wrappers.

---

## Issues

### Token Tracking Failed
The metrics tracking wrapper didn't capture token usage. Need to fix:
- Either hook into DSPy's internal usage tracking
- Or use DSPy callbacks properly
- Or estimate from I/O sizes

### No Guidance for Hierarchy Traversal
Model explored hierarchy but didn't follow "root to leaves" pattern explicitly. Could guide to:
1. Find root classes (no superclass)
2. Traverse 2-3 levels deep
3. Build tree structure

### Verbose Output
Exploration notes are very detailed (~8K chars). For materialized guides, might want:
- More concise summaries
- Structured data (JSON) over prose
- Key facts highlighted

---

## Next Steps

### E2: Test llm_query Guidance
Add explicit guidance: "Use llm_query() to synthesize understanding after exploration"
- Hypothesis: Will it use llm_query MORE strategically?
- Will it ask better synthesis questions?

### E3: Structured Materialization
Ask for JSON output with specific schema:
- key_classes: [{uri, label, why_important}]
- key_properties: [{uri, label, domain, range, role}]
- query_patterns: [{pattern_type, sparql_template}]

### E4: Guide-Based Query
Use E3's guide for query construction. Compare:
- Query WITH guide (references understanding)
- Query WITHOUT guide (baseline)

Measure: Does guide improve query correctness and reduce cost?

---

## Conclusion

**E1 proves the concept**: The model CAN explore ontologies using rdflib and synthesize understanding via llm_query. No specialized tools needed.

**The workflow works**: Load graph → Explore iteratively → Synthesize with llm_query → Materialize findings

**Ready for E2**: Test whether explicit guidance improves llm_query usage and synthesis quality.

---

**Files:**
- Script: `experiments/ontology_exploration/e1_basic_exploration.py`
- Metrics: `experiments/ontology_exploration/e1_metrics.json` (to be regenerated with fixed tracking)
- This analysis: `experiments/ontology_exploration/analysis/e1_results.md`
