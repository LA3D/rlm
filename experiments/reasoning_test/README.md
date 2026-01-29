# Reasoning-Intensive Query Experiment

**Created**: 2026-01-28
**Status**: Planned
**Purpose**: Test if L3-L4 reasoning complexity triggers delegation in RLM

---

## Overview

Previous tests on L1-L2 queries showed **no delegation** - the RLM solved queries directly using bounded tools without calling `llm_query()`. This experiment tests whether more complex queries (multi-hop reasoning, spatial constraints, multi-entity coordination) trigger strategic delegation.

## Research Questions

1. **Do L3-L4 queries trigger delegation?** - Does `llm_query()` get used for semantic disambiguation, validation, or filtering?
2. **What reasoning types cause delegation?** - Spatial reasoning? Multi-hop? Aggregation?
3. **How does cost scale with complexity?** - Does L3-L4 remain cheaper than ReAct baseline ($0.27)?
4. **Is delegation necessary for quality?** - Or can tools + AGENT_GUIDE.md handle complexity directly?

---

## Background

**Previous results** (see `docs/analysis/rlm-behavior-l1-l2-queries.md`):
- L1-L2 queries: 0 delegation attempts, $0.11-0.13 cost, 5-7 iterations
- Tool-first pattern: search → SPARQL queries → submit
- AGENT_GUIDE.md provides sufficient scaffolding for simple queries

**Hypothesis**: L3-L4 complexity may trigger delegation for:
- Semantic disambiguation ("What GO term is kinase?")
- Spatial reasoning ("Does variant overlap active site?")
- Result filtering ("Which properties are most important?")

---

## Test Queries

### L3-1: Multi-Entity Coordination

**Query**: "Find reviewed human proteins with kinase activity"

**Complexity**: Must coordinate 4 concepts:
- Human (taxon:9606)
- Reviewed status (up:reviewed true)
- Kinase activity (GO:0016301)
- GO term hierarchy (classifiedWith + subclasses)

**Reference SPARQL** (from UniProt examples #23):
```sparql
PREFIX GO: <http://purl.obolibrary.org/obo/GO_>
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

SELECT ?protein
WHERE {
    ?protein a up:Protein ;
             up:reviewed true ;
             up:organism taxon:9606 ;
             up:classifiedWith|(up:classifiedWith/rdfs:subClassOf) GO:0016301 .
}
```

**Reasoning needed**:
- Map "kinase activity" → GO:0016301 (semantic knowledge)
- Understand "reviewed" → Swiss-Prot (domain knowledge)
- Handle GO term hierarchy (property path)

**Possible delegation**:
```python
# Model might ask:
llm_query("What is the GO term for kinase activity?")
llm_query("How do I query for reviewed proteins?")
```

---

### L3-2: Multi-Hop Annotation

**Query**: "What diseases involve enzymes located in mitochondria?"

**Complexity**: Must navigate 2 annotation paths:
1. Protein → Disease_Annotation → disease
2. Protein → Subcellular_Location_Annotation → location → mitochondrion

**Reference SPARQL** (from UniProt examples #63):
```sparql
SELECT DISTINCT ?disease
WHERE {
    ?protein a up:Protein ;
             up:organism taxon:9606 ;
             up:annotation ?disease_annotation, ?subcellularLocation .

    # Must be enzyme (two ways to check)
    { ?protein up:enzyme [] }
    UNION
    { ?protein up:annotation/a up:Catalytic_Activity_Annotation }

    # Has disease annotation
    ?disease_annotation a up:Disease_Annotation ;
                       up:disease ?disease .

    # Located in mitochondrion
    ?subcellularLocation a up:Subcellular_Location_Annotation ;
                        up:locatedIn ?location .
    ?location up:cellularComponent ?component .
    ?component up:partOf* <http://purl.uniprot.org/locations/173> .
}
```

**Reasoning needed**:
- Map "enzyme" → two possible representations
- Map "mitochondria" → location URI 173
- Understand transitive partOf* hierarchy
- Coordinate two annotation types on same protein

**Possible delegation**:
```python
llm_query("What URI represents mitochondria in UniProt?")
llm_query("How do I check if a protein is an enzyme?")
```

---

### L4-1: Spatial Reasoning

**Query**: "Find diseases caused by natural variants in enzyme active sites"

**Complexity**: Must check spatial overlap:
- Protein → Natural_Variant_Annotation (with begin/end positions)
- Protein → Active_Site_Annotation (with position)
- Protein → Disease_Annotation
- Check: variant range overlaps active site position

**Reference SPARQL** (from UniProt examples #64):
```sparql
SELECT DISTINCT ?disease
WHERE {
    ?protein a up:Protein ;
             up:organism taxon:9606 ;
             up:annotation ?disease_annotation, ?active_site_annotation, ?natural_variant_annotation .

    # Must be enzyme
    { ?protein up:enzyme [] }
    UNION
    { ?protein up:annotation/a up:Catalytic_Activity_Annotation }

    # Disease annotation
    ?disease_annotation a up:Disease_Annotation ;
                       up:disease ?disease .

    # Active site position
    ?active_site_annotation a up:Active_Site_Annotation ;
                           up:range ?active_site_range .
    ?active_site_range faldo:begin ?active_site_begin .
    ?active_site_begin faldo:position ?active_site_position ;
                      faldo:reference ?sequence .

    # Natural variant position (related to disease)
    ?natural_variant_annotation a up:Natural_Variant_Annotation ;
                               up:range ?natural_variant_range ;
                               skos:related ?disease .
    ?natural_variant_range faldo:begin ?natural_variant_begin ;
                          faldo:end ?natural_variant_end .
    ?natural_variant_begin faldo:position ?natural_variant_begin_position .
    ?natural_variant_end faldo:position ?natural_variant_end_position ;
                        faldo:reference ?sequence .

    # Check overlap
    FILTER(?natural_variant_begin_position <= ?active_site_position
           && ?active_site_position <= ?natural_variant_end_position)
}
```

**Reasoning needed**:
- Understand sequence position representation (FALDO ontology)
- Understand three different annotation types
- Perform spatial reasoning (range overlap)
- Understand disease linkage (skos:related)

**Possible delegation**:
```python
llm_query("How do I check if a sequence range overlaps a position in SPARQL?")
llm_query("What annotation types represent active sites vs natural variants?")
llm_query("How are natural variants linked to diseases?")
```

---

### L3-3: Cross-Organism Comparison

**Query**: "How do human proteins differ from mouse proteins in terms of annotation types?"

**Complexity**: Must aggregate and compare:
- Query two organisms (taxon:9606, taxon:10090)
- Group by annotation types
- Compare distributions
- Synthesize differences

**Reasoning needed**:
- Understand aggregation (GROUP BY, COUNT)
- Compare two result sets
- Identify meaningful differences
- Synthesize narrative answer

**Possible delegation**:
```python
llm_query("Which annotation types are most important to compare?")
llm_query("Summarize these differences in 2-3 sentences")
```

---

### L4-2: Multi-Constraint Integration

**Query**: "Find human proteins that have both disease associations and drug targets, and are membrane-bound"

**Complexity**: Must coordinate 3+ constraints:
- Disease_Annotation
- Drug target annotation (need to discover representation)
- Subcellular_Location_Annotation (membrane)
- All on same protein

**Reasoning needed**:
- Discover how drug targets are represented
- Map "membrane-bound" to location URIs
- Ensure all conditions on same entity
- Handle optional annotations gracefully

**Possible delegation**:
```python
llm_query("How are drug targets represented in UniProt?")
llm_query("What location URIs represent membrane-bound proteins?")
```

---

## Expected Outcomes

### Scenario A: Delegation Emerges ✅

**If llm_query is used:**
- Queries where delegation occurs: L3-2, L4-1, L4-2
- Cost increase: 20-40% vs L1-L2 (still cheaper than ReAct)
- Iterations increase: 8-12 (within budget)
- Quality improvement: More accurate URI mapping, better query construction

**What this tells us**:
- RLM recognizes when semantic disambiguation helps
- Delegation ROI is positive (cost worth the quality)
- L3+ requires strategic reasoning beyond tools

**Next steps**:
- Document delegation patterns
- Tune when to use delegation
- Optimize delegation prompts

---

### Scenario B: No Delegation (Tool-First Continues) ⚪

**If llm_query is NOT used:**
- Model constructs complex queries directly
- AGENT_GUIDE.md provides sufficient scaffolding
- Cost remains low ($0.15-0.20 per query)
- Answers are comprehensive without delegation

**What this tells us**:
- Tool-first pattern scales to L3-L4
- AGENT_GUIDE.md is highly effective
- Explicit RDF semantics don't need disambiguation
- Model is highly capable at direct construction

**Next steps**:
- Accept tool-first as optimal for RDF domain
- Expand AGENT_GUIDE.md with more patterns
- Focus on pattern library vs delegation

---

### Scenario C: Mixed Results 🔀

**If delegation is selective**:
- Some queries use delegation (L4-1 spatial), others don't (L3-1 multi-entity)
- Delegation correlates with specific reasoning types
- Cost variance by query type

**What this tells us**:
- Delegation emerges for specific challenges:
  - Spatial reasoning (position overlaps)
  - Semantic disambiguation (GO terms, locations)
  - Result filtering (many options to choose from)
- Not needed for:
  - Multi-entity coordination (SPARQL handles joins)
  - Annotation type discovery (AGENT_GUIDE.md sufficient)

**Next steps**:
- Identify delegation trigger patterns
- Document when to use delegation
- Create decision tree for delegation

---

## Success Metrics

### Primary Metric: Delegation Usage

**Target**: At least 2/5 queries use llm_query

**Measurement**: Count llm_query attempts in trajectory logs

**Interpretation**:
- 0/5: Tool-first is universal
- 1-2/5: Delegation for specific challenges
- 3+/5: Delegation is standard for complex queries

---

### Secondary Metrics

**Cost Efficiency**:
- Target: < $0.25 per query (ReAct baseline)
- Acceptable: $0.15-0.20 (vs L1-L2's $0.12)
- Warning: > $0.25 (need optimization)

**Convergence Rate**:
- Target: 100% convergence within 15 iterations
- Acceptable: 80%+ (some queries are hard)
- Warning: < 80% (budget too low)

**Answer Quality** (manual review):
- Are SPARQL queries valid?
- Do answers address the question?
- Is evidence grounded?

---

## Comparison to Previous Tests

| Test | Complexity | Delegation | Cost | Iterations |
|------|-----------|-----------|------|-----------|
| **L1** (Protein class) | Entity discovery | 0 attempts | $0.13 | 7 |
| **L2** (Property relationships) | Two-entity queries | 0 attempts | $0.11 | 6 |
| **L3-L4** (This test) | Multi-hop + spatial | ??? | ??? | ??? |

**Hypothesis**: L3-L4 complexity will trigger delegation where L1-L2 did not.

---

## Running the Experiment

### Basic Usage

```bash
source ~/uvws/.venv/bin/activate
python experiments/reasoning_test/run_reasoning_test.py
```

### Configuration

- **Ontology**: `ontology/uniprot/core.ttl`
- **AGENT_GUIDE.md**: 11K chars with prefixes, classes, properties, patterns
- **Budget**: 15 iterations, 30 LLM calls (increased from L1-L2's 8/16)
- **Model**: Sonnet 4.5 (main) + Haiku (sub-LLM if delegated)

### Output

Results saved to:
- **Logs**: `experiments/reasoning_test/*.jsonl` (trajectory logs)
- **Results**: `experiments/reasoning_test/results_YYYYMMDD_HHMMSS.json` (summary)

### Analysis Tools

```bash
# Analyze specific trajectory
python experiments/reasoning_test/analyze_trajectory.py experiments/reasoning_test/l3-1_test.jsonl

# Shows:
# - Context analysis (AGENT_GUIDE.md loaded?)
# - Tool call sequence
# - Token usage per iteration
# - Delegation detection
# - Pattern identification
```

---

## What We'll Learn

### About Delegation

**When does it emerge?**
- Semantic ambiguity (GO terms, locations)?
- Spatial reasoning (position overlaps)?
- Result filtering (many options)?
- Or never (tool-first is sufficient)?

**How is it used?**
- Disambiguation before query construction?
- Validation after query construction?
- Result filtering after query execution?
- Answer synthesis before SUBMIT?

**What's the ROI?**
- Cost increase: X% more expensive
- Quality increase: Better query construction?
- Time increase: More iterations needed?

---

### About RLM Architecture

**Is tool-first pattern universal?**
- If no delegation: Yes, tools handle all complexity
- If delegation: No, some reasoning needs sub-LLM

**What's the role of AGENT_GUIDE.md?**
- If no delegation: Critical scaffolding (prevents delegation need)
- If delegation: Helpful but insufficient for complex reasoning

**What's the complexity ceiling?**
- L1-L2: Tool-first works
- L3-L4: This test determines boundary
- L5+: TBD (aggregation, multi-ontology)

---

### About Production Readiness

**Can we deploy L3-L4?**
- If cost < $0.25: Yes, cost-effective
- If convergence > 80%: Yes, reliable
- If delegation emerges: Document patterns

**What's the optimal configuration?**
- Iteration budget: 12? 15? 20?
- LLM call budget: 2x iterations? More?
- When to use delegation: Always? Never? Conditional?

---

## Next Steps After Test

### If Delegation Emerges

1. **Document delegation patterns** - When/why does model delegate?
2. **Measure delegation ROI** - Compare cost vs quality
3. **Tune delegation prompts** - Can we make delegation more effective?
4. **Test L5+ complexity** - Where does delegation ceiling hit?

### If No Delegation

1. **Accept tool-first pattern** - It's optimal for RDF domain
2. **Expand pattern library** - Add more examples to AGENT_GUIDE.md
3. **Test other ontologies** - Does pattern hold across domains?
4. **Focus on optimization** - Speed up direct approach

---

**Related Documents**:
- Test script: `test_uniprot_reasoning.py`
- Previous analysis: `docs/analysis/rlm-system-behavior-summary.md`
- UniProt examples: `ontology/uniprot/examples/UniProt/*.ttl`
- AGENT_GUIDE.md: `ontology/uniprot/AGENT_GUIDE.md`

**Last Updated**: 2026-01-28
