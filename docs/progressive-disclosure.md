# Progressive Disclosure in Recursive Language Models

This document explores how RLMs implement progressive disclosure—a core context engineering pattern identified by Anthropic for effective AI agents.

## What is Progressive Disclosure?

Progressive disclosure is a context engineering strategy where agents **incrementally discover relevant context through exploration** rather than loading everything upfront.

From Anthropic's [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):

> "Find the smallest set of high-signal tokens that maximize the likelihood of your desired outcome"

### Core Principles

1. **Incremental Discovery**: Each interaction provides signals that inform the next decision
2. **Just-in-Time Retrieval**: Maintain lightweight references, fetch dynamically during execution
3. **Signal-Driven Navigation**: File sizes indicate complexity, timestamps suggest relevance
4. **Minimal High-Signal Tokens**: Context is precious—minimize while maximizing relevance

## Traditional Approaches vs Progressive Disclosure

| Approach | How Context is Handled | Progressive? |
|----------|------------------------|--------------|
| **Direct Prompting** | Full context stuffed into prompt | No |
| **RAG** | Retrieved chunks added to prompt | Partial |
| **Summarization** | Lossy compression upfront | No |
| **Context Pruning** | Older messages removed | No |
| **RLM** | External variable + iterative exploration | **Yes** |

### The Problem with Non-Progressive Approaches

```
Traditional: User Query + [ENTIRE 500K CONTEXT] → LLM → Answer

Issues:
- Wastes tokens on irrelevant content
- Attention diluted across everything
- Cost scales with context size
- "Lost in the middle" phenomenon
- Context limits eventually exceeded
```

### The Progressive Alternative

```
RLM: User Query + [Metadata about context] → LLM → Exploration Code
                                                 ↓
     Targeted slice of context → Sub-LLM → Summary
                                                 ↓
     Query + Summaries → LLM → Answer

Benefits:
- Only relevant content enters attention
- Cost scales with relevance, not size
- No artificial context limits
- Information retrieved just-in-time
```

## How RLM Implements Progressive Disclosure

### Phase 1: Metadata Only

The model first receives **structure without content**:

```python
# From RLM system prompt setup
metadata_prompt = f"""Your context is a {context_type} with
{context_total_length} total characters, and is broken up into
chunks of char lengths: {context_lengths}."""
```

The model learns:
- Type of data (string, list, dict)
- Total size
- Chunk structure

**It does NOT see**: The actual content.

### Phase 2: Forced Exploration

RLM enforces exploration before answering:

```python
# First iteration safeguard (from prompts.py)
safeguard = """You have not interacted with the REPL environment
or seen your prompt / context yet. Your next action should be to
look through and figure out how to answer the prompt, so don't
just provide a final answer yet."""
```

This prevents the model from guessing—it **must** explore.

### Phase 3: Signal-Driven Navigation

The model writes code to gather signals:

```python
# Example REPL exploration
```repl
# Signal: How big is this?
print(f"Total length: {len(context)}")

# Signal: What type of content?
print(f"First 500 chars: {context[:500]}")

# Signal: Any obvious structure?
if isinstance(context, list):
    print(f"Number of chunks: {len(context)}")
    print(f"Chunk sizes: {[len(c) for c in context[:5]]}")
```
```

### Phase 4: Just-in-Time Retrieval

Only relevant portions are retrieved for analysis:

```python
```repl
# Search for relevant sections (cheap operation)
relevant_indices = [i for i, chunk in enumerate(context)
                    if 'protein' in chunk.lower()]

# Retrieve only what's needed
for idx in relevant_indices[:3]:
    chunk = context[idx]
    # NOW content enters an LLM context (sub-LLM, not main)
    result = llm_query(f"Extract protein names from:\n{chunk}")
    print(f"Chunk {idx}: {result}")
```
```

### Phase 5: Aggregation

The main model sees summaries, not raw content:

```python
```repl
# Aggregate sub-LLM results
all_proteins = []
for idx in relevant_indices:
    proteins = llm_query(f"List proteins in:\n{context[idx]}")
    all_proteins.append(proteins)

# Final synthesis
final_answer = llm_query(f"Combine these findings:\n" +
                         "\n".join(all_proteins))
print(final_answer)
```

FINAL_VAR(final_answer)
```

## Progressive Disclosure Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER QUERY                                │
│            "Find all proteins that interact with ACE2"           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: METADATA                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Context: list[str], 1.2M chars, 25 chunks              │    │
│  │ Chunk sizes: [50000, 50000, 48000, ...]                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Model knows: SIZE, STRUCTURE                                    │
│  Model sees: NOTHING of actual content                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: EXPLORATION                                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ len(context) → 25                                       │    │
│  │ context[0][:200] → "Introduction to protein..."        │    │
│  │ [i for i,c in enumerate(context) if 'ACE2' in c]       │    │
│  │   → [3, 7, 12, 18]                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Model discovers: RELEVANT LOCATIONS                             │
│  Cost: Minimal (string operations, no LLM calls)                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: TARGETED RETRIEVAL                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ chunk_3 = context[3]   # 50K chars about ACE2          │    │
│  │ chunk_7 = context[7]   # 50K chars about interactions  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Retrieved: 100K of 1.2M (8% of total)                           │
│  Still not in main LLM context                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: SUB-LLM PROCESSING                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ llm_query("Find proteins interacting with ACE2 in:     │    │
│  │           {chunk_3}") → "TMPRSS2, Furin, ..."          │    │
│  │                                                         │    │
│  │ llm_query("Find interaction types in: {chunk_7}")      │    │
│  │           → "binding, cleavage, ..."                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Sub-LLMs see: Full chunks (fresh context each)                  │
│  Main LLM sees: Only the summaries returned                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: SYNTHESIS                                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Main LLM context contains:                              │    │
│  │ - Original query                                        │    │
│  │ - Exploration code + outputs                            │    │
│  │ - Sub-LLM summaries (~2K tokens total)                  │    │
│  │                                                         │    │
│  │ NOT: The 1.2M character context                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  FINAL("Proteins interacting with ACE2: TMPRSS2, Furin...")     │
└─────────────────────────────────────────────────────────────────┘
```

## Progressive Disclosure Strategies

### Strategy 1: Breadth-First Discovery

Scan everything lightly, then dive deep on relevant sections:

```python
```repl
# Light scan of all chunks
summaries = llm_query_batched([
    f"One sentence summary of:\n{chunk[:2000]}"
    for chunk in context
])

# Identify relevant chunks from summaries
relevant = [i for i, s in enumerate(summaries)
            if 'protein' in s.lower() or 'ACE2' in s]

# Deep analysis of relevant chunks only
for i in relevant:
    detailed = llm_query(f"Detailed protein analysis:\n{context[i]}")
    print(detailed)
```
```

### Strategy 2: Structure-Guided Navigation

Use document structure as navigation signals:

```python
```repl
# Find structure markers
headers = []
for i, chunk in enumerate(context):
    if chunk.startswith('## ') or chunk.startswith('# '):
        headers.append((i, chunk.split('\n')[0]))

print("Document structure:")
for i, h in headers:
    print(f"  Chunk {i}: {h}")

# Navigate to relevant section
target_chunk = next(i for i, h in headers if 'Methods' in h)
methods_content = context[target_chunk]
```
```

### Strategy 3: Query-Driven Focusing

Let the query guide what to explore:

```python
```repl
# Extract key terms from query
query = "Find all proteins that interact with ACE2"
key_terms = ['protein', 'ACE2', 'interact', 'bind']

# Score chunks by term frequency
scores = []
for i, chunk in enumerate(context):
    score = sum(chunk.lower().count(term) for term in key_terms)
    scores.append((i, score))

# Process top-scoring chunks
top_chunks = sorted(scores, key=lambda x: -x[1])[:5]
for i, score in top_chunks:
    if score > 0:
        result = llm_query(f"Answer '{query}' using:\n{context[i]}")
        print(f"Chunk {i} (score {score}): {result}")
```
```

### Strategy 4: Iterative Refinement

Build understanding across multiple iterations:

```python
# Iteration 1: Understand context structure
```repl
print(f"Context type: {type(context)}")
print(f"Total items: {len(context)}")
print(f"Sample: {str(context[0])[:500]}")
```

# Iteration 2: Locate relevant sections
```repl
matches = [(i, context[i].count('ACE2')) for i in range(len(context))]
relevant = [i for i, count in matches if count > 0]
print(f"ACE2 mentioned in chunks: {relevant}")
```

# Iteration 3: Extract information
```repl
findings = []
for i in relevant[:3]:
    finding = llm_query(f"What does this say about ACE2?\n{context[i]}")
    findings.append(finding)
buffer = "\n".join(findings)
print(buffer)
```

# Iteration 4: Synthesize
```repl
final = llm_query(f"Synthesize these findings about ACE2:\n{buffer}")
```
FINAL_VAR(final)
```

## Progressive Disclosure for Graphs (Ontologies)

For RDF graphs, progressive disclosure follows the same pattern with graph-specific operations:

### Phase 1: Graph Metadata

```python
```repl
stats = graph_size(ontology)
print(f"Triples: {stats['triples']}")
print(f"Classes: {stats['classes']}")
print(f"Properties: {stats['object_properties']}")
print(f"Namespaces: {graph_namespaces(ontology)}")
```
```

### Phase 2: Targeted Search

```python
```repl
# Don't load all classes - search for relevant ones
matches = graph_search(ontology, "protein", search_in="labels")
print(f"Found {len(matches)} protein-related classes")
for m in matches[:5]:
    print(f"  {m['uri']}: {m['labels']}")
```
```

### Phase 3: Subgraph Extraction

```python
```repl
# Extract only the relevant subgraph
protein_subgraph = graph_slice(ontology,
                               type_uri="http://onto.org/Protein",
                               depth=1, limit=200)
turtle = graph_serialize(protein_subgraph, "turtle")
print(f"Extracted {len(protein_subgraph)} triples")
```
```

### Phase 4: Sub-LLM Analysis

```python
```repl
# Sub-LLM analyzes the small, relevant slice
schema_info = llm_query(f"""
What properties are available for querying Proteins?
{turtle}
""")
print(schema_info)
```
```

## Measuring Progressive Disclosure Effectiveness

### Token Efficiency

```
Traditional approach:
  Input: 500,000 tokens (full context)
  Output: 500 tokens
  Total: 500,500 tokens
  Cost: $$$

Progressive disclosure (RLM):
  Iteration 1: 2,000 tokens (metadata + exploration)
  Iteration 2: 3,000 tokens (search + slice)
  Iteration 3: 50,000 tokens (sub-LLM on chunk)
  Iteration 4: 5,000 tokens (synthesis)
  Total: 60,000 tokens
  Cost: $ (88% reduction)
```

### Information Density

```
Traditional: 500K tokens, ~1% relevant
  → 5K relevant tokens buried in noise
  → Attention diluted across irrelevant content

Progressive: 60K tokens, ~80% relevant
  → 48K relevant tokens
  → Attention focused on signal
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Premature Deep Dive

```python
# BAD: Immediately processing everything
```repl
for chunk in context:
    result = llm_query(f"Analyze: {chunk}")  # Expensive!
```

# GOOD: Filter first, then process
```repl
relevant = [c for c in context if 'keyword' in c]
for chunk in relevant:
    result = llm_query(f"Analyze: {chunk}")
```
```

### Anti-Pattern 2: Ignoring Signals

```python
# BAD: Not using metadata
```repl
answer = llm_query(f"Answer from: {context}")  # Dumps everything
```

# GOOD: Use structure signals
```repl
print(f"Context has {len(context)} chunks")
print(f"First chunk preview: {context[0][:200]}")
# Now make informed decisions about what to retrieve
```
```

### Anti-Pattern 3: Over-Retrieval

```python
# BAD: Retrieving too much "just in case"
```repl
all_chunks = "\n".join(context)
answer = llm_query(f"Find proteins in: {all_chunks}")
```

# GOOD: Minimal retrieval
```repl
protein_chunks = [c for c in context if 'protein' in c.lower()][:3]
answer = llm_query(f"Find proteins in: {protein_chunks}")
```
```

## Connection to Other Context Engineering Patterns

### Hybrid with Pre-Loading

Some critical context can be pre-loaded while using progressive disclosure for the rest:

```python
# Pre-loaded: Small, always-relevant context
system_prompt = """You have access to:
- SPARQL endpoint at http://...
- Ontology namespaces: {namespaces}
- Common query patterns: {...}
"""

# Progressive: Large ontology explored on-demand
ontology = load_ontology("large_ontology.owl")  # External
# Model explores via graph tools, never sees full ontology
```

### Compaction After Disclosure

After progressive exploration, compact for future iterations:

```python
```repl
# After extensive exploration, save findings
findings = {
    "relevant_classes": [...],
    "key_properties": [...],
    "discovered_patterns": [...]
}
# Future iterations can start from these findings
```
```

## Summary

Progressive disclosure in RLM means:

1. **Start with metadata**, not content
2. **Explore structure** before diving into data
3. **Search and filter** to identify relevant portions
4. **Retrieve just-in-time** only what's needed
5. **Delegate to sub-LLMs** for processing chunks
6. **Aggregate summaries** in main context

The result: Arbitrarily large contexts processed efficiently, with attention focused on high-signal information.

## References

- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [RLM Paper (arXiv:2512.24601)](https://arxiv.org/abs/2512.24601)
- [Alex Zhang's RLM Blog Post](https://alexzhang13.github.io/blog/2025/rlm/)
- [Prime Intellect: RLM - The Paradigm of 2026](https://www.primeintellect.ai/blog/rlm)
