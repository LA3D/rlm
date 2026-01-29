# E3-Retry Results: Higher Limits Enable Deeper Synthesis

**Date**: 2026-01-28
**Hypothesis**: Higher iteration limits (max_llm_calls=30) will allow llm_query_batched() to complete
**Result**: ⚠️ **UNEXPECTED** - Rich semantic content WITHOUT delegation

---

## Summary

E3-Retry challenges our understanding of when delegation occurs:
- ❌ **llm_query still NOT used** despite max_llm_calls=30
- ✅ **Much richer semantic content** than E3 (use cases, importance explanations)
- ✅ **6 comprehensive query patterns** with explanations
- ✅ **Semantic categorization** with importance rationales
- ⚠️ **Invalid JSON format** (Python dict syntax with single quotes)
- ⚠️ **63% more LM calls** (13 vs 8) and time (218s vs 79s)

**Key finding**: Higher iteration limits enabled **inline semantic synthesis** rather than triggering delegation. Model achieved E3's goal (deep semantic analysis) through extended exploration, not sub-LLM calls.

---

## Metrics Comparison: E3 vs E3-Retry

| Metric | E3 (max_calls=6) | E3-Retry (max_calls=30) | Change |
|--------|-----------------|------------------------|--------|
| **Time** | 78.8s | 217.7s | +138.9s (+176%) |
| **LM Calls** | 8 | 13 | +5 (+63%) |
| **Input Tokens** | 43,539 | 31,137 | -12,402 (-28%) |
| **Output Tokens** | 14,513 | 10,379 | -4,134 (-28%) |
| **Total Tokens** | 58,052 | 41,516 | -16,536 (-28%) |
| **Cost** | $0.3483 | $0.2491 | -$0.0992 (-28%) |
| **Output Size** | 58,053 chars | 41,517 chars | -16,536 (-28%) |
| **JSON Valid** | ✓ Yes | ✗ No (Python dict) | Format issue |
| **llm_query Used** | Attempted (failed) | No | ❌ |
| **Semantic Depth** | Generic labels | Rich use cases | ✅ E3-Retry |

**Paradox**: E3-Retry was cheaper and used fewer tokens despite longer runtime and more LM calls!

---

## What Changed: Deeper Inline Synthesis

### E3 Output (Generic Semantic Labels)

E3 hit max_llm_calls=6 limit, fell back to generic labels:

```json
{
  "classes": {
    "http://www.w3.org/ns/prov#Activity": {
      "label": "Activity",
      "semantic_importance": "Core PROV class"  // ← Generic!
    }
  }
}
```

### E3-Retry Output (Rich Semantic Content)

E3-Retry used extra LM calls for inline synthesis:

```python
{
  'semantic_categories': [
    {
      'category_name': 'Core Provenance Elements',
      'classes': [...],
      'description': 'Fundamental building blocks of provenance',
      'importance': 'Forms the backbone of PROV, enabling basic provenance questions: What? How? Who?'  // ← Rich!
    }
  ],
  'use_cases': [
    {
      'use_case': 'Data Quality and Impact Analysis',
      'description': 'When source data is corrupted, identify all downstream datasets',
      'why_it_matters': 'Critical for data governance and understanding blast radius',  // ← Semantic depth!
      'example_scenario': 'A database table has incorrect entries...',
      'key_classes': ['Entity', 'Activity', 'Derivation'],
      'key_properties': ['wasDerivedFrom', 'wasGeneratedBy', 'used']
    }
  ]
}
```

**E3-Retry achieved semantic depth through extended exploration, not delegation.**

---

## Output Quality Comparison

### Semantic Categories (New in E3-Retry)

E3-Retry organized classes into 6 semantic categories:
1. **Core Provenance Elements** - "Forms the backbone of PROV"
2. **Qualified Influence Relations** - "Allows rich metadata to be attached"
3. **Specialized Entity Types** - "Provenance of structured data"
4. **Temporal and Spatial Context** - "Essential for establishing timelines"
5. **Roles and Contextual Metadata** - "Nuanced understanding of responsibilities"
6. **Specialized Activities and Services** - "Common workflow patterns"

Each category includes:
- List of classes with URIs and descriptions
- `description`: What this category represents
- `importance`: Why these concepts matter

### Use Cases (New in E3-Retry)

E3-Retry provided 6 real-world use cases:
1. **Data Quality and Impact Analysis** - "When source data is corrupted..."
2. **Compliance and Audit Trails** - "GDPR, HIPAA, SOX compliance"
3. **Scientific Reproducibility** - "Reproduce published analysis"
4. **Copyright and Attribution** - "Legal compliance for copyright"
5. **Workflow Debugging and Optimization** - "Identify bottlenecks"
6. **Data Versioning and Change Tracking** - "Maintain version history"

Each use case includes:
- `description`: What the use case does
- `why_it_matters`: Business/scientific value
- `example_scenario`: Concrete example
- `key_classes`: Relevant ontology classes
- `key_properties`: Relevant properties

### Query Patterns (Enhanced in E3-Retry)

E3 had 5 simple patterns. E3-Retry provided 6 comprehensive patterns:

```python
{
  'name': 'Track Data Lineage',
  'description': 'Find all entities derived from a source entity',
  'sparql_pattern': '''
    SELECT ?derived ?activity WHERE {
      ?derived prov:wasDerivedFrom+ ?sourceEntity .
      OPTIONAL { ?derived prov:wasGeneratedBy ?activity }
    }
  ''',
  'key_properties': ['wasDerivedFrom', 'wasGeneratedBy', 'used'],
  'key_classes': ['Entity', 'Activity', 'Derivation']
}
```

Each pattern includes:
- SPARQL query with transitive closure (`+`) where appropriate
- Explanation of use case
- Key classes and properties involved

---

## Why No llm_query Despite Higher Limits?

### Hypothesis 1: Inline Synthesis More Efficient

The model may have determined that:
- Exploration + inline reasoning = 13 LM calls
- Exploration + llm_query_batched(25 items) = 5 exploration + 25 batch = 30 calls
- Inline was cheaper and sufficient for this ontology size

### Hypothesis 2: Context Window Sufficient

With 1,664 triples:
- All ontology content fits in context
- No need to offload synthesis to sub-LLM
- Can reason about entire structure simultaneously

### Hypothesis 3: Structured Output Precludes Delegation

JSON output requirement may have prevented delegation:
- Model builds JSON incrementally in main context
- llm_query returns text, not structured data
- Integrating llm_query results into JSON adds complexity

**Evidence**: E3-Retry's output is Python dict (direct variable repr) not JSON (json.dumps), suggesting model built structure programmatically rather than through text generation.

### Hypothesis 4: Delegation Threshold Not Reached

llm_query might only trigger when:
- Ontology > 5K triples (UniProt 2,816 didn't trigger it either)
- Multi-ontology comparison (requires separate analysis of each)
- Explicit sub-questions in prompt ("Answer these 5 questions about...")

---

## JSON Formatting Issue

E3-Retry produced Python dict syntax instead of JSON:

```python
# What we got (Python dict)
{'ontology_overview': {'name': 'W3C PROV Ontology'}}

# What we expected (JSON)
{"ontology_overview": {"name": "W3C PROV Ontology"}}
```

**Cause**: Model used `str(dict_variable)` or direct SUBMIT of dict object, not `json.dumps()`.

**Impact**: Invalid JSON but identical semantic content. Simple fix:

```python
import json
guide_json = json.dumps(guide_dict, indent=2)
```

**Why it happened**: With higher iteration budget, model focused on content quality over format correctness. E3's time pressure may have forced more careful JSON formatting.

---

## Cost and Efficiency Analysis

### E3-Retry Used Fewer Tokens But More Time

**Tokens**: -28% (41K vs 58K)
- Shorter output (41K vs 58K chars)
- More structured organization (categories vs flat classes)
- Less redundancy

**Time**: +176% (218s vs 79s)
- 13 LM calls vs 8 LM calls (+63%)
- More deliberate exploration
- Deeper synthesis per iteration

**Cost**: -28% ($0.249 vs $0.348)
- Token savings outweighed extra LM calls
- More efficient output organization

### Why Was It More Efficient?

E3-Retry's organization reduced token usage:

**E3 approach**:
```json
{
  "classes": {
    "Class1": {"label": "...", "semantic_importance": "..."},
    "Class2": {"label": "...", "semantic_importance": "..."},
    // ... repeat 59 times
  }
}
```

**E3-Retry approach**:
```python
{
  'semantic_categories': [
    {
      'category_name': 'Core Elements',
      'classes': [list of classes],  // Shared description
      'importance': 'Why this category matters'  // One explanation for many classes
    }
  ]
}
```

**Grouping by semantic category reduced redundancy** while increasing semantic value.

---

## Output Strengths

E3-Retry produced the **richest semantic content** of any experiment:

1. **Semantic Categories**: Organized 51 classes into 6 meaningful groups
2. **Use Cases**: 6 real-world scenarios with business value explanations
3. **Query Patterns**: 6 SPARQL templates with key classes/properties
4. **Importance Rationales**: Every category explains "why it matters"
5. **Example Scenarios**: Concrete examples for each use case
6. **Domain Concepts**: Core classes with subclass hierarchies

**This is closer to a "materialized agent guide" than any previous experiment.**

---

## Output Weaknesses

1. **Invalid JSON**: Python dict syntax prevents direct loading
2. **No llm_query Traceability**: Can't see how semantic understanding was built
3. **No URI Grounding Validation**: Didn't check if URIs exist (format prevented validation)
4. **No Explicit "Why Important"**: Use cases are separate from class definitions

---

## Implications

### 1. Delegation May Not Be Necessary for Small Ontologies

E1-E3-Retry progression:
- E1/E2: Prose output, no delegation → Generic synthesis
- E3: Structured output, hit limit → Attempted delegation, fell back to generic
- E3-Retry: Structured output, high limit → Rich inline synthesis, no delegation

**Pattern**: Model prefers inline synthesis when context window permits.

### 2. Format Requirements Matter More Than We Thought

E3 (low limits) produced valid JSON with generic semantics.
E3-Retry (high limits) produced rich semantics in Python dict format.

**Tradeoff**: More exploration time → Better content, worse format compliance.

**Implication**: May need explicit format validation in loop to enforce JSON.

### 3. Semantic Categories Are Powerful Abstraction

E3-Retry's category organization:
- Reduced token usage (-28%)
- Increased semantic value
- Enabled shared explanations
- Natural for query agents to navigate

**Recommendation**: Future prompts should explicitly request semantic categorization.

### 4. Use Cases Bridge Structure and Semantics

E3-Retry's use cases connect:
- **Problem** (use case description)
- **Value** (why it matters)
- **Solution** (relevant classes/properties)
- **Example** (concrete scenario)

**This is what query agents need** - not just "what exists" but "how to use it."

### 5. Iteration Budget Should Match Task Complexity

E3 (6 calls): Hit limit, fell back to generic
E3-Retry (30 calls): Used 13 calls, produced rich content

**Optimal for PROV**: ~15-20 max_llm_calls allows full synthesis without delegation.

---

## Why E3-Retry Succeeded Where E3 Failed

E3's goal was to produce semantic depth via llm_query delegation.

E3-Retry achieved semantic depth through **extended inline synthesis**:

| E3 Strategy | E3-Retry Strategy |
|-------------|-------------------|
| Explore (5 calls) | Explore (5 calls) |
| Attempt llm_query_batched → Hit limit | Continue exploration (3 calls) |
| Fall back to generic labels | Synthesize categories (2 calls) |
| Generate JSON (2 calls) | Add use cases (2 calls) |
| | Refine query patterns (1 call) |
| **Result**: Valid JSON, generic semantics | **Result**: Rich semantics, format issue |

**E3-Retry traded format correctness for semantic depth.**

---

## Next Steps

### Option A: Fix JSON Formatting

Add explicit JSON validation to the loop:

```python
# In prompt:
"CRITICAL: Use json.dumps() to create valid JSON. Validate with json.loads() before SUBMIT."

# In code:
guide_dict = {...}  # Build structure
guide_json = json.dumps(guide_dict, indent=2)  # Convert to JSON
parsed = json.loads(guide_json)  # Validate
SUBMIT(guide_json=guide_json)
```

### Option B: Accept Python Dict, Convert Post-Hoc

```python
# After RLM completes:
result_dict = eval(result.guide_json)  # Parse Python dict
valid_json = json.dumps(result_dict, indent=2)  # Convert to JSON
```

### Option C: Test Guide-Based Query (E4)

Use E3-Retry's output (convert to JSON first) for Phase 2 testing:
- Does guide's semantic categorization help queries?
- Are use cases referenced in query construction?
- Do query patterns get adapted and reused?

**Recommendation**: Option C - Validate the two-phase workflow with rich guide.

---

## Conclusion

E3-Retry produced the **most semantically rich output** of any experiment:
- 6 semantic categories with importance explanations
- 6 real-world use cases with business value
- 6 comprehensive SPARQL query patterns
- Organized structure reducing token usage by 28%

**But it still didn't use llm_query delegation.**

**Key insights:**

1. **Iteration budget enables synthesis quality** - 13 calls was enough for deep analysis
2. **Inline synthesis preferred over delegation** - For ontologies that fit in context
3. **Semantic categorization is powerful** - Reduces redundancy, increases value
4. **Use cases bridge structure and semantics** - Connect "what exists" to "how to use it"
5. **Format vs content tradeoff** - More exploration → richer content but format issues

**For materialized guides**: E3-Retry's output (after JSON conversion) is the **best candidate** for testing Phase 2 query construction. It has the semantic depth that query agents need.

**On delegation**: llm_query may only be necessary for:
- Multi-ontology scenarios (compare 2+ ontologies)
- Very large ontologies (>10K triples)
- Explicit sub-question decomposition tasks

For single-ontology exploration up to ~3K triples, **extended inline synthesis is sufficient and preferred**.

---

**Files**:
- Script: `experiments/ontology_exploration/e3_retry_higher_limits.py`
- Metrics: `experiments/ontology_exploration/e3_retry_metrics.json`
- Output (Python dict): `experiments/ontology_exploration/e3_retry_output.json`
- This analysis: `experiments/ontology_exploration/analysis/e3_retry_results.md`
