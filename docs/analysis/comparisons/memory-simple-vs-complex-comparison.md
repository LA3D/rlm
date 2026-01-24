# Memory Impact: Simple vs Complex Query Comparison

**Date**: 2026-01-23
**Purpose**: Understand if ReasoningBank helps more on complex queries vs simple queries

## TL;DR

**Memory doesn't help either query type with current architecture:**
- Simple query: +44% slower with memory
- Complex query: Same time, but +18% more expensive

**Root cause remains the same:** Memories are strategic guidance, not executable solutions.

---

## Simple Query: Bacteria Taxa

**Query**: "Select all bacterial taxa and their scientific name from UniProt"
**Complexity**: Simple taxonomy lookup, should be answerable in 2-3 iterations

### Performance Comparison

| Metric | Without Memory | With Memory | Change |
|--------|----------------|-------------|--------|
| **Time** | 102.5s | 147.1s | +44% ⬆️ |
| **Iterations** | 10 | 12 | +20% ⬆️ |
| **LLM calls** | 10 | 14 | +40% ⬆️ |
| **Tool calls** | 18 | 31 | +72% ⬆️ |
| **SPARQL calls** | 5 | 8 | +60% ⬆️ |
| **Total tokens** | 59,269 | 97,572 | +65% ⬆️ |
| **Avg prompt** | 5,414 | 6,412 | +18% ⬆️ |
| **Cost** | $0.24 | $0.39 | +62% ⬆️ |

### Retrieved Memories (Simple)
1. "Task Scope Recognition: All vs One"
2. "Taxonomic Entity Resolution Strategy"
3. "Taxonomic Data Extraction Protocol"

### Analysis
Memory **significantly hurt** performance:
- Much slower (+44s)
- Many more operations (tools/queries)
- Much more expensive (+62%)

---

## Complex Query: E. coli K12 Sequences

**Query**: "Retrieve the amino acid sequences for all proteins of Escherichia coli K-12"
**Complexity**: Requires federated query with SERVICE/GRAPH, sequence extraction, multiple steps

### Performance Comparison

| Metric | Without Memory | With Memory | Change |
|--------|----------------|-------------|--------|
| **Time** | 144.1s | 142.5s | -1% ≈ same |
| **Iterations** | 10 | 11 | +10% ⬆️ |
| **LLM calls** | 10 | 13 | +30% ⬆️ |
| **Tool calls** | 16 | 17 | +6% ⬆️ |
| **SPARQL calls** | 4 | 5 | +25% ⬆️ |
| **Total tokens** | 77,096 | 97,856 | +27% ⬆️ |
| **Avg prompt** | 6,910 | 6,932 | +0.3% ⬆️ |
| **Cost** | $0.33 | $0.39 | +18% ⬆️ |

### Retrieved Memories (Complex)
1. "Task Scope Recognition: All vs One"
2. "Incremental Data Source Investigation"
3. "Inconsistent Query Strategy Convergence"

### Analysis
Memory had **minimal time impact but increased cost**:
- Same execution time (142s vs 144s)
- More LLM calls needed (+3)
- More expensive (+18%)
- No iteration reduction benefit

---

## Key Findings

### 1. Memory Doesn't Reduce Iterations for Either Type

**Simple query:**
- Without memory: 10 iterations
- With memory: 12 iterations (+2)

**Complex query:**
- Without memory: 10 iterations
- With memory: 11 iterations (+1)

**In both cases, memory INCREASED iterations instead of reducing them.**

### 2. Memory Always Increases Cost

| Query Type | Cost Without | Cost With | Increase |
|------------|--------------|-----------|----------|
| Simple | $0.24 | $0.39 | +62% |
| Complex | $0.33 | $0.39 | +18% |

### 3. Memory Overhead is Consistent Across Complexity

**Token overhead:**
- Simple: +38K tokens (+65%)
- Complex: +21K tokens (+27%)

**Both show significant token overhead from memory context.**

### 4. Complex Queries Don't Benefit More from Memory

Hypothesis: "Complex queries might benefit more from strategic guidance"

**Result:** ❌ Complex queries show NO time benefit
- Simple: +44s slower with memory
- Complex: ~same time with memory (but +18% cost)

Neither benefits from current memory architecture.

---

## Why Memory Doesn't Help Complex Queries Either

### Retrieved Memories Are Still Strategic, Not Executable

**Complex query memories:**
1. "Task Scope Recognition: All vs One" — scope clarification strategy
2. "Incremental Data Source Investigation" — exploration approach
3. "Inconsistent Query Strategy Convergence" — debugging guidance

**These are meta-strategies, not solutions:**
- ❌ No direct SPARQL template for E. coli K12
- ❌ No federated query pattern
- ❌ No sequence extraction template
- ✓ General advice on "how to think about the problem"

**Agent still has to explore from scratch,** just with extra context suggesting exploration strategies.

### The Complex Query Already Knows What to Do

At 10 iterations WITHOUT memory, the complex query is already:
- Efficient enough for its complexity
- Finding the right SERVICE/GRAPH patterns
- Successfully extracting sequences

Adding strategic memories doesn't help because:
1. **It already has an effective exploration strategy** (baseline Think-Act-Verify-Reflect)
2. **Strategic hints don't accelerate execution** — it still needs to explore ontology, test queries, verify results
3. **Extra context adds token overhead** — slows down LLM calls without providing shortcuts

---

## User's Observation About Prior Memory Success

> "Memory was working in reducing iterations between cold start and succeeding on complex operations"

**Possible explanations for past success:**
1. **Different memory content** — perhaps memories contained more direct solutions then
2. **Different task types** — perhaps previous tasks had exact-match memories
3. **Learning curve effect** — cold start → second attempt showed improvement, attributed to memory but might be model variance
4. **Different memory injection strategy** — perhaps memories were formatted differently

**Need to investigate:**
- What was in the memory bank during successful runs?
- What types of tasks showed iteration reduction?
- Were memories more task-specific then?

---

## Architectural Requirements for Memory Fast Path

Based on both simple and complex query analysis, a memory fast path needs:

### 1. Two Types of Memories

**Type A: Direct Task Solutions** (for fast path)
- Exact SPARQL templates for common queries
- Parameterized patterns (e.g., "bacteria taxa" → template)
- Confidence threshold: >0.8 for direct use
- Example structure:
  ```json
  {
    "type": "direct_solution",
    "query_pattern": "retrieve sequences for [organism]",
    "sparql_template": "SELECT ?seq WHERE { GRAPH <...> { ... } }",
    "parameters": ["organism_taxon"],
    "success_rate": 0.95
  }
  ```

**Type B: Strategic Guidance** (for novel tasks)
- High-level problem-solving approaches
- Used when no Type A match exists
- Current memories are all Type B
- Example: "Incremental Data Source Investigation"

### 2. Confidence-Based Routing

```python
memories = retrieve(query, k=3)
top_memory = memories[0]

if top_memory.type == "direct_solution" and top_memory.confidence > 0.8:
    # FAST PATH: Use template directly
    sparql = instantiate_template(top_memory, query)
    result = execute_and_verify(sparql, max_iterations=3)
else:
    # SLOW PATH: Full exploration with strategic guidance
    context = build_context(sense_card, memories, meta)
    result = rlm.run(query, context, max_iterations=16)
```

### 3. Memory Structure Changes

**Current structure** (strategies only):
```python
{
    "memory_id": "mem-001",
    "title": "Taxonomic Entity Resolution Strategy",
    "content": "When resolving taxonomic entities...",
    "tags": ["taxonomy", "strategy"]
}
```

**Proposed structure** (with solution templates):
```python
{
    "memory_id": "mem-001",
    "type": "direct_solution",  # or "strategy"
    "title": "E. coli K12 Sequence Retrieval",
    "query_pattern": "retrieve sequences for {organism}",
    "sparql_template": "...",
    "parameters": {"organism": "Escherichia coli K-12"},
    "success_rate": 0.95,
    "avg_iterations": 2,
    "tags": ["sequences", "organism-specific"]
}
```

---

## Recommendations

### Immediate (E007 Baseline Optimization)

1. **Run E007 WITHOUT memory**
   - Establish clean baseline for iteration reduction
   - Test adaptive iteration budgets (5 vs 16)
   - Measure: pass rate, time, cost, evidence quality

2. **Document baseline behavior**
   - Simple queries: How low can we get iterations? (target: 3-5)
   - Complex queries: What's reasonable? (target: 8-12)

### Short-term (Memory Architecture Redesign)

3. **Design dual-memory system**
   - Type A: Direct solutions (SPARQL templates)
   - Type B: Strategic guidance (current memories)

4. **Implement confidence-based routing**
   - High confidence + Type A → fast path (2-3 iterations)
   - Low confidence or Type B → full exploration

5. **Create memory curation process**
   - Convert successful trajectories to Type A memories
   - Extract SPARQL templates with parameters
   - Build confidence scoring based on success rate

### Medium-term (E008 Memory Fast Path Experiment)

6. **Test memory fast path effectiveness**
   - Cohort A: Memory fast path (with Type A memories)
   - Cohort B: Full exploration (no memory)
   - Cohort C: Strategic guidance only (current memory behavior)

7. **Measure**:
   - Cache hit rate (how often Type A matches?)
   - Time on cache hits vs misses
   - Pass rate (does fast path maintain quality?)
   - Cost efficiency

---

## Summary Table

| Aspect | Simple Query | Complex Query | Conclusion |
|--------|--------------|---------------|------------|
| **Time impact** | +44% slower | ~same | Memory hurts simple, neutral for complex |
| **Cost impact** | +62% more | +18% more | Memory always increases cost |
| **Iteration impact** | +2 iterations | +1 iteration | Memory increases iterations |
| **Memory type** | Strategic guidance | Strategic guidance | Both get same type of memories |
| **Benefit** | ❌ None | ❌ None | Neither benefits from current memory |

**Universal problem:** Current memory provides strategic guidance (extra context), not executable solutions (cache benefit).

**Path forward:** Design dual-memory architecture with fast path routing.

---

## Next Steps

1. ✅ Documented memory impact on simple query
2. ✅ Documented memory impact on complex query
3. ⏭️ **Run E007 without memory** (baseline iteration optimization)
4. ⏭️ **Design dual-memory architecture** (Type A + Type B)
5. ⏭️ **Create E008 memory fast path experiment**

## Open Questions

1. **What was in memory during previous successful runs?**
   - Need to investigate past success stories
   - Were memories more task-specific then?

2. **What's the optimal cache hit threshold?**
   - Confidence > 0.8? 0.9?
   - How to measure confidence for SPARQL templates?

3. **How to curate Type A memories?**
   - Automated extraction from successful trajectories?
   - Manual curation?
   - Hybrid approach?

4. **Memory pack design:**
   - Should Type A and Type B be separate packs?
   - Version control for memory evolution?
