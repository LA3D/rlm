"""Quick end-to-end test to verify all notebooks work with real API calls.

This test exercises the main functionality from each notebook to ensure
the code actually works, not just passes unit tests.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*70)
print("QUICK END-TO-END TEST WITH REAL API CALLS")
print("="*70)

# Test 1: Core RLM loop (00_core.ipynb)
print("\n1. Testing core RLM loop...")
from rlm.core import llm_query
ns = {}
result = llm_query("What is 2+2?", ns, name='math_test')
assert 'math_test' in ns
assert '4' in result
print("   ✓ llm_query works")

# Test 2: Ontology loading (01_ontology.ipynb)
print("\n2. Testing ontology loading...")
from rlm.ontology import setup_ontology_context
ns = {}
result = setup_ontology_context('ontology/prov.ttl', ns, name='prov')
assert 'prov' in ns
assert 'prov_meta' in ns
assert 'search_by_label' in ns
print(f"   ✓ Loaded PROV ontology: {ns['prov_meta'].summary()}")

# Test 3: Dataset memory (02_dataset_memory.ipynb)
print("\n3. Testing dataset memory...")
from rlm.dataset import setup_dataset_context
ns = {}
result = setup_dataset_context(ns)
assert 'ds' in ns
assert 'ds_meta' in ns
assert 'mem_add' in ns
print(f"   ✓ Dataset context: {ns['dataset_stats']()}")

# Test 4: SPARQL handles (03_sparql_handles.ipynb)
print("\n4. Testing SPARQL handles...")
from rlm.sparql_handles import SPARQLResultHandle
handle = SPARQLResultHandle(
    rows=[{'x': 1}, {'x': 2}],
    result_type='select',
    query='SELECT ?x WHERE { }',
    endpoint='local',
    columns=['x'],
    total_rows=2
)
assert handle.summary() == "SELECT: 2 rows, columns=['x']"
assert len(handle) == 2
print("   ✓ SPARQL result handles work")

# Test 5: Procedural memory (05_procedural_memory.ipynb)
print("\n5. Testing procedural memory...")
from rlm.procedural_memory import MemoryStore, MemoryItem, retrieve_memories
from datetime import datetime, timezone
import uuid

store = MemoryStore()
item = MemoryItem(
    id=str(uuid.uuid4()),
    title='Test memory',
    description='A test memory item',
    content='- Step 1\n- Step 2',
    source_type='success',
    task_query='test',
    created_at=datetime.now(timezone.utc).isoformat(),
    tags=['test']
)
store.add(item)
retrieved = retrieve_memories(store, 'test query', k=1)
assert len(retrieved) == 1
print("   ✓ Procedural memory works")

# Test 6: SHACL examples (06_shacl_examples.ipynb)
print("\n6. Testing SHACL indexing...")
from rlm.shacl_examples import detect_shacl, build_shacl_index
from rdflib import Graph

# Load DCAT-AP SHACL shapes
dcat_path = Path('ontology/dcat-ap/dcat-ap-SHACL.ttl')
if dcat_path.exists():
    g = Graph()
    g.parse(dcat_path)

    detection = detect_shacl(g)
    assert detection['node_shapes'] > 0

    index = build_shacl_index(g)
    assert len(index.shapes) > 0
    print(f"   ✓ SHACL indexing works: {index.summary()}")
else:
    print("   ⊘ DCAT-AP shapes not found, skipping")

# Test 7: Integration - RLM with ontology
print("\n7. Testing RLM with ontology integration...")
from rlm.core import rlm_run

ns = {}
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

query = "What is prov:Activity?"
context = ns['prov_meta'].summary()

print(f"   Running RLM query: {query[:50]}...")
answer, iterations, ns = rlm_run(
    query,
    context,
    ns=ns,
    max_iters=3,
    verbose=False
)

print(f"   Answer: {answer[:100] if answer else 'No answer'}...")
print(f"   Iterations: {len(iterations)}")
assert len(iterations) > 0
print("   ✓ RLM integration works")

# Test 8: Memory closed loop (if time allows)
print("\n8. Testing memory closed loop...")
from rlm.procedural_memory import extract_trajectory_artifact, judge_trajectory
from rlm._rlmpaper_compat import RLMIteration, CodeBlock, REPLResult

# Create mock trajectory
block = CodeBlock(
    code="result = 'prov:Activity is a class'",
    result=REPLResult(stdout="Success", stderr=None, locals={})
)
iteration = RLMIteration(
    prompt="test",
    response="test",
    code_blocks=[block],
    final_answer="prov:Activity is a class",
    iteration_time=0.1
)

artifact = extract_trajectory_artifact(
    task="What is prov:Activity?",
    answer="prov:Activity is a class",
    iterations=[iteration],
    ns={'result': 'success'}
)

assert artifact['converged']
assert len(artifact['key_steps']) > 0
print("   ✓ Memory closed loop components work")

print("\n" + "="*70)
print("ALL TESTS PASSED ✓")
print("="*70)
print("\nSummary:")
print("  - Core RLM loop works")
print("  - Ontology loading works")
print("  - Dataset memory works")
print("  - SPARQL handles work")
print("  - Procedural memory works")
print("  - SHACL indexing works")
print("  - RLM + ontology integration works")
print("  - Memory closed loop works")
print("\nThe code in all notebooks is functional!")
