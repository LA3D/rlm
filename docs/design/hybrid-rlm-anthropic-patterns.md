# Hybrid RLM Architecture: Integrating Anthropic Agent Patterns

**Date**: 2026-01-28
**Status**: Design Proposal
**Context**: Current RLM doesn't use delegation strategically, losing Anthropic's multi-agent benefits

---

## Problem Statement

Our RLM testing revealed:

1. **No strategic delegation** - 0 llm_query calls despite 12 wasteful searches ($0.10 wasted)
2. **Cost regression on L3+** - $0.35 per query exceeds ReAct baseline ($0.27)
3. **Brute-force exploration** - Searches 'kinase' repeatedly instead of delegating once
4. **Lost Anthropic patterns** - Not using orchestrator, subagents, or clean handoffs

**The core issue**: We have llm_query (subagent mechanism) but no orchestrator teaching when/how to use it.

---

## What We're Doing Right (Keep These)

### ✅ Bounded Tools
- `search_entity` limited to 10 results
- `sparql_select` auto-injects LIMIT 100
- No raw graph access

**Anthropic principle**: "Context-aware design with sensible defaults"

### ✅ Just-in-Time Retrieval
- Start with sense card (~11K chars)
- Tools fetch data as needed
- Results accumulate in REPL

**Anthropic principle**: "Maintain lightweight identifiers, dynamically retrieve at runtime"

### ✅ Progressive Context Growth
- L1-L2: Grows 1.4K → 6K tokens
- L3: Grows 1.4K → 11K tokens
- Bounded accumulation

**Anthropic principle**: "Find the smallest set of high-signal tokens"

---

## What We're Missing (Add These)

### ❌ Orchestrator Pattern

**Current**: Single monolithic agent tries to solve everything directly

**Anthropic pattern**: "Lead agent analyzes, develops strategy, spawns subagents"

**What this means for RLM**:
```python
# Current (no orchestration):
search('kinase activity')  # fails
search('kinase')          # tries again
search('activity')        # tries again
# ... 9 more failed searches ...

# With orchestrator:
# THINK: "I need the GO term for 'kinase activity'. I've searched twice with no results.
#         This is a semantic concept, not a literal string in the ontology.
#         I should delegate to sub-LLM for disambiguation."
result = llm_query("What is the Gene Ontology (GO) term ID for kinase activity? Return only the GO ID.")
# → "GO:0016301"
search('GO:0016301')  # success on first try
```

**Implementation**: Add orchestration prompts teaching WHEN to delegate

---

### ❌ Subagent Task Specification

**Current**: llm_query exists but model never uses it

**Anthropic pattern**: "Each subagent needs objective, output format, guidance, boundaries"

**What this means for RLM**:
```python
# Current (if it were used):
llm_query("What is kinase activity?")  # vague, gets essay response

# With clear specification:
llm_query("""
Task: Find the GO term ID for 'kinase activity'
Output format: Just the GO ID (e.g., GO:0016301)
Sources: Use your knowledge of Gene Ontology
Boundaries: Return ONLY the ID, no explanation
""")
# → "GO:0016301"
```

**Implementation**: Template library for common delegation patterns

---

### ❌ Strategic Delegation Triggers

**Current**: Model never recognizes when to delegate

**Anthropic principle**: "If humans can't choose the right tool, agents can't either"

**Delegation triggers for RLM**:

| Situation | Should Delegate? | Why |
|-----------|-----------------|-----|
| **Semantic disambiguation** | ✅ YES | "kinase activity" → GO term mapping |
| **Concept translation** | ✅ YES | "human" → taxon:9606 |
| **Result filtering** | ✅ YES | "Which of these 20 properties are important?" |
| **Validation** | ✅ YES | "Is this SPARQL query correct?" |
| **Direct lookup** | ❌ NO | "What is the label of prov:Activity?" - use tools |
| **Graph exploration** | ❌ NO | "What subclasses exist?" - use SPARQL |

**Implementation**: Add explicit rules in system prompt

---

### ❌ Response Format Control

**Current**: Tools return everything, wasting tokens

**Anthropic principle**: "response_format parameter for concise vs detailed"

**What this means for RLM**:
```python
# Current:
search_entity('Protein')
# Returns: [{'uri': 'http://...', 'label': 'Protein', 'match_type': 'label_match', ...}]
# Full dict every time, ~100 tokens

# With response_format:
search_entity('Protein', response_format='concise')
# Returns: ['up:Protein']  # Just URI, 10 tokens

search_entity('Protein', response_format='detailed')
# Returns: Full dict when needed for downstream use
```

**Implementation**: Add response_format parameter to tools

---

### ❌ Structured Memory (Notes)

**Current**: Everything in REPL context (grows unbounded)

**Anthropic pattern**: "Persistent notes outside context window, retrieved as needed"

**What this means for RLM**:
```python
# Current:
# Iteration 1-12: All search results accumulate in REPL
# Total: 85K tokens by iteration 11

# With structured notes:
# Iteration 1-3: Search for concepts, write to notes
write_note('concepts_found', {
    'human': 'taxon:9606',
    'kinase_activity': 'GO:0016301',
    'reviewed': 'up:reviewed true'
})
# Iterations 4-10: Reference notes, not full history
concepts = read_note('concepts_found')
# Total: 40K tokens by iteration 11 (47% reduction)
```

**Implementation**: Add note-taking tools (write_note, read_note, list_notes)

---

### ❌ Compaction for Long Queries

**Current**: Context grows unbounded until failure

**Anthropic pattern**: "Summarize and create new windows with compressed details"

**What this means for RLM**:
```python
# Current (L3-2):
# Iteration 11: 85K tokens, 14 SPARQL queries in history

# With compaction:
# Iteration 6: Check if context > 50K
if context_size > 50000:
    summary = llm_query("""
    Summarize findings so far:
    - Concepts identified
    - Key relationships found
    - What still needs exploration
    Keep under 2000 tokens.
    """)
    # Clear old tool results, keep summary
    compact_context(keep_summary=summary)
# Iteration 11: 45K tokens (47% reduction)
```

**Implementation**: Automatic compaction at token threshold

---

### ❌ Parallel Execution

**Current**: Sequential tool calls

**Anthropic pattern**: "3-5 subagents concurrently + 3+ tool calls simultaneously"

**What this means for RLM**:
```python
# Current:
search_entity('disease')    # 2s
search_entity('enzyme')     # 2s
search_entity('mitochondria') # 2s
# Total: 6 seconds sequential

# With parallelization:
results = parallel_execute([
    lambda: search_entity('disease'),
    lambda: search_entity('enzyme'),
    lambda: search_entity('mitochondria')
])
# Total: 2 seconds (3x faster)
```

**Implementation**: Batch tool execution in DSPy RLM

---

### ❌ Better Error Messages

**Current**: Generic errors or silent failures

**Anthropic principle**: "Actionable guidance, not opaque error codes"

**What this means for RLM**:
```python
# Current:
search_entity('kinase activity')
# Returns: []  # Empty, no guidance

# With actionable errors:
search_entity('kinase activity')
# Returns: {
#   'results': [],
#   'suggestion': 'No exact matches. Try: 1) Search for "kinase" alone, '
#                 '2) Use llm_query to find GO term, or 3) Check AGENT_GUIDE.md examples'
# }
```

**Implementation**: Enhance tool return values with guidance

---

### ❌ Tool Consolidation

**Current**: Minimal tools (2), which is good, but descriptions could be better

**Anthropic principle**: "Consolidate related operations, don't expose raw APIs"

**What we could improve**:
```python
# Current (good minimalism):
- search_entity
- sparql_select

# Possible additions (if needed):
- find_concept: Combines search + llm_query disambiguation
- validate_query: Checks SPARQL syntax + logic
- lookup_example: Searches AGENT_GUIDE.md for patterns

# Keep minimal - only add if delegation alone can't solve it
```

---

## Proposed Hybrid Architecture

### Layer 1: Orchestrator (Main RLM Agent)

**Role**: Strategic planning and delegation decisions

**Prompt additions**:
```markdown
## Delegation Strategy

When solving queries, follow this decision tree:

1. **Check AGENT_GUIDE.md first** - Look for examples
2. **Try direct tools** (1-2 attempts max):
   - search_entity for entity discovery
   - sparql_select for graph queries
3. **Delegate to subagent** if:
   - Semantic disambiguation needed (concept → URI)
   - Multiple failed searches (> 2 attempts)
   - Result filtering needed (> 10 options)
   - Validation needed (check query correctness)

### Delegation Template

Use llm_query with clear specification:
```python
result = llm_query(\"\"\"
Task: [specific objective]
Output: [exact format needed]
Context: [relevant info from tools]
\"\"\")
```

### Cost Awareness

- Each search costs ~$0.01
- Each llm_query costs ~$0.005 (Haiku)
- **3+ searches = delegation would be cheaper**
```

---

### Layer 2: Subagents (llm_query calls)

**Role**: Focused semantic analysis tasks

**Standard patterns**:

#### Pattern 1: Concept Disambiguation
```python
llm_query("""
Task: Map concept to ontology identifier
Concept: [user term, e.g., "kinase activity"]
Ontology: [e.g., Gene Ontology]
Output: Just the identifier (e.g., GO:0016301)
""")
```

#### Pattern 2: Result Filtering
```python
llm_query("""
Task: Select most relevant items
Items: [list from tool call]
Criteria: [e.g., "most important properties for defining this class"]
Output: Top 5 items with brief justification
""")
```

#### Pattern 3: Query Validation
```python
llm_query("""
Task: Check SPARQL query correctness
Query: [constructed SPARQL]
Schema: [from tools]
Output: Valid/Invalid + specific fixes if invalid
""")
```

#### Pattern 4: Summary Generation
```python
llm_query("""
Task: Summarize findings for compaction
History: [last N tool calls]
Output: Key facts in under 500 tokens
""")
```

---

### Layer 3: Enhanced Tools

**Updated tool signatures**:

```python
def search_entity(
    query: str,
    limit: int = 5,
    search_in: str = 'all',
    response_format: str = 'standard'  # NEW: 'standard' | 'concise' | 'detailed'
) -> list | dict:
    """Search for entities with format control.

    response_format:
    - 'concise': Returns just URIs ['up:Protein', 'up:Gene']
    - 'standard': Returns dicts with uri, label, match_type
    - 'detailed': Returns full metadata (use for downstream tools)
    """
```

```python
def sparql_select(
    query: str,
    max_results: int = 100,
    explain: bool = False  # NEW: Return query plan
) -> list | dict:
    """Execute SPARQL with optional explanation.

    explain: If True, returns:
    {
        'results': [...],
        'plan': 'This query finds...',
        'performance': {'triples_matched': 45, 'time_ms': 12}
    }
    """
```

**New tools (minimal additions)**:

```python
def write_note(key: str, content: str) -> str:
    """Store information outside main context.

    Use for: Discovered concepts, key findings, partial results
    Stored in: Session memory (retrieved via read_note)
    """

def read_note(key: str) -> str:
    """Retrieve stored note by key."""

def list_notes() -> list[str]:
    """List all note keys in current session."""
```

---

### Layer 4: Memory & Compaction

**Automatic compaction**:
```python
if context_tokens > 50000:
    # Summarize via subagent
    summary = llm_query("""
    Task: Compact context for continuation
    Include: Key findings, concepts identified, remaining questions
    Exclude: Failed attempts, redundant tool outputs
    Output: Under 2000 tokens
    """)

    # Clear old context, inject summary
    context.compact(keep=summary)
```

**Note-based persistence**:
```python
# Iteration 3: Store findings
write_note('concepts', json.dumps({
    'human': 'taxon:9606',
    'kinase': 'GO:0016301'
}))

# Iteration 8: Retrieve without full history
concepts = json.loads(read_note('concepts'))
```

---

## Implementation Phases

### Phase 1: Orchestrator Prompting (Week 1)

**Changes**:
- Add delegation strategy section to system prompt
- Add delegation pattern templates
- Add cost awareness guidance

**Test**: Re-run L3-1 query, expect llm_query usage

**Success metric**: ≥1 delegation attempt, cost < $0.20

---

### Phase 2: Enhanced Tool Returns (Week 1-2)

**Changes**:
- Add response_format parameter to tools
- Add actionable error messages
- Add suggestions in empty results

**Test**: Compare token usage with/without concise mode

**Success metric**: 20% token reduction with response_format='concise'

---

### Phase 3: Structured Memory (Week 2)

**Changes**:
- Implement write_note, read_note, list_notes
- Add automatic note suggestion in prompts

**Test**: Long-running queries with context compaction

**Success metric**: Handle 15+ iteration queries without failure

---

### Phase 4: Parallel Execution (Week 3)

**Changes**:
- Batch tool calls in DSPy RLM
- Parallel llm_query calls for independent tasks

**Test**: Multi-entity queries with concurrent searches

**Success metric**: 2-3x speedup on multi-search queries

---

### Phase 5: Subagent Templates (Week 3-4)

**Changes**:
- Create delegation pattern library
- Add pattern matching in system prompt

**Test**: Diverse L3-L4 queries

**Success metric**: 80% of queries use appropriate delegation pattern

---

## Expected Improvements

### Cost Reduction

**L3-1 query** (before):
- 12 search attempts: $0.12
- 6 SPARQL queries: $0.10
- Context growth: $0.05
- **Total: $0.27**

**L3-1 query** (after, with delegation):
- 2 search attempts: $0.02
- 1 llm_query (disambiguation): $0.01
- 6 SPARQL queries: $0.10
- Context growth (compacted): $0.03
- **Total: $0.16** (41% reduction)

---

### Convergence Rate

**Current**:
- L1-L2: 100% converge in 5-7 iterations
- L3: 50% converge in 15 iterations

**Target**:
- L1-L2: 100% converge in 4-5 iterations (delegation for synthesis)
- L3: 90% converge in 8-10 iterations (strategic delegation)
- L4-L5: 80% converge in 12-15 iterations (heavy delegation)

---

### Quality Metrics

**Current**:
- Answers comprehensive but verbose
- Some incorrect concept mappings
- Brute-force exploration visible

**Target**:
- Concise, focused answers
- Correct concept mappings (via delegation)
- Strategic exploration visible in reasoning

---

## Comparison to Pure Patterns

### vs Current RLM (Tool-First Only)

| Aspect | Current | Hybrid | Change |
|--------|---------|--------|--------|
| **Cost L3** | $0.27-0.35 | $0.16-0.20 | -41% |
| **Delegation** | 0% | 60-80% | +strategic |
| **Convergence L3** | 50% | 90% | +40% |
| **Speed** | 120s | 80s | -33% |

---

### vs Pure ReAct

| Aspect | ReAct | Hybrid RLM | Advantage |
|--------|-------|-----------|-----------|
| **Cost L1-L2** | $0.27 | $0.12 | RLM 2x cheaper |
| **Cost L3** | $0.27 | $0.16-0.20 | RLM 26-41% cheaper |
| **Delegation** | N/A | Strategic | RLM more flexible |
| **Context growth** | Large upfront | Progressive | RLM more efficient |

---

### vs Pure Delegation (Prime Intellect)

| Aspect | Prime Intellect | Hybrid RLM | Advantage |
|--------|-----------------|-----------|-----------|
| **Domain** | Unstructured docs | Structured RDF | Different needs |
| **Delegation** | Heavy (required) | Strategic (optional) | RLM adapts |
| **Tools** | Document-focused | Ontology-focused | Domain-specific |
| **Cost** | Not reported | $0.12-0.20 | RLM measured |

---

## Key Architectural Principles

### 1. Orchestrator Decides, Subagents Execute

**Main agent**: Strategic thinking, delegation decisions, synthesis
**Subagents**: Focused tasks with clear objectives and output formats

### 2. Progressive Disclosure with Strategic Shortcuts

**Keep**: Just-in-time retrieval, bounded tools
**Add**: Delegation shortcuts when exploration fails

### 3. Context as Finite Resource

**Techniques**:
- response_format for token control
- Structured notes outside context
- Automatic compaction at thresholds
- Subagent summaries (not full histories)

### 4. Clear Handoff Protocols

**Delegation spec**:
```
Task: [what]
Output: [format]
Context: [relevant info]
Boundaries: [constraints]
```

**Return spec**:
```
{
  'result': [answer],
  'confidence': 0.95,
  'reasoning': 'brief justification'
}
```

### 5. Tool Design Follows Signal-Over-Flexibility

- response_format parameter (concise by default)
- Actionable error messages
- Semantic fields over low-level IDs
- Consolidated operations over raw APIs

---

## Implementation Risks

### Risk 1: Over-Delegation

**Concern**: Model delegates everything, losing cost benefits

**Mitigation**:
- Clear delegation triggers (3+ failed searches)
- Cost awareness in prompts
- Monitor delegation rate per query type

---

### Risk 2: Prompt Complexity

**Concern**: Adding orchestration makes prompts too long

**Mitigation**:
- Keep delegation section under 500 tokens
- Use examples > rules
- Test minimal version first

---

### Risk 3: Coordination Overhead

**Concern**: Subagent handoffs add latency

**Mitigation**:
- Use Haiku for fast subagent responses
- Parallel execution where possible
- Cache common delegations

---

## Success Criteria

### Minimum Viable Hybrid (Phase 1-2)

- ✅ At least 1 delegation per L3 query
- ✅ L3 cost < $0.20 (vs current $0.27-0.35)
- ✅ 80% convergence on L3 queries
- ✅ response_format reduces tokens 20%

### Full Hybrid (Phase 3-5)

- ✅ Strategic delegation (60-80% of L3-L4 queries)
- ✅ L3 cost $0.16-0.20 (41% reduction)
- ✅ 90% convergence on L3, 80% on L4
- ✅ Context compaction enables 20+ iteration queries
- ✅ Parallel execution 2-3x faster on multi-entity queries

---

## Next Steps

1. **Read Anthropic articles** ✅ (completed)
2. **Design hybrid architecture** ✅ (this document)
3. **Implement Phase 1** (orchestrator prompting)
4. **Test on L3-1 query** (expect delegation)
5. **Iterate based on results**

---

## Related Documents

- Current behavior: `docs/analysis/reasoning-test-results-partial.md`
- RLM execution: `docs/analysis/rlm-execution-deep-dive.md`
- L1-L2 baseline: `docs/analysis/rlm-behavior-l1-l2-queries.md`

**Last Updated**: 2026-01-28
