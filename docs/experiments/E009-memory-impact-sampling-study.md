# E009: Memory Impact Sampling Study

**Date**: 2026-01-23
**Status**: Proposed
**Purpose**: Systematically test memory impact with proper sampling to account for stochasticity

## Problem Statement

Current conclusions about memory are based on N=1 runs:
- 1 run without memory
- 1 run with memory
- High LLM stochasticity means single runs are not reliable

**Key unknowns:**
1. Is memory impact consistent across runs? (or just variance)
2. Do agents actually use memories when present? (tracking needed)
3. Are specific memories helpful/harmful? (need per-memory analysis)
4. What's in the memory bank? (content analysis)
5. Is this architectural or just execution issue?

## Memory Bank Analysis (Initial Findings)

**Current state:**
- **73 memories** stored in evals/memory.db
- All have **0 accesses, 0 successes** → not being tracked or used?
- Memory content is actually quite good (see examples below)

### Sample Memory Content

**"Task Scope Recognition: All vs One"** (retrieved for both queries):
```
Recognize task scope and adjust strategy:

**Find ALL instances** (e.g., "all bacterial taxa"):
✓ Use transitive hierarchy queries (?taxon subClassOf+ bacteria)
✓ Avoid LIMIT clauses in final query
✓ Test hierarchy predicates (rdfs:subClassOf+, skos:narrower+)
✗ Don't inspect individual entity lineages
✗ Don't use describe_entity on samples

**Find ONE example** (e.g., "give example of activity"):
✓ Use describe_entity to inspect structure
✓ Check sample instance properties
✓ Validate one case thoroughly
✗ Don't construct exhaustive queries

Match your iteration strategy to task scope.
```

**Observation**: This memory has GOOD, ACTIONABLE advice:
- For "all bacteria taxa": Use transitive hierarchy, avoid LIMIT
- Clear do's and don'ts

**But the agent IGNORED it:**
- Agent with memory: Generic exploration in early iterations
- Agent without memory: Targeted FILTERs from iteration 1
- Result: Agent WITHOUT memory was MORE focused

**Question**: Why isn't the agent using good memories?

### Retrieved Memories by Query

**Simple query (bacteria taxa):**
1. Task Scope Recognition: All vs One
2. Taxonomic Entity Resolution Strategy
3. Taxonomic Data Extraction Protocol

**Complex query (E. coli K12):**
1. Task Scope Recognition: All vs One
2. Taxonomic Lineage Retrieval Approach
3. Taxonomy-Based Entity Retrieval

**Observation**: Retrieval seems reasonable (taxonomy-related memories for taxonomy queries)

## Experiment Design: Proper Sampling

### Hypothesis

**H0 (Null)**: Memory has no consistent impact on performance (observed differences are random variance)

**H1 (Alternative)**: Memory has consistent impact (positive or negative) on:
- Iteration count
- Execution time
- Token usage
- Success rate
- Evidence quality

### Cohorts

**Cohort A: Without memory** (baseline)
- Disable memory retrieval
- Clean baseline behavior
- N=10 runs per task

**Cohort B: With memory** (current system)
- Enable memory retrieval (k=3)
- Current injection format
- N=10 runs per task

**Cohort C: Memory with explicit prompting** (experimental)
- Enable memory retrieval (k=3)
- Add explicit instruction: "CONSULT the retrieved memories before planning"
- N=10 runs per task

### Task Selection

Test on 4 tasks spanning complexity:

1. **Simple taxonomy** (uniprot/taxonomy/uniprot_bacteria_taxa_001)
   - Expected: 5-10 iterations
   - Retrieved memories: Task scope, taxonomic strategies

2. **Complex sequences** (uniprot/taxonomy/uniprot_ecoli_k12_sequences_001)
   - Expected: 10-15 iterations
   - Retrieved memories: Task scope, lineage retrieval

3. **Federated query** (uniprot/federated/uniprot_rhea_reaction_ec_protein_001)
   - Expected: 10-15 iterations
   - Tests: SERVICE/GRAPH handling

4. **Multi-hop** (uniprot/multihop/uniprot_gene_protein_rhea_sets_001)
   - Expected: 12-16 iterations
   - Tests: Complex reasoning

### Metrics to Collect

**Performance:**
- Iteration count (primary metric)
- Total time (seconds)
- Token usage (prompt + completion)
- Cost ($)

**Success:**
- Pass/fail (grader result)
- Evidence quality score
- SPARQL correctness

**Memory-specific:**
- Which memories retrieved
- Memory retrieval BM25 scores
- Did agent reference memories? (text search in code/reasoning)
- Token overhead from memory context

### Statistical Analysis

**Per task:**
- Mean ± std for each metric by cohort
- Student's t-test: Cohort A vs B, A vs C
- Effect size (Cohen's d)
- P-value threshold: 0.05

**Across tasks:**
- Aggregate statistics
- Mixed-effects model (task as random effect)

**Decision criteria:**
- If p > 0.05: Can't reject H0 (differences are noise)
- If p < 0.05 and memory helps: Keep memory
- If p < 0.05 and memory hurts: Redesign memory architecture

## Memory Usage Tracking (Missing)

**Current state**: No explicit tracking of which memories influenced which decisions

**Need to add:**

1. **Memory injection logging**
   - Log exactly what text was added to context
   - Log token count for memory section

2. **Memory reference tracking**
   - After each LLM response, check if any memory titles/content referenced
   - Log binary: was_memory_referenced

3. **Memory usage stats**
   - Update access_count when memory is retrieved
   - Update success_count when used AND task succeeds
   - Update failure_count when used AND task fails

4. **Per-iteration tracking**
   - Which memories were in context for this iteration?
   - Did agent's code/reasoning mention them?
   - Did behavior align with memory guidance?

## Implementation Plan

### Phase 1: Add Memory Usage Tracking (prerequisite)

1. **Update TrajectoryCallback**
   - Add memory_context_injected event
   - Log memory IDs, titles, token overhead

2. **Update memory system**
   - Increment access_count on retrieval
   - Track memory → trajectory mapping

3. **Add memory reference detection**
   - Search LLM outputs for memory titles/keywords
   - Log was_referenced boolean

### Phase 2: Run Sampling Experiment

1. **Setup**
   - Create experiment directory: evals/experiments/E009_memory_sampling/
   - Define cohorts in experiment.yaml

2. **Execution**
   ```bash
   # Cohort A (no memory): 4 tasks × 10 runs = 40 runs
   for task in [bacteria_taxa, ecoli_k12, rhea_reaction, gene_protein]; do
       python -m evals.cli run ${task} --trials 10 \
           --output E009/cohort_A \
           --enable-trajectory-logging
   done

   # Cohort B (with memory): 4 tasks × 10 runs = 40 runs
   for task in [bacteria_taxa, ecoli_k12, rhea_reaction, gene_protein]; do
       python -m evals.cli run ${task} --trials 10 \
           --output E009/cohort_B \
           --enable-memory \
           --enable-trajectory-logging
   done

   # Cohort C (explicit prompting): 4 tasks × 10 runs = 40 runs
   for task in [bacteria_taxa, ecoli_k12, rhea_reaction, gene_protein]; do
       python -m evals.cli run ${task} --trials 10 \
           --output E009/cohort_C \
           --enable-memory \
           --explicit-memory-prompting \
           --enable-trajectory-logging
   done
   ```

3. **Total**: 120 runs (4 tasks × 3 cohorts × 10 trials)
   - Estimated time: ~4-6 hours
   - Estimated cost: ~$40-60

### Phase 3: Analysis

1. **Aggregate metrics** per cohort
2. **Statistical tests** (t-tests, effect sizes)
3. **Memory usage analysis** (were memories referenced?)
4. **Trajectory comparison** (qualitative review of samples)

## Expected Outcomes

### Scenario 1: Memory consistently helps
- Cohort B/C: Lower iterations, faster time, similar pass rate
- P < 0.05, positive effect size
- **Action**: Keep memory, optimize retrieval/injection

### Scenario 2: Memory consistently hurts
- Cohort B/C: Higher iterations, slower time, similar pass rate
- P < 0.05, negative effect size
- **Action**: Redesign memory architecture (Type A/B split)

### Scenario 3: No consistent effect
- High variance, p > 0.05
- Differences are just stochasticity
- **Action**: Need larger N or rethink hypothesis

### Scenario 4: Explicit prompting helps (C > A, B)
- Cohort C outperforms A and B
- **Action**: Memory content is good, but needs explicit instruction to use

## Open Questions

1. **Are memories being used at all?**
   - All 73 memories show 0 accesses, 0 successes
   - Is usage tracking broken?
   - Or are memories truly not being consulted?

2. **Is retrieval working correctly?**
   - Retrieved memories seem relevant (taxonomy for taxonomy tasks)
   - But agent behavior suggests they're not being applied
   - Is the injection format the problem?

3. **What's the cold start solution?**
   - 73 memories already exist
   - More runs → more memories
   - But if they're not being used, more won't help

4. **Is this architectural or execution?**
   - Content is good ("Task Scope Recognition" has actionable advice)
   - Retrieval is reasonable (taxonomy memories for taxonomy queries)
   - But agent ignores them
   - **Hypothesis**: Injection format / lack of explicit instruction

## Next Steps

1. ⏭️ **Add memory usage tracking** (prerequisite)
   - Implement tracking in callbacks
   - Update access_count, track references

2. ⏭️ **Pilot test** (N=3 per cohort, 1 task)
   - Validate tracking works
   - Check variance levels
   - Refine design if needed

3. ⏭️ **Full experiment** (N=10 per cohort, 4 tasks)
   - Run all 120 trials
   - Collect complete data

4. ⏭️ **Statistical analysis**
   - Test hypotheses
   - Make data-driven decision

5. ⏭️ **Based on results:**
   - If memory helps: Proceed with optimization
   - If memory hurts: Design E010 (dual-memory architecture)
   - If inconclusive: Increase N or rethink approach

## References

- Current N=1 analysis: docs/analysis/memory-agent-behavior-analysis.md
- Memory architecture: docs/design/reasoningbank-sqlite-architecture.md
- Previous experiments: E001 (baseline), E002 (TAVR)
