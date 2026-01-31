# E9a: Memory Accumulation Impact

**Question**: Does accumulated procedural memory help subsequent queries?

**Design**:
- Run 1 (cold start): No memory → extract 3 procedures
- Run 2 (warm start): Load memory from Run 1 → compare performance

**Configuration**: L0 (sense card) + L2 (memory)

---

## Results

### Iteration Counts

| Task | Run 1 (cold) | Run 2 (warm) | Improvement |
|------|--------------|--------------|-------------|
| entity_lookup | 11 | 3 | **-8 (-73%)** |
| property_find | 9 | 12 | **+3 (+33%)** ⚠️ |
| hierarchy | 9 | 3 | **-6 (-67%)** |
| **TOTAL** | **29** | **18** | **-11 (-38%)** |

### Context Size (chars injected)

| Task | Run 1 | Run 2 | Delta |
|------|-------|-------|-------|
| entity_lookup | 473 | ~1500 | +1027 |
| property_find | 473 | 2004 | +1531 |
| hierarchy | 473 | ~1500 | +1027 |

---

## Analysis

### Success Cases (2/3 tasks)

**entity_lookup** and **hierarchy** showed dramatic improvements:
- Both converged in 3 iterations (vs 9-11)
- Explicitly referenced memory procedures in reasoning
- Example quote from hierarchy Run 2:
  > "The context specifically outlined a strategy for querying class hierarchies using rdfs:subClassOf, which I followed exactly"

### Failure Case (1/3 tasks)

**property_find** got **worse** with memory:
- 9→12 iterations (hit max_iters limit)
- Context size 2004 chars (largest)
- Likely retrieved too much context or wrong procedure

**Hypothesis**: The "multi-approach property discovery" procedure may have been:
1. Too complex (suggested 3 different query approaches)
2. Created confusion rather than clarity
3. Led to over-exploration

---

## Key Findings

1. ✅ **Memory accumulation helps** (38% overall reduction)
2. ✅ **Dramatic speedup** on simple tasks (entity lookup, hierarchy)
3. ⚠️ **Quality matters**: Complex/ambiguous procedures can hurt performance
4. ⚠️ **Retrieval relevance**: Need better filtering to avoid injecting wrong context

---

## Extracted Procedures (Run 1)

1. **[success]** Query Class Labels for Concept Definitions
   - "Use rdfs:label to get foundational definitions"
   
2. **[success]** Multi-approach property discovery with domain/range analysis
   - "Use three-pronged approach: domain, range, and known properties"
   
3. **[success]** Query class hierarchy using rdfs:subClassOf
   - "Use rdfs:subClassOf pattern to find direct subclasses"

---

## Next Steps

1. **Improve extraction quality**: Simpler, more focused procedures
2. **Better retrieval**: Filter by task similarity, not just keyword match
3. **Test with more tasks**: E9a used only 3 tasks (small sample)
4. **Add L1 schema**: Would schema constraints help with property_find?

