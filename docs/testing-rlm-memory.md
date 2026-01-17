# Testing RLM with Dataset Memory

## Quick Start

### Option 1: Run the Interactive Demo (Recommended)

The easiest way to see RLM using memory:

```bash
# Activate environment
source ~/uvws/.venv/bin/activate

# Run the demo (requires Claude API key)
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python examples/rlm_memory_demo.py
```

This demo shows:
- **Demo 1**: Basic memory operations (add/query facts)
- **Demo 2**: Ontology + memory integration
- **Demo 3**: Memory persistence across multiple RLM turns
- **Demo 4**: Snapshot and restore

### Option 2: Run Unit Tests

Test without API calls (no LLM needed):

```bash
source ~/uvws/.venv/bin/activate
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python tests/test_dataset_integration.py
```

### Option 3: Run Integration Tests

Test RLM with memory (requires API key):

```bash
source ~/uvws/.venv/bin/activate
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python tests/test_rlm_with_memory.py
```

## Manual Testing in REPL

### Simple Test

```python
from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context

# Setup
ns = {}
setup_dataset_context(ns)

# Give RLM a memory task
context = """
You have these memory operations:
- mem_add(subject, predicate, object, source='agent', reason='...')
- mem_query(sparql_query, limit=100)
"""

query = "Store: Alice is 30, Bob is 25. Then query memory to verify."

# Run RLM
answer, iterations, ns = rlm_run(query, context, ns=ns, max_iters=5)

# Check results
print(f"Answer: {answer}")
print(f"Memory: {len(ns['ds_meta'].mem)} triples")
print(f"Provenance: {len(ns['ds_meta'].prov)} events")
print(f"Iterations: {len(iterations)}")

# Inspect memory
for s, p, o in ns['ds_meta'].mem.triples((None, None, None)):
    print(f"{s} -> {p} -> {o}")
```

### Test with Ontology

```python
from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context
from rlm.ontology import setup_ontology_context

# Setup both
ns = {}
setup_dataset_context(ns)
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

context = """
You have:
- PROV ontology in prov_meta
- Memory operations: mem_add(), mem_query()

Use the ontology to understand concepts, store examples in memory.
"""

query = """
Find the Activity class in PROV ontology.
Store its comment in memory.
Verify it was stored.
"""

answer, iterations, ns = rlm_run(query, context, ns=ns, max_iters=8)

print(f"Ontology: {len(ns['prov_meta'].classes)} classes")
print(f"Memory: {len(ns['ds_meta'].mem)} triples")
```

### Test Persistence

```python
from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context

ns = {}
setup_dataset_context(ns)
context = "You have mem_add() and mem_query()"

# First RLM run
query1 = "Store: Alice knows Bob"
answer1, _, ns = rlm_run(query1, context, ns=ns, max_iters=5)
print(f"After run 1: {len(ns['ds_meta'].mem)} triples")

# Second RLM run (same namespace)
query2 = "Who does Alice know? Query memory."
answer2, _, ns = rlm_run(query2, context, ns=ns, max_iters=5)
print(f"After run 2: {len(ns['ds_meta'].mem)} triples")
print(f"Answer: {answer2}")
```

## What to Look For

### 1. Memory Operations in Iterations

Check that RLM is actually using memory:

```python
# After rlm_run
for i, iteration in enumerate(iterations):
    print(f"\n--- Iteration {i} ---")
    print(f"Response: {iteration.response[:200]}...")

    # Check if code used memory operations
    for block in iteration.code_blocks:
        if 'mem_add' in block.code or 'mem_query' in block.code:
            print("✓ Used memory operations")
            print(f"Code:\n{block.code}")
            print(f"Result: {block.result.stdout[:100]}")
```

### 2. Provenance Tracking

Verify all changes are tracked:

```python
from rdflib import RDF

ds_meta = ns['ds_meta']

print(f"Total provenance events: {len(ds_meta.prov)}")

# Show event types
for event in ds_meta.prov.subjects(RDF.type, None):
    event_type = list(ds_meta.prov.objects(event, RDF.type))[0]
    print(f"\nEvent: {event}")
    print(f"  Type: {event_type}")

    # Show details
    for p, o in ds_meta.prov.predicate_objects(event):
        if p != RDF.type:
            pred_name = str(p).split('/')[-1]
            print(f"  {pred_name}: {o}")
```

### 3. Memory Contents

Inspect what RLM stored:

```python
ds_meta = ns['ds_meta']

print(f"Memory graph: {len(ds_meta.mem)} triples")

# Show all triples
for s, p, o in ds_meta.mem.triples((None, None, None)):
    print(f"\n{s}")
    print(f"  {p}")
    print(f"    {o}")

# Or use mem_query
results = ns['mem_query']('SELECT ?s ?p ?o WHERE { ?s ?p ?o }')
for row in results:
    print(row)
```

### 4. Session Continuity

Verify session ID stays constant:

```python
ds_meta = ns['ds_meta']
session_id = ds_meta.session_id

# Run multiple RLM turns
for i in range(3):
    query = f"Turn {i}: Store something in memory"
    answer, iters, ns = rlm_run(query, context, ns=ns, max_iters=5)

    # Session ID should be same
    assert ns['ds_meta'].session_id == session_id
    print(f"Turn {i}: session_id={ns['ds_meta'].session_id}")
```

## Common Patterns

### Pattern 1: Progressive Disclosure

RLM builds up knowledge incrementally:

```python
context = """
You're exploring an ontology. Use:
- search_by_label(text) to find concepts
- describe_entity(uri) to learn about them
- mem_add() to remember important findings
- mem_query() to recall what you learned
"""

query = "Explore the PROV ontology. Remember 3 key concepts."
```

### Pattern 2: Scratch Graph Workflow

RLM uses work graphs for analysis:

```python
context = """
For analysis tasks:
1. work_create(task_id) for temporary storage
2. Add intermediate results to work graph
3. work_to_mem(task_id) to promote validated findings
4. work_cleanup(task_id) to remove scratch data
"""

query = "Analyze the ontology hierarchy, validate findings, store final results."
```

### Pattern 3: Provenance Audit

Review what RLM did and why:

```python
# After RLM completes
from rdflib import Namespace

RLM_PROV = Namespace('urn:rlm:prov:')
ds_meta = ns['ds_meta']

# Find all additions
for event in ds_meta.prov.subjects(RDF.type, RLM_PROV.AddEvent):
    subject = list(ds_meta.prov.objects(event, RLM_PROV.subject))[0]
    reason = list(ds_meta.prov.objects(event, RLM_PROV.reason))
    reason_str = str(reason[0]) if reason else "No reason given"

    print(f"Added {subject}")
    print(f"  Reason: {reason_str}")
```

## Debugging Tips

### Enable Verbose Output

```python
# See what RLM is doing each iteration
for i, iteration in enumerate(iterations):
    print(f"\n{'='*60}")
    print(f"Iteration {i}")
    print(f"{'='*60}")
    print(f"Prompt: {iteration.prompt[:200]}...")
    print(f"\nResponse: {iteration.response}")

    for j, block in enumerate(iteration.code_blocks):
        print(f"\n--- Code Block {j} ---")
        print(block.code)
        print(f"\nStdout: {block.result.stdout}")
        if block.result.stderr:
            print(f"Stderr: {block.result.stderr}")
```

### Check Dataset State

```python
# Use the bounded view functions
print(ns['dataset_stats']())

# List all graphs
for uri, count in ns['list_graphs']():
    print(f"{uri}: {count} triples")

# Sample each graph
for uri, _ in ns['list_graphs']():
    print(f"\nGraph: {uri}")
    sample = ns['graph_sample'](uri, limit=3)
    for s, p, o in sample:
        print(f"  {s} -> {p} -> {o}")
```

### Save Snapshot for Analysis

```python
# Save current state
path = ns['snapshot_dataset'](path='debug.trig')
print(f"Saved to {path}")

# Later: reload and inspect
from rlm.dataset import load_snapshot
ns2 = {}
load_snapshot('debug.trig', ns2)

# Inspect offline
print(f"Memory: {len(ns2['ds_meta'].mem)} triples")
```

## Expected Behavior

When RLM runs successfully with memory:

1. ✓ `len(ns['ds_meta'].mem) > 0` - Facts stored in memory
2. ✓ `len(ns['ds_meta'].prov) > 0` - Provenance recorded
3. ✓ `answer is not None` - RLM completed successfully
4. ✓ Code blocks contain `mem_add()` or `mem_query()` calls
5. ✓ Memory persists across multiple `rlm_run()` calls in same namespace
6. ✓ Session ID stays constant within a namespace

## Troubleshooting

**RLM doesn't use memory operations:**
- Check that context explains the available functions
- Try a more explicit query: "Use mem_add() to store..."
- Verify namespace has mem_add bound: `'mem_add' in ns`

**Memory is empty after RLM runs:**
- Check iteration code blocks - did RLM call mem_add?
- Look for errors in code block stderr
- Try simpler task: "Just store one fact using mem_add()"

**Provenance missing:**
- Provenance is automatic - if memory has triples, prov should too
- Check: `len(ns['ds_meta'].prov)`
- Verify using mem_add (not direct graph operations)

**Namespace confusion:**
- Each `setup_dataset_context(ns)` creates new dataset
- Reuse same `ns` dict for persistent memory
- Different `ns` = different session
