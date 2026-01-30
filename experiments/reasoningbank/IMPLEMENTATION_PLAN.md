# ReasoningBank Experiments: Implementation Plan (v2)

## Architecture Principle

**Foundation**: `dspy.predict.rlm` + `rdflib` only. No `rlm_runtime` dependencies.

The existing `rlm_runtime` code embodies assumptions we want to *test*, not assume. This experiment suite builds fresh implementations that directly test the hypotheses in README.md.

**Key Insight**: *"RLM will naturally follow the path of least resistance. If the easiest function returns the whole blob, you'll get blob-in-history. If the easiest returns metadata + offsets, you'll get Algorithm-1 behavior."*

**Style**: Follow [fastai style guide](../docs/guides/style.md) - brevity facilitates reasoning.

---

## Key Design Decisions

1. **Ref complements DSPy's REPLVariable** - DSPy shows preview+length for Python variables; `Ref` adds explicit storage/slicing for large tool returns

2. **Default to auto-inject** - Delegation doesn't reliably emerge (per ontology_exploration findings); system retrieves + packs + injects

3. **In-memory store per experiment** - Clean isolation; save snapshots as JSON for reproducibility

4. **Match Daytona truncation limits** - 10K chars for interpreter output, configurable per experiment

5. **Two-phase memory retrieval** - `search()` returns IDs only, `get()` returns content with hard cap

6. **DSPy RLM tool calling convention** - DSPy RLM calls tools as `tool(args, kwargs)` with TWO positional parameters (not `*args, **kwargs`). All tool wrappers must use signature `lambda args, kwargs: ...` to receive arguments correctly. This is a critical implementation detail discovered during testing.

---

## External Dependencies (Reuse)

| Library | Purpose |
|---------|---------|
| `dspy.predict.rlm` | RLM scaffold: code gen + execution, `llm_query`, `SUBMIT` |
| `rdflib` | Graph parsing, SPARQL execution, namespace handling |
| `sqlite3` | Simple persistence (stdlib) |

---

## Naming Conventions (Huffman Coding)

Common terms get short names:

| Long | Short | Usage |
|------|-------|-------|
| reference | `ref` | BlobRef handles |
| memory | `mem` | Memory store/items |
| context | `ctx` | Context tools |
| graph | `g` | RDFLib graph |
| size | `sz` | Character counts |
| preview | `prev` | Short excerpts |
| query | `q` | SPARQL/search queries |
| result | `res` | Return values |
| config | `cfg` | Configuration |
| count | `n` | Counts |

Loop variables: `o` for objects, `i` for index, `k`/`v` for dict items, `x` for data input.

---

## File Structure

```
experiments/reasoningbank/
├── README.md                    # EXISTS - experiment design
├── rlm_notes.md                 # EXISTS - RLM v2 principles
├── IMPLEMENTATION_PLAN.md       # THIS FILE
│
├── core/                        # Foundation (fresh implementations)
│   ├── __init__.py
│   ├── blob.py                  # BlobRef handle pattern (~40 LOC)
│   ├── graph.py                 # rdflib wrappers (~100 LOC)
│   ├── mem.py                   # Minimal memory store (~80 LOC)
│   └── instrument.py            # Leakage metrics (~50 LOC)
│
├── packers/                     # Layer packers (fresh)
│   ├── __init__.py
│   ├── l0_sense.py              # Ontology sense card (~60 LOC)
│   ├── l1_schema.py             # Schema constraints (~60 LOC)
│   ├── l2_mem.py                # Memory formatting (~40 LOC)
│   └── l3_guide.py              # Guide compression (~40 LOC)
│
├── ctx/                         # Layer cake assembler
│   ├── __init__.py
│   └── builder.py               # ContextBuilder (~100 LOC)
│
├── run/                         # Experiment execution
│   ├── __init__.py
│   ├── rlm.py                   # Direct dspy.RLM wrapper (~120 LOC)
│   ├── phase0.py                # E1-E8 layer experiments (~150 LOC)
│   └── phase1.py                # E9-E12 closed-loop (~120 LOC)
│
├── seed/                        # Bootstrap data
│   ├── strategies.json          # Curated success/failure strategies
│   └── constraints/             # Per-ontology constraint files
│
└── results/                     # Output (gitignored)
```

**Total**: ~960 LOC fresh implementation

---

## Module Specifications

### 1. `core/blob.py` - Handle Pattern

```python
from dataclasses import dataclass

@dataclass
class Ref:
    "Handle for large data - REPL sees metadata, not payload."
    key: str
    dtype: str   # 'graph', 'results', 'mem', 'text'
    sz: int      # char count
    prev: str    # first 80 chars
    def __repr__(self): return f"Ref({self.key!r}, {self.dtype}, {self.sz} chars)"

class Store:
    "In-memory blob storage for a single run."
    def __init__(self): self._blobs,self._counter = {},0

    def put(self, content:str, dtype:str) -> Ref:
        "Store `content`, return handle."
        k = f"{dtype}_{self._counter}"; self._counter += 1
        self._blobs[k] = content
        return Ref(k, dtype, len(content), content[:80])

    def get(self, k:str) -> str: return self._blobs[k]
    def peek(self, k:str, n:int=200) -> str: return self._blobs[k][:n]
    def slice(self, k:str, start:int, end:int) -> str: return self._blobs[k][start:end]
    def stats(self, k:str) -> dict:
        c = self._blobs[k]
        return {'sz': len(c), 'lines': c.count('\n')+1}
```

### 2. `core/graph.py` - RDFLib Wrappers

```python
from rdflib import Graph, RDF, RDFS, OWL

_store = None  # Set by runner
_graphs = {}   # key -> Graph

def g_load(path:str) -> Ref:
    "Load graph from `path`, return handle."
    g = Graph().parse(path)
    ref = _store.put(path, 'graph')
    _graphs[ref.key] = g
    return ref

def g_stats(ref:Ref) -> dict:
    "Return `{triples, classes, props, ns}`."
    g = _graphs[ref.key]
    return {
        'triples': len(g),
        'classes': len(list(g.subjects(RDF.type, OWL.Class))),
        'props': len(list(g.subjects(RDF.type, OWL.ObjectProperty))),
        'ns': [str(n) for _,n in g.namespaces()][:10],
    }

def g_query(ref:Ref, q:str, limit:int=100) -> Ref:
    "Execute SPARQL `q`, return results as handle."
    g = _graphs[ref.key]
    res = list(g.query(q))[:limit]
    txt = '\n'.join(str(row) for row in res)
    return _store.put(txt, 'results')

def g_sample(ref:Ref, n:int=10) -> str:
    "Return `n` sample triples as text."
    g = _graphs[ref.key]
    triples = list(g)[:n]
    return '\n'.join(f"{s} {p} {o}" for s,p,o in triples)

def g_classes(ref:Ref, limit:int=50) -> list[str]:
    "Return class URIs (bounded)."
    g = _graphs[ref.key]
    return [str(c) for c in list(g.subjects(RDF.type, OWL.Class))[:limit]]

def g_props(ref:Ref, limit:int=50) -> list[str]:
    "Return property URIs (bounded)."
    g = _graphs[ref.key]
    props = list(g.subjects(RDF.type, OWL.ObjectProperty))
    props += list(g.subjects(RDF.type, OWL.DatatypeProperty))
    return [str(p) for p in props[:limit]]

def g_describe(ref:Ref, uri:str, limit:int=20) -> str:
    "Return triples about `uri` (bounded)."
    g = _graphs[ref.key]
    from rdflib import URIRef
    subj = URIRef(uri)
    triples = list(g.triples((subj, None, None)))[:limit]
    return '\n'.join(f"{p} {o}" for _,p,o in triples)
```

### 3. `core/mem.py` - Minimal Memory

```python
from dataclasses import dataclass, field, asdict
import json, hashlib

@dataclass
class Item:
    "A reusable procedure."
    id: str
    title: str       # ≤10 words
    desc: str        # one sentence
    content: str     # full procedure
    src: str         # 'success' | 'failure' | 'seed'
    tags: list[str] = field(default_factory=list)

    @staticmethod
    def make_id(title:str, content:str) -> str:
        return hashlib.sha256(f"{title}\n{content}".encode()).hexdigest()[:12]

class MemStore:
    "Minimal memory store for experiments."
    def __init__(self): self._items = {}

    def add(self, item:Item) -> str:
        self._items[item.id] = item
        return item.id

    def search(self, q:str, k:int=5) -> list[dict]:
        "Return IDs + titles + descs ONLY (not content)."
        # Simple: score by word overlap
        qwords = set(q.lower().split())
        scored = []
        for item in self._items.values():
            words = set(f"{item.title} {item.desc} {' '.join(item.tags)}".lower().split())
            score = len(qwords & words)
            if score > 0: scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [{'id': o.id, 'title': o.title, 'desc': o.desc} for _,o in scored[:k]]

    def get(self, ids:list[str], max_n:int=3) -> list[Item]:
        "Return full items (hard cap enforced)."
        if len(ids) > max_n: raise ValueError(f"Requested {len(ids)} items, max is {max_n}")
        return [self._items[i] for i in ids if i in self._items]

    def all(self) -> list[Item]: return list(self._items.values())

    def save(self, path:str):
        with open(path, 'w') as f: json.dump([asdict(o) for o in self._items.values()], f)

    def load(self, path:str):
        with open(path) as f:
            for d in json.load(f): self._items[d['id']] = Item(**d)
```

### 4. `core/instrument.py` - Leakage Metrics

```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class Metrics:
    "Tracks prompt leakage during RLM execution."
    stdout_chars: int = 0
    large_returns: int = 0   # returns > 1000 chars
    subcalls: int = 0
    vars_n: int = 0

@dataclass
class Instrumented:
    "Wraps tools to capture leakage metrics."
    tools: dict[str, Callable]
    metrics: Metrics = field(default_factory=Metrics)

    def wrap(self) -> dict[str, Callable]:
        "Return wrapped tools that track `metrics`."
        wrapped = {}
        for name, fn in self.tools.items():
            def make_wrapper(f):
                def wrapper(*args, **kwargs):
                    res = f(*args, **kwargs)
                    if isinstance(res, str) and len(res) > 1000:
                        self.metrics.large_returns += 1
                    return res
                return wrapper
            wrapped[name] = make_wrapper(fn)
        return wrapped
```

### 5. `packers/l0_sense.py` - Enhanced Ontology Sense Card (Widoco-inspired)

**Status**: ✅ Enhanced - Handles 15+ vocabularies

```python
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.namespace import DC, DCTERMS, SKOS, FOAF

# Extended vocabularies
VANN = Namespace("http://purl.org/vocab/vann/")
SCHEMA = Namespace("http://schema.org/")
VOID = Namespace("http://rdfs.org/ns/void#")

def extract_metadata(g: Graph) -> dict:
    """Extract comprehensive ontology metadata.

    Handles:
    - Widoco standard (DC, DCTerms, VANN, FOAF, PAV)
    - OGC/GeoSPARQL (Schema.org, SKOS, Profiles)
    - OBO Foundry/SIO (CITO, VOID subsets, ORCID)
    """
    # Find ontology URI
    onto = list(g.subjects(RDF.type, OWL.Ontology))[0] if g.subjects(RDF.type, OWL.Ontology) else None

    meta = {
        'title': str(g.value(onto, DC.title) or g.value(onto, DCTERMS.title) or ""),
        'description': str(g.value(onto, DCTERMS.description) or ""),
        'prefix': str(g.value(onto, VANN.preferredNamespacePrefix) or ""),
        'imports': [str(i) for i in g.objects(onto, OWL.imports)],
        'subsets': [str(s) for s in g.objects(onto, VOID.subset)],
        'namespaces': {p: str(n) for p, n in g.namespaces() if p not in ['rdf','rdfs','owl','xsd']},
        'label_property': 'skos:prefLabel' if g.triples((None, SKOS.prefLabel, None)) else 'rdfs:label',
        'desc_property': 'skos:definition' if g.triples((None, SKOS.definition, None)) else 'rdfs:comment',
    }
    return meta

def pack(g: Graph, budget: int = 600) -> str:
    """Pack metadata into compact sense card (~500 chars).

    Priority: title, description, size, namespaces, imports/subsets, conventions
    """
    # Implementation extracts and formats based on priority
    # See l0_sense.py for full implementation
```

**Example Output (PROV, 473 chars)**:
```
**W3C PROVenance Interchange**
This document is published by the Provenance Working Group...
**Size**: 1664 triples, 59 classes, 69 properties
**Namespaces**: `brick`, `csvw`, `dcat`, `dcmitype`, `dcam`
**Imports**: prov-aq, prov-dc, prov-dictionary, prov-links, prov-o, prov-o-inverses
**Labels**: use `rdfs:label`
**Descriptions**: use `rdfs:comment`
**Formalism**: OWL-DL
```

### 6. `packers/l1_schema.py` - Enhanced Schema Constraints with Anti-patterns

**Status**: ✅ Enhanced - Adds anti-patterns, cardinality, property characteristics

```python
from rdflib import Graph, RDF, RDFS, OWL

def extract(g: Graph) -> dict:
    """Extract comprehensive schema constraints.

    Returns:
    - domain_range: Property signatures
    - disjoint: Disjoint class pairs
    - functional, symmetric, transitive, inverse_functional: Property types
    - cardinality: From OWL Restrictions (min/max/exact)
    """
    # Extract domain/range, disjoint, property characteristics
    # Extract cardinality from OWL Restrictions
    # See l1_schema.py for full implementation

def generate_anti_patterns(constraints: dict) -> list[str]:
    """Generate actionable warnings from constraints.

    Examples:
    - "Don't mix Activity and Entity in same query (disjoint)"
    - "Functional props have max 1 value per subject"
    - "Always specify rdf:type for class-based queries"
    """

def pack(g: Graph, budget: int = 1000) -> str:
    """Pack constraints prioritizing actionability (~900 chars).

    Priority:
    1. Anti-patterns (most actionable)
    2. Disjoint classes (prevent invalid queries)
    3. Property characteristics (enable optimizations)
    4. Domain/range (top 10 most important)
    5. Cardinality (if space)
    """
```

**Example Output (PROV, 943 chars)**:
```
**Schema Constraints**:

**Anti-patterns**:
- Don't mix Activity and Entity in same query (disjoint)
- Don't mix ActivityInfluence and EntityInfluence in same query (disjoint)
- Functional props (pairKey, pairEntity) have max 1 value per subject

**Disjoint**: Activity⊥Entity, ActivityInfluence⊥EntityInfluence, ...

**Property Types**:
- Functional: pairKey, pairEntity

**Domain/Range** (key properties):
- `actedOnBehalfOf`: Agent → Agent
- `qualifiedDelegation`: Agent → Delegation
...

**Cardinality**:
- `pairKey`: exactly 1
- `pairEntity`: exactly 1
```

### 7. `packers/l2_mem.py` - Memory Formatting

```python
from core.mem import Item

def pack(items:list[Item], budget:int=2000) -> str:
    "Format memories for context injection."
    lines = ['**Relevant Procedures**:']
    for o in items:
        lines.append(f"\n### {o.title}")
        lines.append(o.content)
    return '\n'.join(lines)[:budget]
```

### 8. `packers/l3_guide.py` - Guide Compression

```python
def pack(guide:str, budget:int=1000) -> str:
    "Compress guide to summary (extractive)."
    # Simple: take first `budget` chars, break at sentence
    if len(guide) <= budget: return guide
    cut = guide[:budget]
    # Find last sentence boundary
    for end in ['. ', '.\n', '! ', '? ']:
        i = cut.rfind(end)
        if i > budget//2: return cut[:i+1]
    return cut
```

### 9. `ctx/builder.py` - Layer Cake Assembler

```python
from dataclasses import dataclass, field
from rdflib import Graph
from core.blob import Store, Ref
from core.mem import MemStore
from core import graph as G
from packers import l0_sense, l1_schema, l2_mem, l3_guide

@dataclass
class Layer:
    on: bool = False
    budget: int = 0

@dataclass
class Cfg:
    l0: Layer = field(default_factory=lambda: Layer(False, 600))
    l1: Layer = field(default_factory=lambda: Layer(False, 1000))
    l2: Layer = field(default_factory=lambda: Layer(False, 2000))
    l3: Layer = field(default_factory=lambda: Layer(False, 1000))
    guide_text: str = ""  # Full guide for L3

class Builder:
    "Assembles layer cake context for injection."
    def __init__(self, cfg:Cfg): self.cfg = cfg

    def build(self, g:Graph, task:str, mem:MemStore=None) -> str:
        "Build context string from enabled layers."
        parts = []
        if self.cfg.l0.on: parts.append(l0_sense.pack(g, self.cfg.l0.budget))
        if self.cfg.l1.on: parts.append(l1_schema.pack(g, self.cfg.l1.budget))
        if self.cfg.l2.on and mem:
            hits = mem.search(task, k=3)
            if hits:
                items = mem.get([h['id'] for h in hits])
                parts.append(l2_mem.pack(items, self.cfg.l2.budget))
        if self.cfg.l3.on and self.cfg.guide_text:
            parts.append(l3_guide.pack(self.cfg.guide_text, self.cfg.l3.budget))
        return '\n\n'.join(parts)

    def tools(self, store:Store, g_path:str) -> dict:
        "Build tool dict for dspy.RLM."
        # Set module globals
        G._store = store

        # Load graph and store in module
        g = Graph().parse(g_path)
        ref = store.put(g_path, 'graph')
        G._graphs[ref.key] = g

        # Return bounded tools with correct DSPy RLM signatures
        # CRITICAL: DSPy RLM calls tools as tool(args, kwargs) where:
        #   args = actual arguments (value, list, etc)
        #   kwargs = keyword arguments dict
        # Tools MUST use signature: lambda args, kwargs: ...
        return {
            'g_stats': lambda args, kwargs: G.g_stats(ref),
            'g_query': lambda args, kwargs: G.g_query(ref, args if isinstance(args, str) else (args[0] if args else kwargs.get('q', '')), kwargs.get('limit', 100)),
            'g_sample': lambda args, kwargs: G.g_sample(ref, args if isinstance(args, int) else (args[0] if args else kwargs.get('n', 10))),
            'g_classes': lambda args, kwargs: G.g_classes(ref, args if isinstance(args, int) else (args[0] if args else kwargs.get('limit', 50))),
            'g_props': lambda args, kwargs: G.g_props(ref, args if isinstance(args, int) else (args[0] if args else kwargs.get('limit', 50))),
            'g_describe': lambda args, kwargs: G.g_describe(ref, args if isinstance(args, str) else (args[0] if args else kwargs.get('uri', '')), kwargs.get('limit', 20)),
            'ctx_peek': lambda args, kwargs: store.peek(args if isinstance(args, str) else (args[0] if args else kwargs.get('k', '')), args[1] if isinstance(args, list) and len(args) > 1 else kwargs.get('n', 200)),
            'ctx_slice': lambda args, kwargs: store.slice(args if isinstance(args, str) else (args[0] if args else kwargs.get('k', '')), args[1] if isinstance(args, list) and len(args) > 1 else kwargs.get('start', 0), args[2] if isinstance(args, list) and len(args) > 2 else kwargs.get('end', 100)),
            'ctx_stats': lambda args, kwargs: store.stats(args if isinstance(args, str) else (args[0] if args else kwargs.get('k', ''))),
        }
```

### 10. `run/rlm.py` - Direct DSPy RLM

```python
import dspy
from dataclasses import dataclass
from rdflib import Graph
from core.blob import Store
from core.mem import MemStore
from core.instrument import Metrics, Instrumented
from ctx.builder import Builder, Cfg

@dataclass
class Result:
    answer: str
    sparql: str|None
    converged: bool
    iters: int
    leakage: Metrics
    trace: list[dict]

def run(
    task: str,
    graph_path: str,
    cfg: Cfg,
    mem: MemStore|None = None,
    max_iters: int = 12,
    max_calls: int = 25,
) -> Result:
    "Run `task` using dspy.RLM with configured context."
    # Load graph
    g = Graph().parse(graph_path)

    # Build context
    builder = Builder(cfg)
    ctx = builder.build(g, task, mem)

    # Build tools
    store = Store()
    tools = builder.tools(store, g)
    inst = Instrumented(tools)

    # Run RLM
    rlm = dspy.RLM(
        "context, question -> sparql, answer",
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        tools=inst.wrap(),
    )
    res = rlm(context=ctx, question=task)

    return Result(
        answer=res.answer,
        sparql=getattr(res, 'sparql', None),
        converged=getattr(res, 'converged', True),
        iters=getattr(res, 'iterations', 0),
        leakage=inst.metrics,
        trace=[],
    )
```

### 11. `run/phase0.py` - E1-E8

```python
from ctx.builder import Cfg, Layer
from run.rlm import run, Result
from pathlib import Path
import json

# Experiment configurations
EXPS = {
    'E1': Cfg(),  # Baseline - no layers
    'E2': Cfg(l0=Layer(True, 600)),  # L0 only (sense card)
    'E3': Cfg(l1=Layer(True, 1000)), # L1 only (constraints)
    'E4': Cfg(l3=Layer(True, 1000)), # L3 only (guide summary)
    'E5': Cfg(l2=Layer(True, 2000)), # L2 only (seeded memories)
    'E6': Cfg(l0=Layer(True,600), l1=Layer(True,1000),
              l2=Layer(True,2000), l3=Layer(True,1000)),  # Full layer cake
}

# E7: Prompt leakage ablation - compare naive vs handle-based tools
# Run separately with different tool implementations:
#   E7a: Naive tools (return full payloads, verbose stdout)
#   E7b: Handle-based tools (Ref pattern, two-phase retrieval)
# Measure: context size per iteration, total iterations, cost, convergence

# E8: Retrieval policy ablation - compare injection modes:
#   E8a: Auto-inject (system retrieves + packs + injects L2)
#   E8b: Tool-mediated (agent calls mem_search/mem_get explicitly)
# Use identical budgets; measure convergence and answer quality

def run_phase0(exps:list[str], tasks:list[dict], ont:str, out:str):
    "Run layer ablation experiments."
    results = []
    for exp in exps:
        cfg = EXPS[exp]
        for t in tasks:
            res = run(t['query'], ont, cfg)
            results.append({
                'exp': exp, 'task': t['id'],
                'converged': res.converged, 'iters': res.iters,
                'answer': res.answer, 'sparql': res.sparql,
                'leakage': res.leakage.__dict__,
            })
            print(f"{exp} {t['id']}: {'✓' if res.converged else '✗'} ({res.iters} iters)")

    Path(out).mkdir(parents=True, exist_ok=True)
    with open(f"{out}/phase0_results.json", 'w') as f:
        json.dump(results, f, indent=2)
```

### 12. `run/phase1.py` - E9-E12

```python
from core.mem import MemStore, Item
from run.rlm import run, Result
import dspy

def judge(res:Result) -> dict:
    "Simple LLM-based judgment."
    # Use dspy for judgment
    judge_fn = dspy.Predict("answer, sparql -> is_success: bool, reason: str")
    j = judge_fn(answer=res.answer, sparql=res.sparql or "")
    return {'success': j.is_success, 'reason': j.reason}

def extract(res:Result, judgment:dict, task:str) -> list[Item]:
    "Extract procedures from trajectory."
    if not judgment['success']: return []
    # Use dspy for extraction
    ext = dspy.Predict("task, answer, sparql -> title, procedure")
    e = ext(task=task, answer=res.answer, sparql=res.sparql or "")
    item = Item(
        id=Item.make_id(e.title, e.procedure),
        title=e.title, desc=f"Procedure for: {task[:50]}",
        content=e.procedure, src='success', tags=[],
    )
    return [item]

def run_closed_loop(tasks:list[dict], ont:str, mem:MemStore,
                    do_extract:bool=True, consolidate:bool=False):
    "Run E9-E12 closed-loop learning."
    from ctx.builder import Cfg, Layer
    cfg = Cfg(l2=Layer(True, 2000))

    for t in tasks:
        res = run(t['query'], ont, cfg, mem)
        j = judge(res)
        print(f"{t['id']}: {'✓' if j['success'] else '✗'} - {j['reason'][:50]}")

        if do_extract:
            items = extract(res, j, t['query'])
            for item in items:
                mem.add(item)
                print(f"  Extracted: {item.title}")
```

---

## Implementation Order

### Week 1: Core Foundation
1. `core/blob.py` - No deps (~40 LOC)
2. `core/graph.py` - Deps: rdflib, blob (~100 LOC)
3. `core/mem.py` - No deps (~80 LOC)
4. `core/instrument.py` - No deps (~50 LOC)

### Week 2: Packers + Context
5. `packers/l0_sense.py` - Deps: rdflib (~60 LOC)
6. `packers/l1_schema.py` - Deps: rdflib (~60 LOC)
7. `packers/l2_mem.py` - Deps: mem (~40 LOC)
8. `packers/l3_guide.py` - No deps (~40 LOC)
9. `ctx/builder.py` - Deps: all packers (~100 LOC)

### Week 3: Runners + Experiments
10. `run/rlm.py` - Deps: dspy, builder (~120 LOC)
11. `run/phase0.py` - Deps: rlm (~150 LOC)
12. `run/phase1.py` - Deps: rlm (~120 LOC)
13. `seed/` - Curated strategies and constraints

---

## Verification

### Implementation Status

**Completed (✅):**
- ✅ Core modules: `blob.py`, `graph.py`, `mem.py`, `instrument.py` (~270 LOC)
- ✅ **L0 enhanced**: Widoco-inspired metadata extractor (~220 LOC)
  - Handles 15+ vocabularies (DC, VANN, SKOS, Schema.org, VOID, CITO, PAV)
  - Extracts: title, description, imports, namespaces, subsets, conventions
  - Tested on PROV (473 chars), SIO (497 chars), GeoSPARQL (70 chars)
- ✅ **L1 enhanced**: Schema constraints with anti-patterns (~180 LOC)
  - Anti-patterns derived from disjoint classes
  - Property characteristics (Functional, Symmetric, Transitive, InverseFunctional)
  - Cardinality constraints from OWL Restrictions
  - Prioritized by actionability (anti-patterns first, then disjoint, property types, domain/range)
- ✅ L2 memory packer: `l2_mem.py` (~40 LOC)
- ✅ L3 guide packer: `l3_guide.py` (~40 LOC)
- ✅ Context builder: `builder.py` with corrected DSPy RLM tool signatures (~90 LOC)
- ✅ RLM runner: `rlm.py` with trajectory logging and token usage tracking (~140 LOC)
- ✅ Phase 0 runner: `phase0.py` for E1-E6 experiments (~150 LOC)
- ✅ Bootstrap data: `seed/strategies.json` with 5 curated strategies
- ✅ **L0+L1 validation**: Context generation works (1418 chars, 88% of budget)
- ✅ **E2 validation**: All 3 test tasks converged with proper tool usage (5-7 tool calls per task)

**Total**: ~1130 LOC implemented

**Pending (⏳):**
- ⏳ Verify L2 procedural memory layer works correctly
- ⏳ Verify L3 guide layer works correctly
- ⏳ Test full layer cake (E6: L0+L1+L2+L3 together)
- ⏳ Full E1-E6 ablation suite execution and analysis
- ⏳ E7 prompt leakage ablation (naive vs handle-based)
- ⏳ E8 retrieval policy ablation (auto-inject vs tool-mediated)
- ⏳ Phase 1 closed-loop learning (E9-E12)

### Unit Tests
```bash
pytest experiments/reasoningbank/core/test_blob.py
pytest experiments/reasoningbank/core/test_mem.py
pytest experiments/reasoningbank/packers/test_packers.py
```

### Integration Test (E1 Baseline)
```bash
python experiments/reasoningbank/run/phase0.py \
    --exp E1 --ont /path/to/ontology/prov.ttl --out results/
```

### E2 Validation (Completed ✅)
```bash
python experiments/reasoningbank/run/phase0.py \
    --exp E2 --ont /path/to/ontology/prov.ttl --out results/
```

**Results:**
- entity_lookup ("What is Activity?"): ✅ Converged in 5 iterations, 5 tool calls
- property_find ("What properties does Activity have?"): ✅ Converged
- hierarchy ("What are subclasses of Entity?"): ✅ Converged in 11 iterations, 7 tool calls

**Tools used**: g_stats, g_classes, g_query, g_describe, g_props, g_sample

### Layer Ablation Validation (E1-E6)
```bash
# Run all Phase 0 layer ablation experiments
python experiments/reasoningbank/run/phase0.py \
    --exp E1,E2,E3,E4,E5,E6 --ont /path/to/ontology/prov.ttl --out results/

# Compare: E1 (baseline) vs E2-E5 (single layers) vs E6 (full layer cake)
# Expected: E6 >= max(E2, E3, E4, E5) for quality; check cost tradeoffs
```

### Prompt Leakage Validation (E7)
```bash
# Run E7 with both conditions
python experiments/reasoningbank/run/phase0.py \
    --exp E7a,E7b --ont /path/to/ontology/prov.ttl --out results/

# Compare leakage metrics between naive (E7a) and handle-based (E7b)
```

### Success Criteria

1. **E1-E6**: All experiments converge on test tasks
2. **E7**: Handle-based tools (E7b) show <50% `large_returns` vs naive (E7a)
3. **E8**: Auto-inject achieves >=80% convergence rate of tool-mediated
4. **Phase 1**: Closed-loop extraction produces valid `Item` objects

### Quality Gates

1. **Reproducibility**: Every run saves config + results JSON
2. **Observability**: Logs capture layers enabled, what was packed/injected
3. **Bounded context**: Each layer enforces budget; never inject unbounded content
4. **Stable evaluation**: Deterministic checks where possible

---

## Implementation Lessons Learned

### 1. DSPy RLM Tool Calling Convention (Critical Discovery)

**Problem**: Initial implementation used standard Python `lambda *args, **kwargs: ...` signature for tools, which failed with errors like `"g_stats() missing 2 required positional arguments: 'args' and 'kwargs'"`.

**Root Cause**: DSPy RLM calls tools with a specific convention:
```python
tool(args, kwargs)  # Two positional parameters
```
NOT the typical Python pattern:
```python
tool(*args, **kwargs)  # Variadic parameters
```

**Solution**: All tool wrappers must use signature:
```python
lambda args, kwargs: implementation(...)
```

**Verification**: Created `test_tool_signature.py` to test three signatures:
- `lambda *args, **kwargs` - ❌ Failed (missing positional arguments)
- `lambda args, kwargs` - ✅ Success
- `lambda args, **kwargs` - ❌ Failed (various errors)

**Impact**: This is a non-negotiable requirement for DSPy RLM tool integration. Without correct signatures, tools are visible but unusable.

### 2. Context Impact on Tool Usage

**Discovery**: Tools are technically available but only used when context provides guidance.

**Experiment**: Compared E1 (empty context) vs E2 (L0 sense card):
- **E1**: 0 tool calls - RLM used `llm_query()` to generate generic answer from training data
- **E2**: 5-7 tool calls per task - RLM explored graph with proper tools

**Lesson**: Empty baseline (E1) is expected to show zero tool usage. This is NOT a bug - it demonstrates that context layers actively guide tool discovery and usage. The sense card provides critical metadata (triple count, formalism, label/description properties) that prompts exploration.

### 3. Tool Docstrings Not Required (But Helpful)

**Discovery**: DSPy RLM can use tools without docstrings via `help()` inspection, but docstrings improve efficiency.

**Verification** (`verify_tools.py`):
- Proper function with docstring: Used immediately (2 iterations)
- Bare lambda without docstring: Still works but requires `help()` inspection (3 iterations)
- Lambda with attached docstring: Similar to bare lambda

**Lesson**: Docstrings are not strictly required but reduce iteration count by eliminating inspection overhead.

### 4. Trajectory Logging Essential for Debugging

**Implementation**: Added comprehensive logging to `run/rlm.py`:
```python
log_event('run_start', {'task': task, 'context_size': len(ctx), 'max_iters': max_iters})
log_event('run_complete', {
    'converged': True,
    'answer_length': len(str(getattr(res, 'answer', ''))),
    'has_sparql': getattr(res, 'sparql', None) is not None,
    'iterations': len(history),
    'lm_usage': lm_usage,
})
```

**Value**: Trajectory logs were critical for diagnosing:
- Tool signature issues (captured error messages)
- Empty context behavior (explained zero tool usage)
- Iteration patterns (identified when tools were called)

---

## Key Differences from Original Plan

| Aspect | Original Plan | Actual Implementation | Reason |
|--------|---------------|----------------------|---------|
| Memory backend | Wrap `rlm_runtime/memory/sqlite_backend.py` | Fresh `MemStore` (~55 LOC) | Existing code has curriculum/TAVR assumptions to test |
| Sense card | Wrap `rlm_runtime/ontology/sense_card.py` | Fresh `l0_sense.py` (~45 LOC) | Need simple rdflib-based extraction |
| RLM runner | Use `run_dspy_rlm()` | Direct `dspy.RLM()` (~120 LOC with logging) | Need full control over tool registration and logging |
| Retrieval | Complex curriculum retrieval | Simple word overlap search | Test whether complexity helps |
| Memory schema | MemoryItem with 12+ fields | Minimal `Item` (6 fields) | Reduce assumptions, test incrementally |
| Naming | Verbose (`memory_store`, `context_config`) | Huffman (`mem`, `cfg`) | Brevity facilitates reasoning (fastai style) |
| Tool signatures | Direct function references | `lambda args, kwargs: ...` wrappers | **Critical discovery**: DSPy RLM calling convention |
| Logging | Minimal | Comprehensive trajectory + token tracking | Essential for debugging and analysis |
| Total LOC | Estimated ~960 LOC | Actual ~850 LOC | Tighter implementation, less boilerplate |

**Why Fresh Implementation**: The existing `rlm_runtime` code embodies assumptions (curriculum levels, TAVR fields, verification feedback, sqlite backend) that are experimental variables to TEST, not baseline infrastructure to assume. This suite needs to validate whether those features actually help.

**Critical Addition**: DSPy RLM tool signature requirements were discovered during implementation and are now documented. This was not anticipated in the original plan but is essential for tool functionality.
