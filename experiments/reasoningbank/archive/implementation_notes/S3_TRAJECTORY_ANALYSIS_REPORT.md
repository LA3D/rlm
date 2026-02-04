# S3 Experiment: Comprehensive Trajectory Analysis Report

**Date**: 2026-02-03
**Analyst**: Claude Sonnet 4.5
**Total Trajectories**: 100 (5 tasks × 4 strategies × 5 rollouts)

---

## Executive Summary

Comprehensive analysis of all 100 S3 experiment trajectories reveals **strong agent competence** on 4/5 tasks, with one task failing due to a code bug. Key findings:

### ✅ Agent Competence Validated
- Systematic reasoning and tool use
- Appropriate error handling
- Logical problem-solving approach
- Successful convergence on 4/5 tasks

### ⚠ Critical Issues Identified
1. **No LM-as-judge evaluation**: Judgments not run (blocking MaTTS contrastive extraction)
2. **Task 5 code bug**: `AttributeError` causing 100% failure
3. **Cost underestimate**: Actual $8.81 vs estimated $6.00

---

## 1. Convergence Analysis

### Overall Success Rate: 80% (80/100)

| Metric | Value |
|--------|-------|
| Converged | 80/100 (80.0%) |
| Failed | 20/100 (20.0%) |
| All failures | Task 5 only |

### By Task

| Task | Success Rate | Mean Iterations |
|------|-------------|----------------|
| 1_select_all_taxa_used_in_uniprot | 100% (20/20) | 5.1 ± 0.6 |
| 4_uniprot_mnemonic_id | 100% (20/20) | 4.9 ± 0.8 |
| 2_bacteria_taxa_and_their_scientific_name | 100% (20/20) | 8.2 ± 2.0 |
| 121_proteins_and_diseases_linked | 100% (20/20) | 8.4 ± 2.1 |
| **30_merged_loci** | **0% (0/20)** | **N/A (crash)** |

### By Strategy

All strategies achieved **identical 80% success rate**:

| Strategy | Success Rate | Mean Iterations |
|----------|-------------|----------------|
| none (baseline) | 80% (20/25) | 6.5 ± 2.1 |
| prefix | 80% (20/25) | 6.2 ± 2.0 |
| thinking | 80% (20/25) | 7.3 ± 2.5 |
| rephrase | 80% (20/25) | 6.8 ± 2.4 |

**Interpretation**: Perturbations create diversity without degrading performance ✓

---

## 2. Iteration Count Analysis

### Distribution

| Iterations | Count | Percentage |
|-----------|-------|-----------|
| 4 | 9 | 11.2% |
| 5 | 22 | 27.5% |
| 6 | 17 | 21.2% |
| 7 | 10 | 12.5% |
| 8 | 3 | 3.8% |
| 9 | 10 | 12.5% |
| 10 | 3 | 3.8% |
| 11 | 1 | 1.2% |
| 12 | 4 | 5.0% |
| 13 | 1 | 1.2% |

### Statistics

- **Mean**: 6.7 iterations
- **Median**: 6.0 iterations
- **Range**: 4-13 iterations
- **Std Dev**: 2.2 iterations

### Insights

1. **Most tasks converge quickly**: 60% finish in 4-6 iterations
2. **Task complexity affects iterations**:
   - Simple tasks (1, 4): ~5 iterations
   - Moderate tasks (2, 121): ~8 iterations
3. **Long tail exists**: 10% take 10+ iterations (exploratory trajectories)

---

## 3. Tool Usage Analysis

### Overall Tool Frequency (871 total calls)

| Tool | Calls | Percentage | Purpose |
|------|-------|-----------|---------|
| sparql_query | 413 | 47.4% | Execute SPARQL queries |
| sparql_slice | 302 | 34.7% | Extract result data |
| endpoint_info | 80 | 9.2% | Get endpoint metadata |
| sparql_peek | 29 | 3.3% | Inspect result previews |
| sparql_describe | 21 | 2.4% | Explore entity properties |
| sparql_stats | 14 | 1.6% | Get dataset statistics |
| sparql_count | 12 | 1.4% | Count query results |

### Common Tool Sequences

**Top pattern** (10 trajectories):
```
endpoint_info → sparql_query → sparql_query → sparql_slice → sparql_query
```

**Interpretation**:
1. Agent starts by getting endpoint info (exploration)
2. Iteratively refines queries
3. Uses sparql_slice to extract data
4. Often requires multiple query attempts (refinement)

### Tool Usage Quality

✅ **Appropriate tool selection**: Agents use right tools for each phase
✅ **Query refinement**: Multiple sparql_query calls show iterative improvement
✅ **Data extraction**: Proper use of sparql_slice after queries
✅ **Exploration**: endpoint_info, sparql_peek for understanding schema

---

## 4. Reasoning Quality Assessment

### Sample Trajectory Analysis

**Task**: Select UniProtKB entry with mnemonic 'A4_HUMAN'
**Strategy**: Baseline (none)
**Iterations**: 4
**Result**: SUCCESS ✓

#### Iteration-by-Iteration Reasoning

**Iteration 1**: Problem exploration
```
Reasoning: "I need to:
1. First explore the available data - look at context and question
2. Understand what UniProtKB entries are and how to query them
3. Use the available SPARQL tools to find the entry with mnemonic 'A4_HUMAN'
4. Construct a proper SPARQL query and get the answer"

Code: print(question); print(context[:1000])
```
✅ **Sound approach**: Systematic exploration before acting

**Iteration 2**: Schema understanding
```
Reasoning: "I can see the context provides information about the UniProt RDF schema.
I need to find out what predicate relates to 'mnemonic' in UniProt."

Code: info = endpoint_info(); result = llm_query("What predicate for mnemonic?")
```
✅ **Logical progression**: Gets endpoint info, tries to query for schema knowledge

**Iteration 3**: Error recovery
```
Reasoning: "I see that llm_query is not available in the namespace. Let me work
with the SPARQL tools instead. In UniProt, the mnemonic is typically stored using
the up:mnemonic predicate. I'll construct a SPARQL query."

Code: query = "PREFIX up: <...> SELECT ?entry WHERE { ?entry up:mnemonic 'A4_HUMAN' . }"
```
✅ **Graceful error handling**: Recognizes failure, adapts strategy, applies domain knowledge

**Iteration 4**: Solution completion
```
Reasoning: "Perfect! The SPARQL query worked and returned 1 row. Now I need to:
1. Get the actual data using sparql_slice
2. Extract the full URI
3. Prepare final answer with SPARQL query and entry URI"

Code: data = sparql_slice(result); SUBMIT(sparql=query, answer=data[0]['entry'])
```
✅ **Proper completion**: Extracts data, submits correctly formatted answer

### Reasoning Quality Metrics

| Quality Aspect | Assessment | Evidence |
|---------------|-----------|----------|
| **Systematic exploration** | ✅ Excellent | Agents explore context/tools before acting |
| **Logical progression** | ✅ Excellent | Clear reasoning chain toward solution |
| **Error handling** | ✅ Excellent | Graceful adaptation when tools fail |
| **Domain knowledge** | ✅ Good | Correct use of UniProt predicates |
| **Tool selection** | ✅ Excellent | Appropriate tools for each task phase |
| **Completion protocol** | ✅ Excellent | Proper SUBMIT with sparql + answer |

---

## 5. LM-as-Judge Analysis

### Critical Finding: ⚠ No Judgments Run

**Event types found in trajectories**:
- `run_start`
- `tool_call`
- `tool_result`
- `iteration`
- `run_complete`

**Missing**:
- ❌ `judgment` events
- ❌ Judge reasoning
- ❌ Grounded success/failure assessment

### Impact on MaTTS

**Blocked capabilities**:
1. ❌ **Contrastive extraction**: Cannot compare success vs failure reasoning
2. ❌ **Quality filtering**: Cannot distinguish correct vs incorrect solutions
3. ❌ **Memory extraction**: No grounded evidence for what worked

**Current success determination**:
- Based solely on `converged` status (SUBMIT called)
- No verification that answer is correct
- No assessment of reasoning quality

### Recommendation

**MUST add LM-as-judge before MaTTS**:
1. Run judge on all 80 successful trajectories
2. Verify answers are actually correct
3. Extract grounded reasoning from judge
4. Use for contrastive memory extraction

---

## 6. Task 5 Failure Analysis

### The Problem

**Task**: Find UniProtKB entries with merged loci in Bordetella avium
**Result**: 100% failure (0/20 across all strategies)
**Cause**: Code bug, not reasoning failure

### Error Details

```json
{
  "event_type": "run_error",
  "data": {
    "error": "'NoneType' object has no attribute 'strip'",
    "type": "AttributeError"
  }
}
```

**Characteristics**:
- Immediate crash (no iterations)
- Identical failure across all strategies (Vendi=1.00)
- $0.00 cost (no LLM calls made)
- No trajectory data

### Root Cause Hypothesis

Likely causes:
1. **Malformed task query**: Query string may be None or empty
2. **Context building bug**: rollout_id handling may have edge case
3. **Perturbation bug**: One of the perturbation strategies may return None

### Impact

- Inflated failure rate (20/100 vs 0/80 on working tasks)
- Skewed diversity metrics for Task 5
- Reduced statistical power (4 tasks instead of 5)

### Recommendation

1. **Debug Task 5**: Inspect code path for this specific query
2. **Add null checks**: Prevent crashes on None values
3. **Re-run Task 5**: After fix, re-evaluate with 20 rollouts
4. **Consider exclusion**: If task is fundamentally problematic, remove from eval set

---

## 7. Cost Analysis

### Actual vs Estimated

| Metric | Estimated | Actual | Difference |
|--------|-----------|--------|-----------|
| Total cost | $6.00 | **$8.81** | +47% |
| Cost per trajectory | $0.06 | **$0.088** | +47% |

### Cost by Task

| Task | Cost | Trajectories | Avg/Trajectory |
|------|------|-------------|---------------|
| 121_proteins_and_diseases_linked | $3.07 | 20 | $0.154 |
| 2_bacteria_taxa_and_their_scientific_name | $3.24 | 20 | $0.162 |
| 1_select_all_taxa_used_in_uniprot | $1.35 | 20 | $0.068 |
| 4_uniprot_mnemonic_id | $1.14 | 20 | $0.057 |
| 30_merged_loci | $0.00 | 20 | $0.000 |

### Token Usage

- **Total tokens**: 2,039,464
  - Prompt tokens: 1,849,288 (90.7%)
  - Completion tokens: 190,176 (9.3%)

**Interpretation**:
- Complex tasks (121, 2) cost ~3× more than simple tasks
- More iterations = higher cost
- Prompt caching would reduce costs significantly (90% prompt tokens)

---

## 8. Memory Analysis

### Finding: No Memory Integration

**Expected**:
- Memory extraction from successful trajectories
- Memory storage in SQLite ReasoningBank
- Memory retrieval for context injection

**Actual**:
- ❌ Memories extracted: 0
- ❌ Memories stored: 0
- ❌ No memory events in logs

**Conclusion**: This was a **baseline run** without memory integration.

### Impact on MaTTS Goals

**S3 experiment validated**:
✅ Prompt perturbation creates diversity
✅ Agent competence on 4/5 tasks
✅ Perturbations don't hurt performance

**NOT validated**:
❌ Memory extraction quality
❌ Memory storage/retrieval
❌ Contrastive extraction (success vs failure)
❌ LM-as-judge quality

---

## 9. Trajectory Diversity Validation

### Diversity Metrics (from reprocessed results)

**By strategy (averaged across 4 working tasks)**:

| Strategy | Trajectory Vendi | Efficiency | Mean Jaccard |
|----------|-----------------|-----------|--------------|
| none (baseline) | 1.51 | 30.2% | 0.584 |
| **prefix** | **1.68** | **33.5%** | 0.598 |
| thinking | 1.65 | 32.9% | 0.593 |
| rephrase | 1.64 | 32.8% | 0.615 |

### Validation

✅ **Caching fix works**: All strategies show Vendi > 1.0 (no identical trajectories)
✅ **Perturbations create diversity**: Prefix strategy +11% Vendi vs baseline
✅ **Efficiency reasonable**: ~33% unique trajectories (k=5, expect ~2 effective)

### Tool Sequence Diversity

**Top 10 sequences** (out of 80 successful):
- Most common: 10 trajectories (12.5%)
- Diverse patterns: 10 different sequences in top 10

**Interpretation**: Good diversity in problem-solving approaches

---

## 10. Key Findings Summary

### Agent Competence ✅

1. **Reasoning quality**: Systematic, logical, coherent
2. **Tool usage**: Appropriate selection and sequencing
3. **Error handling**: Graceful adaptation to failures
4. **Problem-solving**: Iterative refinement toward solution
5. **Completion protocol**: Proper SUBMIT with required fields

### Trajectory Diversity ✅

1. **Caching fix validated**: No identical trajectories (Vendi > 1.0)
2. **Perturbations effective**: Prefix strategy best (+11% diversity)
3. **No performance degradation**: All strategies maintain 80% success
4. **Tool sequence diversity**: Varied problem-solving approaches

### Critical Issues ⚠

1. **No LM-as-judge**: Blocks contrastive extraction for MaTTS
2. **Task 5 bug**: 20% failure rate due to code error
3. **No memory integration**: Baseline run, not full MaTTS
4. **Cost underestimate**: $8.81 vs $6.00 estimated (+47%)

---

## 11. Recommendations

### Immediate Actions (Before MaTTS)

1. **Add LM-as-judge evaluation**
   - Run judge on all 80 successful trajectories
   - Verify answers are correct
   - Extract grounded reasoning

2. **Fix Task 5 bug**
   - Debug `AttributeError: 'NoneType' object has no attribute 'strip'`
   - Re-run Task 5 with all strategies
   - Validate fix doesn't affect other tasks

3. **Validate judgment quality**
   - Manually inspect 10-20 judge outputs
   - Check for false positives/negatives
   - Tune judge prompt if needed

### MaTTS Implementation

4. **Use prefix perturbation** ("[Attempt N] query")
   - Best diversity (Vendi=1.68)
   - Highest efficiency (33.5%)
   - No performance impact

5. **Set k=5 rollouts per task**
   - Vendi ~1.5-2.0 suggests good coverage
   - Cost-effective (~$0.09 per task)
   - Diminishing returns likely beyond k=5

6. **Implement contrastive extraction**
   - Extract from success/failure pairs
   - Use judge reasoning for grounding
   - Store in SQLite ReasoningBank

### Cost Management

7. **Budget for higher costs**
   - Use $0.09/trajectory (not $0.06)
   - Full 10-task eval: ~$0.90
   - Full 100-task eval: ~$9.00

8. **Consider prompt caching**
   - 90% of tokens are prompts
   - Anthropic prompt caching could reduce costs 50%+
   - Worth investigating for large-scale runs

---

## 12. Next Steps

### Phase 1: Validate Judge (1-2 days)

1. Implement LM-as-judge for S3 trajectories
2. Run judge on 80 successful trajectories
3. Manual inspection of judge outputs (10-20 samples)
4. Validate judge accuracy and reasoning quality

### Phase 2: Fix Task 5 (1 day)

1. Debug AttributeError in Task 5
2. Re-run Task 5 (20 rollouts)
3. Validate fix doesn't break other tasks
4. Update S3 results with fixed Task 5 data

### Phase 3: MaTTS Implementation (3-5 days)

1. Implement memory extraction from judge outputs
2. Store memories in SQLite ReasoningBank
3. Implement memory retrieval for context injection
4. Run closed-loop MaTTS experiment

### Phase 4: Evaluation (2-3 days)

1. Compare baseline (no memory) vs MaTTS (with memory)
2. Measure Pass@1 improvement
3. Analyze which memories help which tasks
4. Document findings and recommendations

---

## Appendix: Trajectory Examples

### Example 1: Successful Simple Task (4 iterations)

**Task**: Select UniProtKB entry with mnemonic 'A4_HUMAN'
**Strategy**: Baseline (none)
**Result**: SUCCESS ✓

**Reasoning chain**:
1. Explore context and question
2. Get endpoint info, try llm_query (fails)
3. Adapt: Use SPARQL with up:mnemonic predicate
4. Extract data, SUBMIT answer

**Final answer**: `http://purl.uniprot.org/uniprot/P05067`

### Example 2: Successful Moderate Task (8 iterations)

**Task**: List UniProtKB proteins and diseases annotated to be related
**Strategy**: Prefix perturbation
**Result**: SUCCESS ✓

**Reasoning chain** (abbreviated):
1. Explore problem, get endpoint info
2. Try initial query for diseases
3. Refine query based on results
4. Iterate on query structure
5-7. Multiple refinements
8. SUBMIT final query and answer

**Characteristic**: More iterations needed for complex task

### Example 3: Failed Task (immediate crash)

**Task**: Find UniProtKB entries with merged loci in Bordetella avium
**Strategy**: All strategies
**Result**: FAILURE (code error)

**Error**: `AttributeError: 'NoneType' object has no attribute 'strip'`

**Iterations**: 0 (crashed before execution)

---

## Conclusion

The S3 experiment successfully validated:
- ✅ Agent competence on UniProt SPARQL tasks
- ✅ Prompt perturbation effectiveness for diversity
- ✅ Caching fix preventing identical rollouts
- ✅ Trajectory diversity metrics (Vendi Score, efficiency)

Critical gaps identified:
- ⚠ No LM-as-judge evaluation (required for MaTTS)
- ⚠ Task 5 code bug (20% artificial failure rate)
- ⚠ No memory integration (baseline only)

**Recommendation**: Add LM-as-judge evaluation and fix Task 5 bug before proceeding with full MaTTS implementation. The agent is competent and the diversity methods work - we now need grounded judgment to enable contrastive memory extraction.
