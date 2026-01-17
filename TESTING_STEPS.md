# Step-by-Step Testing Guide

## Testing RLM with Dataset Memory - Solveit Approach

This guide walks through testing each component incrementally.

## Prerequisites

```bash
source ~/uvws/.venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"  # Only needed for RLM tests
```

## Step 1: Test Basic Infrastructure (No API calls)

Test that the dataset module works:

```bash
python << 'EOF'
from rlm.dataset import setup_dataset_context

ns = {}
setup_dataset_context(ns)
print(f"✓ Dataset created: {ns['ds_meta'].session_id}")

ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30')
print(f"✓ Memory has {len(ns['ds_meta'].mem)} triples")

results = ns['mem_query']('SELECT ?s ?age WHERE { ?s <http://ex.org/age> ?age }')
print(f"✓ Query returned: {results}")
EOF
```

**Expected output:**
```
✓ Dataset created: abc12345
✓ Memory has 1 triples
✓ Query returned: [{'s': 'http://ex.org/alice', 'age': '30'}]
```

## Step 2: Test Memory Operations in Detail (No API calls)

Run the comprehensive test:

```bash
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python << 'EOF'
from rlm.dataset import setup_dataset_context

ns = {}
setup_dataset_context(ns)

# Test add
ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30', reason='Testing')
print(f"Memory: {len(ns['ds_meta'].mem)} triples")
print(f"Provenance: {len(ns['ds_meta'].prov)} events")

# Test query
results = ns['mem_query']('SELECT ?s ?age WHERE { ?s <http://ex.org/age> ?age }')
print(f"Query results: {results}")

# Test describe
desc = ns['mem_describe']('http://ex.org/alice')
print(f"Description: {desc}")

# Test work graphs
uri, graph = ns['work_create']('test')
print(f"Work graph: {uri}")

from rdflib import URIRef, Literal
graph.add((URIRef('http://ex.org/temp'), URIRef('http://ex.org/val'), Literal('42')))
ns['work_to_mem']('test', reason='Promotion test')
ns['work_cleanup']('test')
print(f"Final memory: {len(ns['ds_meta'].mem)} triples")

print("\n✓ All memory operations work!")
EOF
```

## Step 3: Test RLM with Memory (Requires API Key)

Run the simple RLM test:

```bash
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python test_rlm_memory_simple.py
```

**What to look for:**
- "✓ RLM called mem_add()"
- "✓ RLM called mem_query()"
- "✓ Memory has expected facts"
- "✓ Provenance was recorded"
- Final: "✓ SUCCESS"

**If it fails:**
- Check you have ANTHROPIC_API_KEY set
- Look at the code blocks - did RLM try to use memory?
- Check stderr for any errors

## Step 4: Test RLM with Ontology + Memory (Requires API Key)

```bash
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python << 'EOF'
from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context
from rlm.ontology import setup_ontology_context
from pathlib import Path

ont_path = Path('ontology/prov.ttl')
if not ont_path.exists():
    print("Skipping: prov.ttl not found")
    exit(0)

ns = {}
setup_dataset_context(ns)
setup_ontology_context(str(ont_path), ns, name='prov')

context = """
You have:
- PROV ontology in prov_meta (use prov_meta.classes, search_by_label(), etc.)
- Memory: mem_add(), mem_query()
"""

query = "Find the Activity class in PROV. Store a note about it in memory."

answer, iterations, ns = rlm_run(query, context, ns=ns, max_iters=8)

print(f"Answer: {answer}")
print(f"Memory: {len(ns['ds_meta'].mem)} triples")
print(f"Ontology classes: {len(ns['prov_meta'].classes)}")
EOF
```

## Step 5: Test Memory Persistence (Requires API Key)

Test that memory persists across RLM runs:

```bash
PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm python << 'EOF'
from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context

ns = {}
setup_dataset_context(ns)
context = "You have mem_add() and mem_query()"

# First run
print("=== First RLM run ===")
query1 = "Store: Alice knows Bob"
answer1, _, ns = rlm_run(query1, context, ns=ns, max_iters=5)
print(f"Memory after run 1: {len(ns['ds_meta'].mem)} triples")

# Second run (same namespace)
print("\n=== Second RLM run (same namespace) ===")
query2 = "Query memory: who does Alice know?"
answer2, _, ns = rlm_run(query2, context, ns=ns, max_iters=5)
print(f"Memory after run 2: {len(ns['ds_meta'].mem)} triples")
print(f"Answer: {answer2}")

if "Bob" in answer2:
    print("\n✓ Memory persisted across runs!")
else:
    print("\n✗ Memory may not have persisted")
EOF
```

## Step 6: Interactive Jupyter Notebook

For interactive testing, use the step-by-step notebook:

```bash
jupyter notebook nbs/03_test_memory_solveit.ipynb
```

This notebook has 10 steps testing each component. You can run cells one at a time and inspect results.

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'rlm'"

**Fix:** Set PYTHONPATH:
```bash
export PYTHONPATH=/Users/cvardema/dev/git/LA3D/rlm
```

Or run from project root:
```bash
cd /Users/cvardema/dev/git/LA3D/rlm
python test_rlm_memory_simple.py
```

### Issue: RLM doesn't use memory operations

**Check:**
1. Is context clear about available functions?
2. Look at iteration code blocks - what did RLM try?
3. Check stderr for errors in code execution

**Fix:** Make query more explicit:
```python
query = "Use mem_add() to store this fact: Alice is 30"
```

### Issue: "Memory has 0 triples after RLM"

**Debug:**
```python
# After rlm_run, inspect what happened
for i, iteration in enumerate(iterations):
    print(f"Iteration {i}:")
    for block in iteration.code_blocks:
        print(f"Code: {block.code}")
        print(f"Stdout: {block.result.stdout}")
        print(f"Stderr: {block.result.stderr}")
```

### Issue: Provenance missing

This shouldn't happen - provenance is automatic. Check:
```python
print(f"Provenance events: {len(ns['ds_meta'].prov)}")
for s, p, o in list(ns['ds_meta'].prov.triples((None, None, None)))[:10]:
    print(f"{p}: {o}")
```

## Quick Verification Checklist

After each test, verify:

- [ ] `'ds' in ns` - Dataset created
- [ ] `'ds_meta' in ns` - Metadata available
- [ ] `len(ns['ds_meta'].mem) > 0` - Memory has facts
- [ ] `len(ns['ds_meta'].prov) > 0` - Provenance recorded
- [ ] `answer is not None` - RLM completed
- [ ] Code blocks contain `mem_add` or `mem_query` calls

## Summary

**Without API calls (fast):**
1. ✓ Test imports
2. ✓ Test dataset setup
3. ✓ Test memory operations
4. ✓ Test work graphs
5. ✓ Test snapshots

**With API calls (requires key):**
6. Test RLM using memory
7. Test RLM with ontology + memory
8. Test memory persistence

All tests passing = dataset memory is working correctly!
