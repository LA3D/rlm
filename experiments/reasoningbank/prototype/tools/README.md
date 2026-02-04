# SPARQL Tools for ReasoningBank

RLM-friendly tools for SPARQL endpoint discovery and query execution.

## Architecture: Agentic Discovery

The agent discovers endpoint capabilities through **tools**, not pre-loaded context.

```
┌─────────────────────────────────────────────────────────────┐
│  L0 Sense Card (minimal metadata)                           │
│  - Ontology stats, namespaces                               │
│  - "Federated endpoints available via tools"                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Agentic Discovery Tools                                    │
│                                                             │
│  Static (from SHACL examples):                              │
│  - federated_endpoints(path) → Ref                          │
│  - endpoints_list(ref, limit) → [{name, url, count}]        │
│                                                             │
│  Dynamic (from endpoints):                                  │
│  - service_desc(url) → Ref                                  │
│  - service_desc_graphs/features/sample()                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  SHACL Examples → Task Corpus (for learning)                │
│  - Competency questions become TASKS                        │
│  - Agent runs → trajectories → judge → extract strategies   │
│  - Strategies go into L2 procedural memory                  │
└─────────────────────────────────────────────────────────────┘
```

---

## RLM Tool Contract (Required)

All tools MUST follow these constraints:

### 1. Handles, Not Payloads

Large data returns `Ref` handles, not raw content:

```python
@dataclass
class Ref:
    key: str        # Storage key
    dtype: str      # 'results', 'registry', 'service_desc'
    rows: int       # Item/triple count
    sz: int         # Character count
    source: str     # Attribution (endpoint name/URL)

    def __repr__(self):
        return f"Ref({self.key!r}, {self.dtype!r}, {self.rows} items from {self.source})"
```

The REPL sees `Ref('results_0', 'results', 10 items from UniProt)`, not 400K chars.

### 2. Two-Phase Retrieval

Separate search/stats from content retrieval:

```python
# Phase 1: Get handle with metadata
ref = sparql_query("SELECT ?class WHERE { ?class a owl:Class }", limit=100)
# → Ref('results_0', 'results', 45 items, 2847 chars from UniProt)

# Phase 2: Inspect content (bounded)
stats = sparql_stats(ref.key)      # → {rows, cols, source}
rows = sparql_peek(ref.key, 5)     # → first 5 rows
slice = sparql_slice(ref.key, 0, 10)  # → rows 0-10
```

### 3. Bounded Returns

All tools enforce hard caps:

```python
sparql_classes(limit=50)      # Hard cap: 100
sparql_properties(limit=50)   # Hard cap: 100
sparql_find(pattern, limit=20)  # Hard cap: 50
sparql_peek(ref, n=5)         # Hard cap: 20
sparql_slice(ref, start, end) # Hard cap: 50 rows
endpoints_list(ref, limit=10) # Hard cap: 50
service_desc_features(ref)    # Hard cap: 50
```

### 4. Source Attribution

Every return includes `source` for provenance:

```python
ref.source                    # 'UniProt'
stats['source']               # 'UniProt'
classes['source']             # 'UniProt'
endpoints_list(ref)['source'] # 'ontology/uniprot'
```

### 5. DSPy RLM Signatures

Tools use `lambda args, kwargs:` pattern:

```python
def as_dspy_tools(self) -> dict:
    return {
        'sparql_query': lambda args, kwargs: self.sparql_query(
            _get_arg(args, kwargs, 0, 'query', ''),
            _get_arg(args, kwargs, 1, 'limit', 100)
        ),
        # ...
    }
```

### 6. No Stdout Bloat

Tools return JSON/dicts, never print:

```python
# Good
return {'source': 'UniProt', 'count': 5, 'results': [...]}

# Bad
print(f"Found {count} results...")  # Bloats RLM history
```

---

## Tool Reference

### Endpoint Discovery (`endpoint_tools.py`)

```python
from experiments.reasoningbank.tools.endpoint_tools import EndpointTools

tools = EndpointTools()

# Static discovery (from SHACL examples)
ref = tools.federated_endpoints('ontology/uniprot')
endpoints = tools.endpoints_list(ref.key, limit=10)
detail = tools.endpoint_detail(ref.key, 'Rhea')
graphs = tools.data_graphs(ref.key)

# Dynamic discovery (from service description)
sd = tools.service_desc('https://sparql.uniprot.org/sparql/')
stats = tools.service_desc_stats(sd.key)
features = tools.service_desc_features(sd.key)
named_graphs = tools.service_desc_graphs(sd.key)
sample = tools.service_desc_sample(sd.key, n=10)

# DSPy integration
dspy_tools = tools.as_dspy_tools()
```

| Tool | Returns | Description |
|------|---------|-------------|
| `federated_endpoints(path)` | Ref | Discover endpoints from SHACL examples |
| `endpoints_list(ref, limit)` | dict | List discovered endpoints |
| `endpoint_detail(ref, name)` | dict | Details for specific endpoint |
| `data_graphs(ref, limit)` | dict | FROM clause graphs |
| `service_desc(url)` | Ref | Fetch endpoint service description |
| `service_desc_stats(ref)` | dict | Service description stats |
| `service_desc_graphs(ref)` | dict | Named graphs from sd |
| `service_desc_features(ref)` | dict | Supported features from sd |
| `service_desc_sample(ref, n)` | dict | Sample triples from sd |

### SPARQL Query (`sparql.py`)

```python
from experiments.reasoningbank.tools.sparql import SPARQLTools
from experiments.reasoningbank.tools.endpoint import EndpointConfig

config = EndpointConfig(
    url='https://sparql.uniprot.org/sparql/',
    name='UniProt',
    authority='UniProt Consortium',
)
tools = SPARQLTools(config)

# Query execution
ref = tools.sparql_query("SELECT ?s WHERE { ?s a owl:Class }", limit=100)
stats = tools.sparql_stats(ref.key)
rows = tools.sparql_peek(ref.key, 5)

# Schema exploration
classes = tools.sparql_classes(limit=50)
props = tools.sparql_properties(limit=50)
desc = tools.sparql_describe(uri, limit=20)

# Search
results = tools.sparql_find("kinase", limit=20)
sample = tools.sparql_sample(class_uri, n=10)
count = tools.sparql_count("SELECT (COUNT(*) as ?n) WHERE {...}")

# DSPy integration
dspy_tools = tools.as_dspy_tools()
```

| Tool | Returns | Description |
|------|---------|-------------|
| `sparql_query(q, limit)` | Ref | Execute SPARQL, return handle |
| `sparql_stats(ref)` | dict | Result metadata |
| `sparql_peek(ref, n)` | list | First n rows |
| `sparql_slice(ref, start, end)` | list | Row range |
| `sparql_classes(limit)` | dict | Available classes |
| `sparql_properties(limit)` | dict | Available properties |
| `sparql_describe(uri, limit)` | dict | Triples about URI |
| `sparql_find(pattern, limit)` | dict | Label search |
| `sparql_sample(class, n)` | dict | Sample instances |
| `sparql_count(query)` | dict | Count query |
| `endpoint_info()` | dict | Endpoint metadata |

### Task Corpus (`shacl_tasks.py`)

```python
from experiments.reasoningbank.tools.shacl_tasks import (
    load_shacl_tasks, get_task_stats, sample_tasks
)

# Load tasks from SHACL examples
tasks = load_shacl_tasks('ontology/uniprot')

# Filter by complexity
simple_tasks = load_shacl_tasks(
    'ontology/uniprot',
    complexity_filter=['simple', 'moderate']
)

# Get statistics
stats = get_task_stats(tasks)
# → {total, by_complexity, by_endpoint, top_keywords}

# Sample tasks
sample = sample_tasks(tasks, n=10, complexity='simple')

# Task structure
task = tasks[0]
task.id              # '121_proteins_and_diseases'
task.query           # 'List all proteins and diseases...'
task.expected_sparql # 'SELECT ?protein ?disease WHERE...'
task.endpoint        # 'https://sparql.uniprot.org/sparql/'
task.keywords        # ['protein', 'disease', 'list']
task.complexity      # 'moderate'
```

---

## Files

```
experiments/reasoningbank/tools/
├── README.md           # This file
├── endpoint.py         # EndpointConfig dataclass
├── endpoint_tools.py   # Discovery tools (RLM pattern)
├── sparql.py           # Query tools (RLM pattern)
├── shacl_tasks.py      # Task corpus loader
├── discovery.py        # Low-level endpoint discovery
├── uniprot_examples.py # SHACL example parser
├── sense_card.py       # L0 sense card builder
└── test_sparql.py      # Test suite
```

---

## Learning Flow

SHACL examples become the **task corpus** for ReasoningBank learning:

1. **Load tasks**: `tasks = load_shacl_tasks('ontology/uniprot')`

2. **Agent runs on task**:
   ```python
   # Task: "List proteins associated with Alzheimer's disease"
   # Agent uses tools to explore and construct query:
   sd = service_desc('https://sparql.uniprot.org/sparql/')
   features = service_desc_features(sd.key)
   classes = sparql_classes(limit=20)
   # ... constructs query based on exploration
   ```

3. **Judge trajectory**: Success/failure

4. **Extract strategy** (if successful):
   ```python
   Item(
       title="UniProt disease annotation pattern",
       content="""When querying protein-disease associations:
       1. Explore up:Disease_Annotation class
       2. Use up:annotation to link proteins
       Pattern: ?protein up:annotation ?ann . ?ann a up:Disease_Annotation""",
       src='success'
   )
   ```

5. **Store in L2**: Strategy becomes retrievable procedural memory

---

## Testing

```bash
# Test SPARQL tools (requires network)
python experiments/reasoningbank/tools/test_sparql.py

# Test endpoint discovery
python experiments/reasoningbank/tools/endpoint_tools.py

# Test task loader
python experiments/reasoningbank/tools/shacl_tasks.py

# Test SHACL parser
python experiments/reasoningbank/tools/uniprot_examples.py

# Test discovery
python experiments/reasoningbank/tools/discovery.py
```

---

## Related

- **IMPLEMENTATION_PLAN.md**: Full architecture documentation
- **rlm_notes.md**: RLM v2 principles
- **README.md** (parent): Experiment design
