# E001: Baseline Before Reasoning Fields

## Summary

Baseline measurements collected 2026-01-20 to 2026-01-22 before implementing Think-Act-Verify-Reflect reasoning cycles.

**Git commit**: `03d298b4`

## Results

| Task | Pass Rate | Trials | Avg Iterations |
|------|-----------|--------|----------------|
| bacteria_taxa | 58.6% | 17/29 | 8.9 |
| ecoli_k12 | **0.0%** | 0/6 | 11.0 |
| basic_search | 0.0% | 0/4 | 0.0 (failed) |

## Key Findings

### Evidence Format Problem

The E. coli K12 task revealed a systematic evidence format issue:

**What the task requires:**
- Protein URIs
- **Actual amino acid sequences** (strings of A-Z letters)

**What the agent provided:**
```json
{
  "protein": "http://purl.uniprot.org/uniprot/...",
  "sequence_length": 298  // WRONG - this is metadata, not data
}
```

The agent stored `sequence_length` (metadata about the sequence) instead of the actual sequence string.

### Why This Happened

No explicit verification step before `SUBMIT`. The agent:
1. Executed SPARQL query
2. Got results with sequence data
3. Extracted result summary
4. **Never checked** if evidence had required fields
5. Submitted with wrong evidence format

### Bacteria Taxa Success

The bacteria_taxa task had moderate success (58.6%) because:
- Required fields were simpler (just taxon URIs)
- Less likely to confuse metadata with data
- Task was more forgiving of evidence format variations

## Implications for E002

This baseline clearly motivates the Think-Act-Verify-Reflect approach:

**VERIFY step needed:**
- Check results match expectations
- Verify required fields are present
- Confirm data types are correct (sequences are strings, not lengths)

**REFLECT step needed:**
- Self-critique before SUBMIT
- "Does evidence include actual data, not just metadata?"

## Next Steps

→ **E002**: Implement Rung 1 with thinking/verification/reflection fields

**Target improvement:**
- E. coli K12: 0% → >50% pass rate
- Evidence format: metadata → actual data
- Overhead: <2 iteration increase

---

**Migrated from**: `evals/results/` (flat directory)
**Analysis date**: 2026-01-23
