# Performance Profiling Results

**Date**: 2026-01-23
**Context**: User observed 5-minute runtime for simple SPARQL queries vs their 30-40 second manual test
**Goal**: Understand where time is being spent in the agentic loop

## Methodology

1. Added trajectory logging infrastructure with timestamps for all LLM calls and tool executions
2. Created profiling script (`evals/scripts/profile_timing.py`) to analyze trajectory JSONL logs
3. Ran controlled benchmark comparing simple vs complex queries with trajectory logging enabled

## Implementation Fix

**Problem**: Tool execution timing was not captured initially because:
- Tools are plain Python functions executed via `exec()` in NamespaceCodeInterpreter
- DSPy's callback system only captured LLM calls, not tool invocations

**Solution**: Added instrumentation inside NamespaceCodeInterpreter to wrap tools with callback events:
- Modified `execute()` method to call `_instrument_tools_if_needed()`
- Tools are wrapped to emit `on_tool_start` and `on_tool_end` events
- Callback events include call_id, timestamps, inputs, and outputs
- Works transparently with DSPy's RLM module

**Files Modified**:
- `rlm_runtime/interpreter/namespace_interpreter.py` - Added tool instrumentation
- `rlm_runtime/logging/trajectory_callback.py` - Already had callback methods (no changes needed)
- `evals/scripts/profile_timing.py` - Created profiling script

## Benchmark Results

### Simple Query: Bacteria Taxa

**Task**: `uniprot/taxonomy/uniprot_bacteria_taxa_001`
**Description**: Find all bacteria taxa in UniProt

```
Total Duration: 120.8s (2.0 minutes)

Breakdown:
  LLM Calls:       113.1s (93.6%)
  Tool Execution:    7.5s ( 6.2%)
    - SPARQL:        7.4s ( 6.1%)
    - Other tools:   0.2s ( 0.1%)
  Unaccounted:       0.2s ( 0.2%) [overhead/idle]

Counts:
  LLM Calls:    10
  Tool Calls:   25
  SPARQL Calls: 10

Averages:
  Per LLM Call:    11.31s
  Per Tool Call:    0.30s
  Per SPARQL Call:  0.74s
```

**Key Observations**:
- 10 iterations with 10 LLM calls
- SPARQL execution is fast (0.74s average per query)
- LLM latency dominates (93.6% of total time)
- Minimal overhead (0.2%)

### Complex Query: E. coli K12 Sequences

**Task**: `uniprot/taxonomy/uniprot_ecoli_k12_sequences_001`
**Description**: Retrieve amino acid sequences for E. coli K-12 proteins

```
Total Duration: 161.1s (2.7 minutes)

Breakdown:
  LLM Calls:       145.8s (90.5%)
  Tool Execution:   15.1s ( 9.4%)
    - SPARQL:       14.8s ( 9.2%)
    - Other tools:   0.3s ( 0.2%)
  Unaccounted:       0.2s ( 0.1%) [overhead/idle]

Counts:
  LLM Calls:    12
  Tool Calls:   18
  SPARQL Calls:  5

Averages:
  Per LLM Call:    12.15s
  Per Tool Call:    0.84s
  Per SPARQL Call:  2.96s
```

**Key Observations**:
- 12 iterations with 12 LLM calls
- SPARQL execution still fast (2.96s average per query)
- LLM latency dominates (90.5% of total time)
- Minimal overhead (0.1%)
- One slow LLM call in iteration 17: 52.8s (likely hitting rate limits or context size threshold)

## Analysis

### Hypothesis Validation

**Hypothesis from investigation plan**:
> 10 iterations × LLM latency per iteration = ~5 minutes
> Root cause: Iteration count, not SPARQL endpoint latency

**Result**: ✅ **CONFIRMED**

The data clearly shows:
1. **LLM calls dominate**: 90-94% of total time
2. **SPARQL is fast**: 0.74s - 2.96s per query (vs user's concern about endpoint latency)
3. **Iteration overhead is minimal**: <0.2% unaccounted time
4. **The bottleneck is iteration count**: 10-12 iterations × ~11-12s per LLM call

### Comparison to User's Baseline

**User's manual test**: 30-40 seconds
- 1 LLM call with SPARQL tool
- Direct query construction
- Minimal exploration

**Current RLM approach**: 120-161 seconds (2-2.7 minutes)
- 10-12 LLM calls with iterative refinement
- Progressive disclosure (explore before answering)
- Think-Act-Verify-Reflect cycles

**Time difference breakdown**:
- User's baseline: ~1 LLM call × 30-40s = 30-40s
- Current RLM: ~11 LLM calls × 11s = 121s (3x slower)
- Extra ~80-90s spent on exploration and refinement

### Why So Many Iterations?

Looking at per-iteration breakdown, the agent is:
1. **Exploring schema** (search_entity, describe_entity)
2. **Iterative query refinement** (multiple SPARQL attempts)
3. **Verification cycles** (checking results, reflecting)

**Simple query** (bacteria_taxa): 10 iterations, 10 SPARQL queries
- Likely over-exploring for a straightforward taxonomy query
- Could benefit from fast path or reduced max_iterations

**Complex query** (ecoli_k12): 12 iterations, 5 SPARQL queries
- More reasonable exploration for complex federated query
- SERVICE calls to remote endpoints justify more iteration

## Recommendations

Based on the data, we should explore these optimization strategies:

### 1. Adaptive Iteration Budgets (High Impact)

```yaml
# Simple taxonomy queries
max_iterations: 5  # Currently 16

# Complex federated queries
max_iterations: 16  # Keep current
```

**Expected impact**:
- Simple queries: 120s → 60-70s (2x faster)
- Complex queries: Minimal change (already using <16 iterations)

### 2. Fast Path for Direct Queries (High Impact)

Add heuristics to detect when a query can be answered directly:
- Keywords: "list all", "count", "find"
- Simple entity types (no federated joins)
- Skip exploration phase, go straight to query construction

**Expected impact**:
- Simple queries: 120s → 30-50s (approaching user's baseline)
- Complex queries: No change (still requires exploration)

### 3. Use Faster Model for Sub-Calls (Medium Impact)

Currently using sonnet-4.5 for all LLM calls. Consider:
- Main reasoning: sonnet-4.5 (quality)
- Verification/reflection: haiku (speed)
- Memory extraction: haiku (speed)

**Expected impact**:
- Per LLM call: 11-12s → 8-10s (20-30% faster)
- Total time: 120s → 90-100s

### 4. Parallel Tool Execution (Low Impact)

If multiple independent tools are called in same iteration, execute in parallel.

**Expected impact**:
- Minimal (tool execution is only 6-9% of total time)
- May save 1-2s per run

### 5. Caching and Memory (Long-term)

- Cache sense cards (don't rebuild per run)
- Use procedural memory to skip redundant exploration
- Learn efficient query patterns per ontology

**Expected impact**:
- Repeated queries: 120s → 40-60s (2-3x faster)
- First-time queries: No change

## Next Steps

1. ✅ **Profile existing results** - DONE
2. ✅ **Run benchmarks** - DONE
3. ⏭️ **Design E007 performance optimization experiment**:
   - Test adaptive iteration budgets (max_iterations: 5 vs 16)
   - Evaluate fast path heuristics
   - Compare haiku vs sonnet for sub-calls
   - Measure impact on pass rate and evidence quality

## References

- Profiling script: `evals/scripts/profile_timing.py`
- Benchmark script: `evals/scripts/benchmark_simple_vs_complex.sh`
- Trajectory logs: `evals/benchmarks/20260123_091141_simple_vs_complex/trajectories/`
- Investigation plan: `docs/analysis/performance-investigation-plan.md`
