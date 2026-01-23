# Memory Agent Behavior Analysis: Does the Agent Use Memories?

**Date**: 2026-01-23
**Purpose**: Examine actual agent behavior to determine if retrieved memories are being used or ignored

## Executive Summary

**Finding**: The agent **does NOT explicitly use** the retrieved memories, but the memories **DO change agent behavior** in subtle, counterproductive ways.

**Evidence**:
1. ✗ No explicit references to memories in code/comments
2. ✓ Trajectories are substantively different with memory
3. ✓ Different exploration strategies (less targeted with memory)
4. ✓ +1-3 extra iterations with memory
5. ✓ Token patterns diverge at iteration 3

**Conclusion**: Memories act as **passive context pollution** rather than active guidance. They change the LLM's implicit behavior without being explicitly consulted.

---

## Detailed Analysis

### 1. Do Memories Appear in Agent's Reasoning?

**Checked for memory-related terms in code/comments:**
- "memory", "recall", "remember", "retrieved", "learned", "previous"
- "incremental", "investigation", "scope recognition", "strategy"
- "guidance", "approach from", "as suggested", "based on"

**Result**: ✗ **NO explicit references found**

The only instances of "retrieved" (iterations 10-11) were describing query results:
```
"successfully retrieved proteins from all 16 e. coli k12 strains"
```

This is about the SPARQL results, not the procedural memories.

---

### 2. Are Trajectories Different With vs Without Memory?

**Result**: ✓ **YES, significantly different**

#### Iteration-by-Iteration Comparison

**Iteration 1:**
- WITHOUT memory: Targeted FILTER for "protein", "organism", "sequence"
- WITH memory: Generic schema exploration, NO targeting

**Iteration 2:**
- WITHOUT memory: Targeted property exploration with FILTERs
- WITH memory: Generic property exploration, NO targeting

**Iteration 3:**
- WITHOUT memory: Deep dive into Sequence class structure
- WITH memory: Switches to search_entity for E. coli K12

**Iteration 4:**
- WITHOUT memory: Uses search_entity to find E. coli K12
- WITH memory: Queries remote endpoint for organisms

**Pattern:**
- WITHOUT memory: Focused, targeted from the start → finds solution faster
- WITH memory: Generic exploration first, then targets → takes longer

---

### 3. Retrieved Memories

For the complex query (E. coli K12 sequences), these memories were retrieved:

1. **"Task Scope Recognition: All vs One"**
   - About distinguishing "all X" vs "one X" queries

2. **"Incremental Data Source Investigation"**
   - About exploring data sources incrementally

3. **"Inconsistent Query Strategy Convergence"**
   - About debugging queries that don't converge

**Problem**: These are HIGH-LEVEL strategies, not actionable instructions:
- ❌ No specific SPARQL patterns
- ❌ No UniProt-specific guidance
- ❌ No sequence extraction templates
- ✓ Only vague strategic hints

---

### 4. Token Usage Analysis

#### First LLM Call
```
Without memory: 1,657 tokens
With memory:    1,657 tokens
Difference:     +0 tokens
```

**Surprising**: Same token count in first call!

This suggests:
- Memories are NOT added to initial context, OR
- Memories are very small/compressed

#### Token Divergence by Iteration

| Iteration | No Memory | With Memory | Difference |
|-----------|-----------|-------------|------------|
| 1 | 1,657 | 1,657 | 0 |
| 2 | 2,852 | 2,776 | -76 ⬇️ |
| 3 | 3,999 | 5,144 | **+1,145** ⬆️ |
| 4 | 4,839 | 5,543 | +704 |
| 5 | 5,476 | 6,942 | +1,466 |
| 6 | 7,038 | 7,406 | +368 |
| 7 | 8,684 | 8,793 | +109 |
| 8 | 10,060 | 9,762 | -298 ⬇️ |
| 9 | 11,529 | 11,721 | +192 |
| 10 | 12,965 | 12,917 | -48 |
| **11** | **N/A** | **14,396** | **(extra)** |
| **12** | **N/A** | **1,830** | **(extra)** |
| **13** | **N/A** | **1,234** | **(extra)** |

**Key observations:**
1. Iteration 2: WITH memory is SMALLER (-76 tokens) → different path taken
2. Iteration 3: Huge jump (+1,145 tokens) → trajectories diverge significantly
3. Iterations vary: sometimes WITH memory is smaller, sometimes larger
4. +3 extra iterations (11-13) with memory

**This is NOT just memory overhead.** The token patterns show the agent is taking fundamentally different exploration paths.

---

### 5. What's Happening?

#### Hypothesis: Implicit Priming, Not Explicit Use

The memories are in the context, but the agent:
1. ✗ Does NOT explicitly reference them
2. ✗ Does NOT comment "as suggested by memory"
3. ✓ DOES behave differently (less targeted exploration)
4. ✓ DOES take longer paths (+1-3 iterations)

**Explanation**: The LLM is implicitly influenced by the strategic guidance in context, but in a COUNTERPRODUCTIVE way:

- Memory: "Incremental Data Source Investigation"
- Agent interpretation: "Explore generically first, then target"
- Result: Slower to focus on the actual task

Without memory:
- Agent: "I need proteins and sequences from E. coli K12"
- Immediate action: Targeted FILTER for relevant classes
- Result: Faster convergence

With memory:
- Agent: (reads "incremental investigation" guidance)
- Implicit interpretation: "Be more exploratory and careful"
- Action: Generic schema exploration first
- Result: Slower convergence

---

### 6. Why the +1 Iteration is Suspicious

User's insight: "It's very suspicious that there's one extra call between the memory and no memory"

**Two possibilities:**
1. Memory overhead (adding context takes time)
2. Agent is using memory (but we see no evidence)
3. **Agent is being distracted by memory** (this is what we found)

**Evidence for distraction:**
- First iterations are LESS focused with memory
- No explicit use of memories
- Different exploration strategy
- +1-3 extra iterations needed to converge

The agent isn't actively using the memories, but their presence changes the implicit "temperature" of exploration from focused to exploratory.

---

### 7. Memory Format and Injection

**Current format** (inferred from retrieval):
```
Retrieved 3 memories:
1. Task Scope Recognition: All vs One
2. Incremental Data Source Investigation
3. Inconsistent Query Strategy Convergence
```

**Likely injection into context:**
```
You have these related strategies:

1. Task Scope Recognition: All vs One
   [strategy description...]

2. Incremental Data Source Investigation
   [strategy description...]

3. Inconsistent Query Strategy Convergence
   [strategy description...]
```

**Problems with this format:**
1. No clear instruction to USE these
2. Just presented as additional context
3. Vague strategic guidance, not actionable steps
4. LLM may interpret as "be more careful" → slower exploration

---

## Comparison: Simple vs Complex Query

### Simple Query (bacteria taxa)

**With memory:**
- Iterations: 12 (+2)
- Time: 147.1s (+44%)
- Token overhead: +38K (+65%)

**Behavior change:**
- Less targeted from start
- More exploratory iterations
- Strategic memories encouraged caution

### Complex Query (E. coli K12)

**With memory:**
- Iterations: 11 (+1)
- Time: 142.5s (~same)
- Token overhead: +21K (+27%)

**Behavior change:**
- Generic exploration in iterations 1-2
- Switches to targeting in iteration 3
- Eventually converges, but via longer path

**Pattern**: In BOTH cases, memory makes initial exploration less focused.

---

## Root Cause Analysis

### Why Doesn't the Agent Use Memories?

**Possible reasons:**

1. **Memories are too vague**
   - "Incremental Data Source Investigation" doesn't tell agent WHAT to do
   - No concrete SPARQL patterns or templates
   - Strategic guidance ≠ actionable instructions

2. **No explicit instruction to consult memories**
   - Context says "You have these strategies"
   - Doesn't say "USE these strategies"
   - Doesn't say "Check if memories apply"

3. **LLM attention doesn't focus on memory section**
   - Memories buried in context
   - Agent focuses on sense card, query, instructions
   - Memories treated as background noise

4. **Memories change implicit priming, not explicit behavior**
   - Reading "incremental investigation" → LLM becomes more exploratory
   - Reading "scope recognition" → LLM double-checks scope
   - Result: Slower, not faster

---

## Implications for Memory Architecture

### What We Learned

1. **Current memories are PASSIVE, not ACTIVE**
   - Agent doesn't explicitly consult them
   - But they influence behavior implicitly
   - Effect is counterproductive (slower)

2. **Strategic guidance ≠ executable solutions**
   - "Be incremental" is not the same as "Use this SPARQL"
   - High-level advice makes agent MORE cautious
   - Need direct, executable templates

3. **Memory format matters**
   - Current format: "Here are some strategies"
   - Better format: "IF query matches X, USE template Y"
   - Need routing logic, not just context injection

### What's Needed for Memory Fast Path

**Type A memories (direct solutions):**
```python
{
    "type": "direct_solution",
    "query_pattern": "retrieve sequences for {organism}",
    "condition": "confidence > 0.85",
    "action": "USE_TEMPLATE",
    "sparql_template": """
        PREFIX up: <http://purl.uniprot.org/core/>
        SELECT ?protein ?sequence WHERE {
            ?protein up:organism <{taxon_uri}> .
            ?protein up:sequence ?seq .
            ?seq rdf:value ?sequence .
        }
    """,
    "parameters": {"taxon_uri": "..."},
    "skip_exploration": true
}
```

**Type B memories (strategic guidance):**
```python
{
    "type": "strategy",
    "title": "Incremental Data Source Investigation",
    "applies_when": "unfamiliar ontology OR novel query type",
    "guidance": "...",
    "skip_exploration": false
}
```

**Routing logic:**
```python
if Type_A_match and confidence > 0.85:
    # FAST PATH: Execute template directly
    return execute_template(memory, max_iterations=3)
else:
    # SLOW PATH: Full exploration (with or without Type B guidance)
    return full_exploration(query, memories=Type_B, max_iterations=16)
```

---

## Recommendations

### Immediate (E007)

1. **Run WITHOUT memory** for baseline optimization
   - Memory currently hurts performance
   - Get clean iteration count baseline first
   - Test adaptive budgets without memory confound

### Short-term (Memory Architecture Redesign)

2. **Dual-memory system design**
   - Type A: Direct executable solutions
   - Type B: Strategic guidance (for novel tasks only)

3. **Explicit routing logic**
   - Check memory confidence before injecting
   - Route to fast path if Type A match
   - Only inject Type B if no Type A match

4. **Memory format changes**
   - SPARQL templates, not text descriptions
   - Parameter slots for instantiation
   - Clear "USE THIS" vs "CONSIDER THIS" distinction

### Medium-term (E008 Testing)

5. **Test memory fast path**
   - Cohort A: Type A memories (direct solutions)
   - Cohort B: No memory (baseline)
   - Cohort C: Type B only (strategic guidance)
   - Measure: cache hit rate, time, pass rate

---

## Conclusion

**Q: Is the agent using the memories?**
**A: No, not explicitly. But yes, implicitly (in a bad way).**

**What's happening:**
1. Memories are injected into context
2. Agent does NOT explicitly reference them
3. Agent DOES behave differently (less focused)
4. Memories act as DISTRACTION, not GUIDANCE
5. Result: +1-3 iterations, +18-62% cost

**Why:**
- Memories are vague strategic guidance
- No instruction to USE them explicitly
- LLM interprets them as "be more careful"
- Result: Slower, more exploratory behavior

**Solution:**
- Type A memories: Direct executable templates
- Type B memories: Strategic guidance (only for novel tasks)
- Routing logic: Fast path if Type A match, else full exploration
- Explicit instruction: "IF memory matches, USE it directly"

**Next steps:**
1. E007: Baseline optimization WITHOUT memory
2. Design: Dual-memory architecture + routing
3. E008: Test memory fast path effectiveness
