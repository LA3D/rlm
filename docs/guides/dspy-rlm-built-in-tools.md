# DSPy RLM Built-in Tools

**Date:** 2026-01-21

This guide documents the built-in tools automatically available in DSPy RLM runs, provided by the `dspy.RLM` module.

## Overview

When you use `run_dspy_rlm()` or `run_dspy_rlm_with_tools()`, the LLM has access to two built-in tools for delegating semantic analysis to sub-LLMs:

- `llm_query(prompt)` - Query a sub-LLM (~500K char capacity)
- `llm_query_batched(prompts)` - Query multiple prompts concurrently

These tools are **automatically injected** by DSPy RLM and available in addition to your custom tools (ontology tools, SPARQL tools, etc.).

## llm_query(prompt)

Query a sub-LLM for semantic analysis, meaning extraction, or classification tasks.

**Signature:**
```python
def llm_query(prompt: str) -> str:
    """Query the LLM with a prompt string."""
```

**Use cases:**
- Extract meaning from text (e.g., "What does this description mean?")
- Classify entities (e.g., "Is this a disease or a drug?")
- Summarize long text snippets
- Answer semantic questions about data you've retrieved

**Example:**
```python
# In an RLM run, after retrieving an entity description:
description = describe_entity('prov:Activity')
comment = description.get('comment', '')

# Use llm_query to extract key concepts
key_concepts = llm_query(f"""
Extract the 3 most important concepts from this definition:
{comment}

Return as a comma-separated list.
""")
print(key_concepts)
```

**Token capacity:** Sub-LLM can handle ~500K chars (enough for most semantic analysis tasks)

**Call budget:** Limited by `max_llm_calls` parameter (default 16 in `run_dspy_rlm`)

**Sub-model:** Uses `sub_model` parameter (default: `claude-3-5-haiku-20241022`)
- Haiku is fast and cost-effective for semantic tasks
- Can be overridden via `sub_model` parameter

## llm_query_batched(prompts)

Query multiple prompts concurrently using thread pool execution. **Much faster** than sequential `llm_query()` calls.

**Signature:**
```python
def llm_query_batched(prompts: list[str]) -> list[str]:
    """Query the LLM with multiple prompts concurrently."""
```

**Use cases:**
- Batch entity classification (e.g., "Which of these are proteins?")
- Parallel description extraction from multiple URIs
- Concurrent validation of multiple SPARQL result rows
- Any task where you need semantic analysis on multiple items

**Example:**
```python
# In an RLM run, after searching for multiple entities:
results = search_entity('protein', limit=10)
uris = [r['uri'] for r in results]

# Get descriptions for all entities
descriptions = [describe_entity(uri) for uri in uris]

# Extract key function for each protein in parallel
prompts = [
    f"What is the main biological function of: {desc.get('label', '')}? "
    f"Answer in 10 words or less."
    for desc in descriptions
]

functions = llm_query_batched(prompts)

# functions is now a list of strings, one per protein
for uri, func in zip(uris, functions):
    print(f"{uri}: {func}")
```

**Performance:** Uses `ThreadPoolExecutor` (default 8 workers)
- 10x+ faster than sequential calls for large batches
- Respects rate limits (concurrent != parallel API calls, but still faster due to async handling)

**Call budget:** Each prompt in the batch counts toward `max_llm_calls` limit
- Example: `llm_query_batched(["q1", "q2", "q3"])` uses 3 calls

**Error handling:** If a single prompt fails, its result is `"[ERROR] <error message>"`
- Other prompts in batch are not affected
- Check for `[ERROR]` prefix in results

## When to Use Which Tool

| Scenario | Use | Rationale |
|----------|-----|-----------|
| Single semantic question | `llm_query()` | Simple, clear |
| Multiple independent questions | `llm_query_batched()` | Much faster (concurrent) |
| Dependent questions (answer A informs question B) | Sequential `llm_query()` | Must wait for each result |
| Large-scale classification | `llm_query_batched()` | Batch processing wins |
| Iterative refinement | `llm_query()` | Each call depends on previous |

## Integration with Custom Tools

Built-in tools work alongside your custom tools:

```python
# Your custom tools
from rlm_runtime.tools import make_ontology_tools
from rlm.ontology import GraphMeta

meta = GraphMeta.from_file("prov.ttl")
tools = make_ontology_tools(meta)

# RLM execution
result = run_dspy_rlm(
    "What is Activity?",
    "prov.ttl",
    max_llm_calls=16,  # Budget for llm_query/llm_query_batched
    sub_model="anthropic/claude-3-5-haiku-20241022"  # Sub-LLM model
)
```

**Available tools in RLM environment:**
- `llm_query()` and `llm_query_batched()` (built-in)
- `search_entity()`, `describe_entity()`, `probe_relationships()`, `sparql_select()` (from `make_ontology_tools`)
- Any other tools passed via `tools` parameter

## Practical Patterns

### Pattern 1: Two-Phase Discovery

Use tools to **find** entities, then use `llm_query()` to **understand** them:

```python
# Phase 1: Find entities (tool usage)
candidates = search_entity('kinase', limit=5)

# Phase 2: Understand entities (semantic analysis)
for entity in candidates:
    desc = describe_entity(entity['uri'])
    is_enzyme = llm_query(f"""
    Based on this description, is this an enzyme?
    Description: {desc['comment']}

    Answer yes or no with brief reason.
    """)
    print(f"{entity['label']}: {is_enzyme}")
```

### Pattern 2: Batch Classification

Use `llm_query_batched()` to classify multiple entities efficiently:

```python
# Get all entities matching search
entities = search_entity('gene', limit=20)

# Build classification prompts
prompts = [
    f"Is '{e['label']}' a human gene? Answer yes/no."
    for e in entities
]

# Classify in batch (much faster than 20 sequential calls)
classifications = llm_query_batched(prompts)

# Filter to human genes only
human_genes = [
    e for e, classification in zip(entities, classifications)
    if classification.lower().startswith('yes')
]
```

### Pattern 3: Semantic Result Validation

Use `llm_query()` to validate SPARQL results semantically:

```python
# Execute SPARQL query
results = sparql_select("""
    PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?protein ?name WHERE {
        ?protein a up:Protein ;
                 up:recommendedName/up:fullName ?name .
        FILTER(CONTAINS(LCASE(?name), 'kinase'))
    }
""")

# Sample and validate
sample = res_head(results, n=5)

# Check if results are actually kinases
validation = llm_query(f"""
Are these all kinases?
{[row['name'] for row in sample]}

If not, which ones aren't? Answer briefly.
""")
print(validation)
```

## Call Budget Management

The `max_llm_calls` parameter limits total sub-LLM calls to prevent runaway costs:

```python
result = run_dspy_rlm(
    "Complex multi-entity question",
    "large_ontology.ttl",
    max_llm_calls=50,  # Allow up to 50 sub-LLM calls
    max_iterations=10   # But only 10 main loop iterations
)
```

**Budget exhaustion:** If you hit the limit, you'll get a `RuntimeError`:
```
LLM call limit exceeded: 50 + 1 > 50. Use Python code for aggregation instead of making more LLM calls.
```

**Strategies to avoid budget exhaustion:**
1. Use Python string operations instead of `llm_query()` for simple tasks (e.g., extracting substrings, counting)
2. Batch queries with `llm_query_batched()` instead of looping with `llm_query()`
3. Filter data with tools first, then use semantic analysis only on filtered subset
4. Increase `max_llm_calls` if your task genuinely requires many semantic analyses

## Cost Considerations

**Sub-LLM model choice impacts cost:**

| Model | Speed | Cost | When to Use |
|-------|-------|------|-------------|
| `claude-3-5-haiku-20241022` (default) | Fast | Low | Most semantic tasks, classification, extraction |
| `claude-3-5-sonnet-20241022` | Moderate | Medium | Complex reasoning, nuanced classification |
| `claude-opus-4-5-20251101` | Slow | High | Rare; only when Haiku/Sonnet insufficient |

**Typical costs per run:**
- 10 `llm_query()` calls (Haiku): ~$0.001-0.005
- 50 `llm_query_batched()` calls (Haiku): ~$0.005-0.025

**Cost optimization:**
1. Use Haiku by default (covers 95% of cases)
2. Batch queries when possible (`llm_query_batched()` reduces per-call overhead)
3. Use Python logic for non-semantic tasks (free)
4. Set reasonable `max_llm_calls` budget

## Thread Safety

**Important:** `llm_query_batched()` uses `ThreadPoolExecutor` (8 workers by default) and is thread-safe.

However, the **RLM instance itself** is not thread-safe when using `NamespaceCodeInterpreter`:
- Each RLM run should be in a separate thread/process
- Don't share RLM instances across concurrent runs
- For parallel eval trials, create fresh RLM instance per trial

See `docs/design/dspy-rlm-architecture-review.md` for details.

## Summary

**Built-in tools for semantic analysis:**
- `llm_query(prompt)` - Single semantic question
- `llm_query_batched(prompts)` - Batch semantic questions (much faster)

**Automatically available** in all DSPy RLM runs alongside your custom tools.

**Best practices:**
1. Use tools to **find/retrieve** data (bounded, fast)
2. Use `llm_query()` to **understand** data (semantic, slower)
3. Use `llm_query_batched()` for bulk classification/extraction (concurrent)
4. Set appropriate `max_llm_calls` budget
5. Use Haiku sub-model for cost efficiency

**Integration:** Works seamlessly with ontology tools, SPARQL tools, and memory retrieval.
