# Performance Investigation Plan

**Context**: User reports 5-minute runtime for simple SPARQL queries, vs 30-40 seconds for manual test with simple tool use.

**Problem**: 10x slowdown needs investigation.

---

## Hypothesis: Where Time Is Being Spent

### Primary Suspects

1. **Iteration Overhead** (most likely)
   - 10-11 iterations × LLM latency per iteration
   - Each iteration: main LLM call + tool execution + result processing
   - If each iteration is 30s, 10 iterations = 5 minutes ✓

2. **Unnecessary Exploration**
   - Agent explores schema when it doesn't need to
   - Progressive disclosure cost: multiple small queries vs one direct query
   - For simple queries, this overhead may not be justified

3. **Context Building Overhead**
   - Loading/formatting sense cards
   - Memory retrieval
   - Each iteration rebuilds context

4. **Sub-LM Calls**
   - Meaning extraction sub-calls
   - Verification/reflection generation
   - Each may add latency

### Less Likely (but check)

5. **SPARQL Endpoint Latency**
   - User ruled this out (manual test was 30-40s)
   - But check if we're making redundant SPARQL calls

6. **Tool Call Overhead**
   - DSPy interpreter execution overhead
   - Python code execution in namespace

---

## Investigation Steps

### Step 1: Profile Current Runs

Use the profiling script to understand timing breakdown:

```bash
source ~/uvws/.venv/bin/activate

# Find a recent result with trajectory data
python evals/scripts/profile_timing.py \
  evals/experiments/E002_rung1_think_act_verify_reflect/cohorts/rung1_reasoning_fields/results/*.json

# Or run with trajectory logging enabled
python -m rlm_runtime.engine.dspy_rlm \
  --query "Select UniProtKB proteins for E. coli K12" \
  --ontology-path ontology/uniprot/core.ttl \
  --log-path trajectory.jsonl

python evals/scripts/profile_timing.py trajectory.jsonl --verbose
```

**Expected output:**
```
Total Duration: 300.0s (5.0 minutes)

Breakdown:
  LLM Calls:       180.0s (60.0%)  ← Main cost
  Tool Execution:   60.0s (20.0%)
    - SPARQL:       10.0s ( 3.3%)
    - Other tools:  50.0s (16.7%)
  Unaccounted:      60.0s (20.0%) [overhead/idle]

Per-Iteration Breakdown:
  Iter   Total     LLM       Tools     Events
  ------ -------- -------- -------- --------
  0       30.0s    20.0s    10.0s        5
  1       28.0s    18.0s    10.0s        4
  ...
```

### Step 2: Benchmark Simple vs Complex

Run controlled comparison:

```bash
chmod +x evals/scripts/benchmark_simple_vs_complex.sh
./evals/scripts/benchmark_simple_vs_complex.sh
```

**Questions to answer:**
- How many iterations for simple query?
- Does simple query explore unnecessarily?
- What's the LLM time vs tool time ratio?

### Step 3: Compare to Baseline (User's 30-40s Test)

Recreate user's simple approach:

```python
# User's approach (pseudo-code from description):
# 1. Load ontology + agent guide into context (~1000 tokens)
# 2. Single LLM call with SPARQL query tool
# 3. Execute query
# 4. Return results
# Total: 30-40 seconds

# What's different in our system:
# - Progressive disclosure (multiple iterations)
# - Bounded views (explore before answering)
# - Verification/reflection steps
# - Memory retrieval
```

---

## Potential Optimizations

### Option 1: Iteration Budget Tuning

If simple queries don't need exploration, reduce max_iterations:

```yaml
# Task definition
graders:
  - type: convergence
    max_iterations: 3  # Instead of 16 for simple queries
```

Or use adaptive budgets:
- Simple taxonomy queries: 3 iterations
- Complex federated queries: 16 iterations

### Option 2: Fast Path for Direct Queries

Add a "direct query" mode that skips exploration:

```python
# If query is simple and direct:
if is_simple_query(query):
    # Single-shot: load sense card, execute query, submit
    return direct_sparql_execution(query, ontology)
else:
    # Full RLM progressive disclosure
    return rlm_execution(query, ontology)
```

### Option 3: Reduce Context Building Overhead

- Cache sense cards (don't rebuild per iteration)
- Limit memory retrieval to first iteration only
- Reduce context size where possible

### Option 4: Parallelize Where Possible

- Run grading in parallel (don't block on LLM judge)
- Batch multiple SPARQL queries if pattern emerges

### Option 5: Use Faster Model for Sub-Calls

- Main reasoning: sonnet-4.5
- Verification/reflection: haiku (faster, cheaper)
- Memory extraction: haiku

---

## Decision Criteria

After profiling, make decisions based on timing breakdown:

### If 80%+ time is LLM calls:
→ **Problem is iteration count**, not tool overhead
→ Solutions: Reduce iterations for simple queries, fast path, or accept cost for quality

### If 50%+ time is tool execution:
→ **Problem is tool overhead** (unlikely based on user's test)
→ Solutions: Optimize tool implementations, reduce tool calls

### If 30%+ time is unaccounted overhead:
→ **Problem is framework overhead**
→ Solutions: Optimize DSPy/interpreter, reduce context building

### If SPARQL time is significant:
→ **Problem is endpoint latency** (user ruled this out)
→ Solutions: Caching, connection pooling

---

## Expected Findings

**Most likely scenario:**

```
Total: 300s
- LLM calls (10 iterations × 18s): 180s (60%)
- Tool execution: 60s (20%)
- Overhead: 60s (20%)

Root cause: 10 iterations for a simple query
```

**Recommendation:** Adaptive iteration budgets based on query complexity.

For simple taxonomy queries:
- Expected iterations: 2-3
- Target time: 60-90s
- Acceptable: <2 minutes

For complex federated queries:
- Expected iterations: 8-12
- Target time: 4-6 minutes
- Acceptable: <10 minutes

---

## Action Items

1. **Immediate:**
   - Run profiling script on E002 results
   - Document timing breakdown
   - Identify primary bottleneck

2. **Short-term:**
   - Run simple vs complex benchmark
   - Compare to user's baseline
   - Propose specific optimization based on findings

3. **Medium-term:**
   - Implement adaptive iteration budgets
   - Add fast path for simple queries
   - Add timing metrics to experiment framework

4. **Long-term:**
   - Optimize for common query patterns
   - Consider caching strategies
   - Evaluate cost vs quality tradeoffs

---

## References

- User observation: 5min runtime vs 30-40s baseline
- E002 results: 10-11 iterations average
- Profiling script: `evals/scripts/profile_timing.py`
- Benchmark script: `evals/scripts/benchmark_simple_vs_complex.sh`
