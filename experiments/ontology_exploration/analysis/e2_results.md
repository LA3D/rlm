# E2 Results: llm_query Synthesis Guidance

**Date**: 2026-01-28
**Hypothesis**: Explicit guidance to use llm_query() will trigger more strategic usage for semantic synthesis
**Result**: ⚠️ **UNEXPECTED** - Guidance improved output quality and reduced cost, but llm_query still not used

---

## Summary

Adding explicit guidance about using `llm_query()` for semantic synthesis had a paradoxical effect:
- ✅ Output became **30% more concise**
- ✅ Cost reduced by **30%** ($0.034 → $0.024)
- ❌ But `llm_query()` still **not called**

The guidance influenced the model's approach to synthesis, even though it didn't use the suggested tool.

---

## Metrics Comparison: E1 vs E2

| Metric | E1 (Baseline) | E2 (With Guidance) | Change |
|--------|---------------|-------------------|--------|
| **Time** | 77.7s | 86.3s | +8.6s (+11%) |
| **LM Calls** | 7 | 7 | No change |
| **Input Tokens** | 4,284 | 3,012 | -1,272 (-30%) |
| **Output Tokens** | 1,428 | 1,004 | -424 (-30%) |
| **Total Tokens** | 5,712 | 4,016 | -1,696 (-30%) |
| **Cost** | $0.0343 | $0.0241 | -$0.0102 (-30%) |
| **Variables Created** | 39 | 35 | -4 |
| **Exploration Notes** | 3,532 chars | 2,175 chars | -1,357 (-38%) |
| **Domain Summary** | 2,181 chars | 1,841 chars | -340 (-16%) |
| **llm_query Detected** | No | No | No change |

---

## What Changed with Guidance

### Guidance Added in E2

```python
## IMPORTANT: Use llm_query() for Semantic Synthesis

After exploring the ontology structure (classes, properties, hierarchies),
use `llm_query()` to synthesize understanding:

# Example showing how to use it
understanding = llm_query(f'''
Based on exploring this ontology, I found:
- {len(classes)} classes
- {len(properties)} properties

Questions:
1. What is this ontology's main purpose and domain?
2. What are the key concepts and how do they relate?
3. What design patterns are used?
''')

llm_query() helps you understand SEMANTICS (what things mean),
not just STRUCTURE (what exists).
```

### Output Quality Differences

**E1 Output Style** (verbose):
```
PROV ONTOLOGY EXPLORATION NOTES

1. BASIC STATISTICS:
   - Total triples: 1,664
   - Total classes: 59 (including owl:Thing)
   - Object Properties: 60
   - Datatype Properties: 9
   - Annotation Properties: 22

2. NAMESPACES USED:
   - Primary: prov (http://www.w3.org/ns/prov#)
   - Standards: rdf, rdfs, owl, xsd
   - Related: Many W3C vocabularies (csvw, dcat, ...)
[continues with detailed numbered sections...]
```

**E2 Output Style** (focused):
```
PROV Ontology Exploration Notes
================================

Structure Overview:
- Total triples: 1664
- Named classes: 51
- Properties: 69

Core Class Architecture:
The ontology is built around three fundamental classes:
1. Activity - Things that occur over time
2. Agent - Things that bear responsibility
3. Entity - Physical, digital, conceptual things

Influence Pattern:
[describes the pattern concisely]
[continues with focused analysis...]
```

**Key Differences:**
- E2 removed unnecessary detail (annotation properties count, full namespace lists)
- E2 used clearer section headers
- E2 focused on semantic insights rather than structural enumeration
- E2 integrated synthesis into narrative flow

---

## Why Didn't llm_query Get Used?

### Hypothesis 1: Self-Sufficient Synthesis
The model can synthesize understanding on its own after exploring. It doesn't NEED llm_query for a 1,664 triple ontology - the whole structure fits in context.

**Evidence**:
- Both E1 and E2 produced accurate domain summaries
- E2's synthesis is actually better quality despite no llm_query
- Model wrote coherent explanations directly in SUBMIT

### Hypothesis 2: Guidance Changed Synthesis Approach, Not Tool Usage
The guidance emphasized "SEMANTICS not STRUCTURE", which influenced the model to:
- Focus on meaning over enumeration
- Be more concise and purposeful
- Synthesize insights inline

But didn't trigger the specific pattern of "explore → llm_query → synthesize".

### Hypothesis 3: Ontology Too Small for Delegation
With only 59 classes and 69 properties, the model can hold all relevant information and synthesize directly. llm_query might only be useful for:
- Larger ontologies (>1000 classes)
- Complex multi-ontology queries
- Specific sub-domain questions

---

## Implications

### 1. Guidance Influences Behavior Even Without Tool Usage

Adding the llm_query example showed the model:
- What good synthesis looks like
- Focus on semantics over structure
- Be concise and purposeful

This improved output quality without requiring the tool.

### 2. Small Ontologies May Not Need Delegation

For PROV (1,664 triples):
- Model can explore and synthesize directly
- llm_query overhead not justified
- Direct synthesis is faster and cheaper

### 3. When Would llm_query Be Useful?

Potential scenarios:
- **Large ontologies**: UniProt (>100K triples) where exploration output needs summarization
- **Multi-step queries**: "Compare two ontologies" where sub-questions need sub-LLM analysis
- **Complex reasoning**: Spatial queries requiring separate analysis of position logic

---

## Output Quality Assessment

### E2 Improvements Over E1

**Conciseness**: -38% length without losing key information

**Structure**:
- Better section organization
- Clearer hierarchy of concepts
- Focused on semantic insights

**Synthesis Quality**:
- Identified "qualification pattern" as key design
- Explained "core triangular pattern" (Entity-Activity-Agent)
- Connected to real-world use cases (trust, reproducibility)

### What's Still Missing

**No explicit chain-of-thought showing**:
- How the model mapped classes to concepts
- Why certain patterns are important
- Connection between structure and domain purpose

This is what llm_query was supposed to help with - but the model synthesized implicitly.

---

## Next Steps for E3

### Test Structured Materialization

E3 should ask for **JSON output** with explicit schema:

```python
{
  "key_classes": [
    {"uri": "...", "label": "...", "why_important": "..."},
  ],
  "key_properties": [
    {"uri": "...", "label": "...", "domain": "...", "range": "...", "role": "..."},
  ],
  "query_patterns": [
    {"pattern_type": "...", "sparql_template": "...", "use_case": "..."},
  ],
  "domain_model": {
    "core_concepts": ["Entity", "Activity", "Agent"],
    "main_relationships": [...],
    "design_patterns": [...]
  }
}
```

**Why JSON?**
- Forces explicit structure
- Easier to validate grounding (check URIs exist)
- Can be loaded directly by query agents
- Separates "what" (structure) from "why" (semantics)

### Questions for E3

1. Will JSON structure force the model to be more explicit?
2. Can we validate URI grounding programmatically?
3. Will structured output be more useful for query agents?
4. Does structured format increase cost?

---

## Conclusion

E2 showed that **guidance about semantic synthesis improves output quality**, even without triggering the suggested tool usage. The model learned to focus on meaning over structure, producing more concise and insightful exploration notes.

However, **llm_query still wasn't used** for either E1 or E2, suggesting:
- Small ontologies don't require delegation
- Model is capable of self-synthesis
- May need different triggering conditions (larger scale, multi-step reasoning)

**For materialized guides**: E2's concise, semantically-focused output is actually closer to what we want. E3 should test structured JSON format to see if explicit schema produces even better artifacts for query agents.

---

**Files**:
- Script: `experiments/ontology_exploration/e2_llm_query_synthesis.py`
- Metrics: `experiments/ontology_exploration/e2_metrics.json`
- Output: `experiments/ontology_exploration/e2_output.txt`
- This analysis: `experiments/ontology_exploration/analysis/e2_results.md`
