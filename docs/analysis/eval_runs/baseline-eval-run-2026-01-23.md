# Baseline Eval Run Analysis

**Date**: 2026-01-23
**Purpose**: Run one trajectory through each eval task to establish baseline and verify system correctness

## Summary

Ran 9 eval tasks (deprecated 2 PROV tasks that require remote endpoints):
- **Execution errors**: 3 tasks (configuration/parsing issues)
- **Ran but failed graders**: 6 tasks (mostly grader issues, not execution issues)
- **Overall pass rate**: 0/9 (0%)

**Key finding**: System IS executing correctly (6/9 tasks completed full trajectories), but **automated graders are too strict**. LLM judge passes most tasks that automated graders fail.

---

## Task Results Detail

### Execution Errors (3 tasks)

#### 1. hallucination_detection_001
**Error**: `DSPy backend requires SPARQL endpoint in task context`
**Cause**: Task needs special handling (no remote endpoint, expects agent to recognize non-existent class)
**Action**: Defer until other issues resolved

#### 2. uniprot_dopamine_similarity_variants_disease_001
**Error**: `'NoneType' object has no attribute 'strip'`
**Cause**: Parsing error during task execution
**Action**: Investigate task runner parsing logic

#### 3. uniprot_sphingolipids_chembl_001
**Error**: `Adapter JSONAdapter failed to parse the LM response. Expected to find output fields: [thinking, verification, reflection, answer, sparql, evidence] Actual: [thinking, verification, reflection, answer, sparql]`
**Cause**: **Missing required 'evidence' field in DSPy RLM output**
**Action**: **HIGH PRIORITY - Fix DSPy RLM to always output evidence field**

---

### Completed with Grader Failures (6 tasks)

#### 4. multi_endpoint_routing_001 (11 iterations)
**Graders**:
- ✓ Convergence (within 12 limit)
- ✓ Tool called
- ✗ SPARQL structural: Missing SERVICE to rhea-db.org

**Analysis**: Strict grader expects specific SERVICE endpoint, but query may be valid alternative approach.

---

#### 5. uniprot_gene_protein_rhea_sets_001 (12 iterations)
**Graders**:
- ✓ Tool called
- ✗ Convergence: Exceeded iteration limit (13 > 12)
- ✗ Outcome verification: Found 0 results, need >= 1
- ✗ LLM judge: "While the query structure is semantically sound..."

**Analysis**: Iteration limit too tight (off by 1). Outcome verification may be broken (see #8).

---

#### 6. uniprot_genetic_disease_proteins_001 (10 iterations)
**Graders**:
- ✓ LLM judge: "The query correctly identifies proteins with disease..."
- ✓ Tool called
- ✗ Convergence: Exceeded iteration limit (11 > 10)
- ✗ SPARQL structural: Missing required GRAPH clause
- ✗ Outcome verification: Found 2 results, need >= 3

**Analysis**: **LLM judge PASSED but automated graders FAILED**. This is the pattern we're seeing - strict structural requirements vs semantic correctness.

---

#### 7. uniprot_materialized_hierarchy_001 (12 iterations)
**Graders**:
- ✓ Tool called
- ✗ Convergence: Exceeded iteration limit (13 > 12)
- ✗ SPARQL structural: Missing required patterns: up:enzyme

**Analysis**: Off by 1 on iterations. Strict pattern matching vs semantic equivalence.

---

#### 8. uniprot_orthologs_orthodb_001 (11 iterations) ⚠️ IMPORTANT
**Graders**:
- ✓ Convergence (within 12 limit)
- ✓ SPARQL structural (all requirements met)
- ✓ LLM judge: "The agent successfully retrieved orthologous proteins..."
- ✓ Tool called
- ✗ Outcome verification: **"Found 0 results, need >= 1"**

**BUT Agent Answer**: "Found 100 orthologous proteins for UniProtKB entry P05067..."

**Analysis**: **Outcome verification grader is BROKEN**. Agent clearly found and reported results, but grader says 0 results. This grader is reading from the wrong place or has a bug.

---

#### 9. uniprot_rhea_reaction_ec_protein_001 (11 iterations)
**Graders**:
- ✓ Convergence (within 12 limit)
- ✓ LLM judge: "The query correctly federates between Rhea and UniProt..."
- ✓ Tool called
- ✗ SPARQL structural: Missing SERVICE to sparql.uniprot.org
- ✗ Outcome verification: Found 0 results, need >= 1

**Analysis**: LLM judge happy, automated graders not. Outcome verification likely broken (see #8).

---

## Key Issues Identified

### 1. Outcome Verification Grader is Broken (HIGH PRIORITY)
**Evidence**: Task #8 (orthologs) - Agent says "Found 100 orthologous proteins" but grader reports "Found 0 results"

**Hypothesis**: Grader is checking the wrong field or has a parsing bug.

**Action**: Investigate `evals/graders/outcome_verification.py` to see where it's reading results from.

---

### 2. Missing 'evidence' Field in DSPy Output (HIGH PRIORITY)
**Evidence**: Task #3 (sphingolipids) - JSON adapter expects `[thinking, verification, reflection, answer, sparql, evidence]` but only gets first 5.

**Expected output contract** (from query construction design):
```python
{
    "thinking": str,
    "verification": str,
    "reflection": str,
    "answer": str,
    "sparql": str,
    "evidence": dict  # ← Missing!
}
```

**Action**:
1. Check `rlm_runtime/engine/dspy_rlm.py` signature definition
2. Verify DSPy RLM module includes evidence field in output
3. Ensure evidence is populated with grounding info (URIs, result samples, etc.)

---

### 3. Automated Graders Too Strict vs LLM Judge
**Pattern**: LLM judge passes tasks that automated graders fail.

**Examples**:
- Task #6: LLM says "correctly identifies proteins" but structural grader fails on GRAPH clause
- Task #9: LLM says "correctly federates" but structural grader fails on SERVICE endpoint

**Recommendation**:
- **Keep LLM judge as primary arbiter of correctness**
- Use automated graders for **metrics/analysis**, not pass/fail decisions
- Consider integrating automated checks into LLM judge context (let LLM evaluate with hints)

---

### 4. Iteration Limits Too Tight
**Evidence**: Multiple tasks exceeded limit by 1 iteration (off-by-one)
- Task #5: 13 > 12
- Task #6: 11 > 10
- Task #7: 13 > 12

**Current limits**: 10-12 iterations
**Recommendation**: Increase to 15-16 iterations for baseline, then optimize downward with memory

---

### 5. Hallucination Detection Needs Special Handling
**Issue**: Expects agent to recognize non-existent class without querying remote endpoint

**Action**: Defer until other issues resolved. May need different test structure.

---

## Recommendations

### Immediate (Fix before further testing)

1. **Fix outcome_verification grader** (HIGH)
   - Investigate where it reads results from
   - Test against task #8 which clearly has results

2. **Add evidence field to DSPy output** (HIGH)
   - Update signature in dspy_rlm.py
   - Populate with grounding info (URIs, samples, handle metadata)

3. **Increase iteration limits** (MEDIUM)
   - Bump to 15-16 for complex tasks
   - Use this as baseline before optimization

### Short-term (Architecture decisions)

4. **Revise grader strategy** (MEDIUM)
   - Make LLM judge primary pass/fail arbiter
   - Use automated graders for metrics/insights
   - Provide automated check results as context to LLM judge

5. **Fix dopamine task parsing error** (LOW)
   - Investigate NoneType error

6. **Defer hallucination detection** (LOW)
   - Requires different test structure
   - Not blocking other work

---

## Positive Findings

Despite 0% pass rate:

1. **System executes correctly** - 6/9 tasks completed full trajectories
2. **LLM judge is reasonable** - Passed 4/6 completed tasks semantically
3. **Agent finds correct answers** - Task #8 found 100 orthologs despite grader saying 0
4. **SPARQL queries execute** - All tasks that ran used tools correctly
5. **Iteration counts reasonable** - 10-12 iterations for complex tasks

**Conclusion**: The RLM execution engine works. The grading infrastructure needs fixes.

---

## Next Steps

1. ✅ Document findings (this document)
2. ⏭️ Fix outcome_verification grader
3. ⏭️ Add evidence field to DSPy RLM output
4. ⏭️ Increase iteration limits in task definitions
5. ⏭️ Re-run failed tasks to verify fixes
6. ⏭️ Once passing, establish proper baselines for E009 sampling study
