# Dataset-Based Memory Usage Guide

## Overview

The `rlm.dataset` module provides RDF Dataset-based session memory for RLM using named graphs. This enables:

- **Working memory** (`mem`) - Mutable session-scoped memory
- **Provenance tracking** (`prov`) - Audit trail of all changes
- **Scratch graphs** (`work/*`) - Temporary storage for intermediate results
- **Ontology mounting** (`onto/*`) - Read-only ontology graphs

## Quick Start

```python
from rlm.dataset import setup_dataset_context

# Setup dataset in namespace
ns = {}
setup_dataset_context(ns)

# Now you have access to memory operations
ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30')
results = ns['mem_query']('SELECT ?s ?age WHERE { ?s <http://ex.org/age> ?age }')
print(results)
# [{'s': 'http://ex.org/alice', 'age': '30'}]
```

## Named Graph Layout

```
Dataset
├── urn:rlm:ds:mem           (working memory)
├── urn:rlm:ds:prov          (provenance trail)
├── urn:rlm:ds:onto/prov     (mounted ontology)
├── urn:rlm:ds:work/task_001 (scratch graph)
└── urn:rlm:ds:work/task_002 (scratch graph)
```

## Core Operations

### Memory Operations

```python
# Add facts with provenance
ns['mem_add']('http://ex.org/alice', 'http://ex.org/knows', 'http://ex.org/bob',
              source='agent', reason='User stated')

# Query memory (SPARQL)
results = ns['mem_query']('''
    SELECT ?person ?age
    WHERE { ?person <http://ex.org/age> ?age }
''')

# Describe entity
desc = ns['mem_describe']('http://ex.org/alice')
print(desc['as_subject'])  # Triples where alice is subject
print(desc['as_object'])   # Triples where alice is object

# Retract facts
ns['mem_retract'](predicate='http://ex.org/age',
                  source='agent', reason='Correction needed')
```

### Scratch Graph Workflow

```python
# Create scratch graph for analysis
uri, graph = ns['work_create']('analysis_001')

# Add intermediate results to scratch graph
from rdflib import URIRef, Literal
graph.add((URIRef('http://ex.org/temp'),
           URIRef('http://ex.org/value'),
           Literal('42')))

# Promote validated results to mem
ns['work_to_mem']('analysis_001', reason='Analysis validated')

# Cleanup scratch graph
ns['work_cleanup'](task_id='analysis_001')
```

### Provenance Tracking

All `mem_add`, `mem_retract`, and `work_to_mem` operations automatically record provenance:

```python
# Add with provenance
ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30',
              source='agent', reason='User input')

# Provenance is stored in prov graph
ds_meta = ns['ds_meta']
print(f"Provenance events: {len(ds_meta.prov)}")

# Query provenance
for s, p, o in ds_meta.prov.triples((None, None, None)):
    print(f"{p}: {o}")
```

Provenance model:

```turtle
urn:rlm:prov:event_abc123 a rlm:AddEvent ;
    rlm:subject <http://ex.org/alice> ;
    rlm:predicate <http://ex.org/age> ;
    rlm:object "30" ;
    rlm:timestamp "2026-01-17T10:30:00Z"^^xsd:dateTime ;
    rlm:source "agent" ;
    rlm:reason "User input" ;
    rlm:session "abc123" .
```

### Snapshots

```python
# Save dataset snapshot for debugging
snapshot_path = ns['snapshot_dataset']()  # Auto-generates filename
# Or specify path
ns['snapshot_dataset'](path='debug_snapshot.trig')

# Load snapshot later
from rlm.dataset import load_snapshot
ns2 = {}
load_snapshot('debug_snapshot.trig', ns2)
# Preserves all graphs including provenance
```

### Bounded Views

```python
# Dataset statistics
stats = ns['dataset_stats']()
print(stats)

# List all graphs
graphs = ns['list_graphs']()
# [('urn:rlm:ds:mem', 42), ('urn:rlm:ds:prov', 10), ...]

# List specific graphs
work_graphs = ns['list_graphs'](pattern='work/')

# Sample triples from a graph
sample = ns['graph_sample']('urn:rlm:ds:mem', limit=10)
```

## Integration with Ontologies

```python
from rlm.dataset import setup_dataset_context
from rlm.ontology import setup_ontology_context

ns = {}
setup_dataset_context(ns)
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

# Mount ontology into dataset
ns['mount_ontology']('ontology/prov.ttl', 'prov')

# Now ontology is in dataset as onto/prov graph
graphs = ns['list_graphs'](pattern='onto/')
# [('urn:rlm:ds:onto/prov', 523)]

# Use ontology to validate memory operations
prov_classes = ns['prov_meta'].classes
# Use these classes to structure data in mem
```

## Integration with RLM

```python
from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context

# Setup namespace with dataset memory
ns = {}
setup_dataset_context(ns)

# Add initial facts
ns['mem_add']('http://ex.org/alice', 'http://ex.org/age', '30')

# Run RLM with memory available
answer, iterations, ns = rlm_run(
    "What is Alice's age and is she an adult?",
    context="Use mem_query to check memory",
    ns=ns,
    max_iters=5
)

# RLM can use mem_add, mem_query, etc. in code blocks
# Memory persists across iterations
# Provenance tracks all changes
```

## DatasetMeta API

The `DatasetMeta` class provides lazy-cached indexes:

```python
ds_meta = ns['ds_meta']

# Properties
ds_meta.session_id          # Unique session ID
ds_meta.mem                 # Memory graph
ds_meta.prov                # Provenance graph
ds_meta.graph_stats         # Dict of {graph_uri: triple_count}
ds_meta.work_graphs         # List of work/* graph URIs

# Methods
ds_meta.summary()           # Human-readable summary
ds_meta._invalidate_caches() # Called automatically on mutations
```

## Design Principles

1. **Session-scoped**: Memory is per-RLM run, not persistent across sessions
2. **Handle-based**: Functions return bounded views, not raw RDF terms
3. **Provenance-first**: All mutations tracked with source/reason/timestamp
4. **Lazy indexing**: Caches invalidated on mutation for consistency
5. **Read-only ontologies**: Ontologies mounted as immutable reference

## Performance Notes

- `mem_query` automatically injects `LIMIT` if not present (default: 100)
- `mem_describe` limits triples returned (default: 20)
- `graph_stats` is cached until next mutation
- Work graphs are cleaned up manually (not auto-gc'd)

## See Also

- `nbs/02_dataset_memory.ipynb` - Implementation notebook
- `tests/test_dataset_integration.py` - Integration tests
- `docs/rlm-ontology-solveit-trajectory.md` - Architecture overview
