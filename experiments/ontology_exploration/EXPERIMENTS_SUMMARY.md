# Ontology Exploration Experiments - Quick Reference

**Research Question**: How do ontologies improve an LLM's ability to query SPARQL endpoints?

**Answer**: Guides reduce cost by 44-53% with 76% reduction for schema navigation. Production-ready with bounded tools.

---

## Experiment Timeline

| ID | Name | Date | Focus | Key Finding | Cost | Time |
|----|------|------|-------|-------------|------|------|
| **E1** | Basic Exploration | 2026-01-28 | Can models explore ontologies? | ✓ Yes, using rdflib | $0.03 | 78s |
| **E2** | llm_query Synthesis | 2026-01-28 | Will models delegate? | ✗ No, inline better | $0.02 | 86s |
| **E2-L** | Scale Test | 2026-01-28 | Larger ontology triggers delegation? | ✗ No, more efficient | $0.02 | 74s |
| **E3** | Structured Output | 2026-01-28 | Structured format triggers delegation? | ✓ Attempted but hit limits | $0.35 | 79s |
| **E3-R** | Higher Limits | 2026-01-28 | Extended synthesis possible? | ✓ Rich output without delegation | $0.25 | 218s |
| **E4** | Guide Comparison | 2026-01-29 | Do guides help queries? | ✓ -30% cost, better quality | $0.09 | 36s |
| **E4-E** | Multiple Queries | 2026-01-29 | Consistent across query types? | ✓ -44% avg, -49% best | $0.09 | 38s |
| **E5** | Production Endpoint | 2026-01-29 | Real endpoint + tools? | ✓ -53% avg, 100% success | $0.08 | 39s |

---

## Cost Reduction by Query Type

| Query Type | E4 Extension (PROV) | E5 (UniProt Endpoint) | Best Use Case |
|------------|---------------------|----------------------|---------------|
| **Simple (class discovery)** | -48% | -22% | Local ontology sufficient |
| **Relationship (property nav)** | -49% | **-76%** | **Schema navigation (killer app)** |
| **Semantic (conceptual)** | -37% | N/A | Understanding distinctions |
| **Instance (data retrieval)** | N/A | -31% | Querying actual data |
| **Average** | -44% | -53% | All query types benefit |

---

## Key Milestones

### E1-E2: Exploration Works, Delegation Doesn't
- Models can explore ontologies using rdflib
- No need for llm_query delegation
- Inline synthesis more efficient

### E3-E3R: Structured Output Challenge
- Structured format attempted delegation
- Hit iteration limits
- Extended synthesis produced rich guides without delegation

### E4-E4E: Guide Value Validated
- 30-44% cost reduction with guides
- Break-even at 3.6 queries
- Relationship queries benefit most (-49%)

### E5: Production Ready
- 100% success rate on real endpoint
- Bounded tools prevent timeouts
- 76% reduction for schema navigation
- Guide caching eliminates recreation cost

---

## Production Checklist

✅ **Use guides for ontologies queried 4+ times** (break-even at 3.6 queries)

✅ **Always use bounded SPARQL tools** (100% success vs 100% failure)
   - Auto-LIMIT injection
   - Timeout handling
   - Iterative feedback

✅ **Cache guides aggressively** ($0 cost reuse, 80% total savings)

✅ **Start with manual minimal guides** (sufficient for major benefits)

✅ **Prioritize for schema-heavy workloads** (76% reduction for relationship discovery)

---

## File Locations

**Analysis Documents**: `analysis/e{1-5}_results.md`
**Scripts**: `e{1-5}*.py`
**Results Data**: `e{4-5}*_results.json`
**Cached Guides**:
- `e3_retry_guide.json` (PROV)
- `e5_uniprot_guide_cache.json` (UniProt)

---

## Next Steps

1. **Multi-Ontology Validation**: Test on PROV, Dublin Core, FOAF, Schema.org
2. **Complex Queries**: Multi-hop, aggregation, nested queries
3. **Production Integration**: Package as reusable library

---

**For detailed analysis, see individual result documents in `analysis/` directory.**
