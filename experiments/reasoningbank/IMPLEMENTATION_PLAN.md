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
│   ├── rlm_uniprot.py           # UniProt remote endpoint runner (~400 LOC)
│   ├── phase0.py                # E1-E8 layer experiments (~150 LOC)
│   ├── phase1.py                # E9-E12 closed-loop (~120 LOC)
│   └── phase1_uniprot.py        # Phase 1 for UniProt endpoint
│
├── tools/                       # SPARQL and memory tools
│   ├── sparql.py                # Remote SPARQL tools with handles
│   ├── endpoint.py              # Endpoint configuration registry
│   ├── memory_reflect.py        # Human-guided memory augmentation (~300 LOC)
│   └── memory_augment.py        # Automated memory analysis (experimental)
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

### 3. `core/mem.py` - Minimal Memory (Enhanced ✅)

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

    def search(self, q:str, k:int=6, polarity:str=None) -> list[dict]:
        "Return IDs + titles + descs + src. Filter by `polarity` ('success'|'failure'|'seed')."
        qwords = set(q.lower().split())
        scored = []
        for item in self._items.values():
            if polarity and item.src != polarity: continue  # Polarity filter
            words = set(f"{item.title} {item.desc} {' '.join(item.tags)}".lower().split())
            score = len(qwords & words)
            if score > 0: scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [{'id': o.id, 'title': o.title, 'desc': o.desc, 'src': o.src} for _,o in scored[:k]]

    def get(self, ids:list[str], max_n:int=3) -> list[Item]:
        "Return full items (hard cap enforced)."
        if len(ids) > max_n: raise ValueError(f"Requested {len(ids)} items, max is {max_n}")
        return [self._items[i] for i in ids if i in self._items]

    def quote(self, id:str, max_chars:int=500) -> str:
        "Return bounded excerpt of item content."
        item = self._items.get(id)
        if not item: return ""
        return item.content[:max_chars] + ("..." if len(item.content) > max_chars else "")

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

### 7. `packers/l2_mem.py` - Memory Formatting (Enhanced ✅)

```python
from core.mem import Item

def pack(items:list[Item], budget:int=2000) -> str:
    "Format memories with success/failure separation."
    success = [o for o in items if o.src == 'success']
    failure = [o for o in items if o.src == 'failure']
    seed = [o for o in items if o.src == 'seed']

    lines = []

    # Success strategies first (what to do)
    if success:
        lines.append('**Strategies** (what works):')
        for o in success:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    # Failure guardrails (what to avoid)
    if failure:
        lines.append('\n**Guardrails** (what to avoid):')
        for o in failure:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    # Seed items (general strategies)
    if seed:
        lines.append('\n**General Strategies**:')
        for o in seed:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    return '\n'.join(lines)[:budget]


def pack_separate(success:list[Item], failure:list[Item], budget:int=2000) -> str:
    "Pack pre-separated success/failure lists (for explicit k_success + k_failure)."
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
            # Top-K success + top-K failure retrieval
            k_success, k_failure = 2, 1
            success_hits = mem.search(task, k=k_success, polarity='success')
            failure_hits = mem.search(task, k=k_failure, polarity='failure')
            seed_hits = mem.search(task, k=1, polarity='seed')
            all_ids = [h['id'] for h in success_hits + failure_hits + seed_hits]
            if all_ids:
                items = mem.get(all_ids, max_n=len(all_ids))
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
- ✅ **L2 enhanced**: Polarity filtering + bounded excerpt + separated packer (~80 LOC)
  - `search()` now supports `polarity` filter ('success'|'failure'|'seed')
  - Added `quote(id, max_chars)` for bounded excerpts
  - Packer separates **Strategies** from **Guardrails** from **General Strategies**
  - Builder uses top-K success + top-K failure retrieval
  - Memory tools (`mem_search`, `mem_get`, `mem_quote`) exposed for Mode 2
- ✅ L3 guide packer: `l3_guide.py` (~40 LOC)
- ✅ Context builder: `builder.py` with corrected DSPy RLM tool signatures (~90 LOC)
- ✅ RLM runner: `rlm.py` with trajectory logging and token usage tracking (~140 LOC)
- ✅ Phase 0 runner: `phase0.py` for E1-E6 experiments (~150 LOC)
- ✅ Bootstrap data: `seed/strategies.json` with 5 curated strategies
- ✅ **L0+L1 validation**: Context generation works (1418 chars, 88% of budget)
- ✅ **E2 validation**: All 3 test tasks converged with proper tool usage (5-7 tool calls per task)

**Total**: ~1300 LOC implemented

**Recent Additions (2026-02):**
- ✅ **L1 schema v2**: Property type separation, SPARQL hints, NamedIndividuals (~250 LOC)
- ✅ **SPARQL tools fixes**: Prefix handling, API defaults (sparql_peek/slice)
- ✅ **UniProt remote runner**: `run/rlm_uniprot.py` with endpoint tools (~400 LOC)
- ✅ **Phase 1 UniProt**: `run/phase1_uniprot.py` closed-loop for remote endpoints
- ✅ **Memory reflection tool**: `tools/memory_reflect.py` for human-guided augmentation (~300 LOC)
- ✅ **Trajectory logging**: JSONL event streams for all runs

**Pending (⏳):**
- ⏳ Test full layer cake (E6: L0+L1+L2+L3 together)
- ⏳ Full E1-E6 ablation suite execution and analysis
- ⏳ E7 prompt leakage ablation (naive vs handle-based)
- ⏳ E8 retrieval policy ablation (auto-inject vs tool-mediated)
- ⏳ E10 consolidation (merge/supersede similar memories)
- ⏳ E11 forgetting (bounded memory bank)

### L2 Enhancement (Completed ✅)

**Changes made:**
- ✅ `core/mem.py`: Added polarity filtering to `search(q, k=6, polarity=None)` - filters by 'success'|'failure'|'seed'
- ✅ `core/mem.py`: Added `quote(id, max_chars=500)` - bounded excerpt function
- ✅ `packers/l2_mem.py`: Now separates **Strategies** (what works) from **Guardrails** (what to avoid) from **General Strategies**
- ✅ `packers/l2_mem.py`: Added `pack_separate()` for explicit k_success + k_failure retrieval
- ✅ `ctx/builder.py`: Uses top-K success + top-K failure + top-K seed retrieval
- ✅ `ctx/builder.py`: Exposed memory tools (`mem_search`, `mem_get`, `mem_quote`) for Mode 2 (tool-mediated retrieval)

**Example L2 packed output:**
```
**Strategies** (what works):

• **Use TYPE for class queries**
Always start SPARQL queries with ?s rdf:type <Class> to find instances.

• **Check subclass hierarchy**
When looking for entities, check rdfs:subClassOf hierarchy first.

**Guardrails** (what to avoid):

• **Avoid SELECT ***
Never use SELECT * in production. Always specify variables.

**General Strategies**:

• **Explore before querying**
Before writing complex queries, use g_classes() and g_props() to understand available types.
```

**All 8 verification checks passed** (see `test_l2_mem.py`)

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

---

## Remote SPARQL Endpoints: Agentic Discovery Architecture

This section documents the architecture for querying remote SPARQL endpoints (UniProt, Rhea, Wikidata, etc.) using an agentic discovery approach rather than pre-loaded static context.

### Key Insight: Discover, Don't Pre-Load

**Problem with static context**: Pre-loading endpoint descriptions into L0 assumes what the agent needs to know. This causes:
- Context bloat (26+ federated endpoints × metadata each)
- Stale information (endpoint capabilities change)
- Role confusion (static preambles can trigger refusals on biomedical queries)

**Solution**: Agent discovers endpoint capabilities through bounded tools, learning what it needs when it needs it.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  L0 Sense Card (existing approach - minimal)                    │
│  - Primary ontology metadata                                    │
│  - Mention: "Federated endpoints available via tools"           │
│  - NO static endpoint descriptions or role preambles            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agentic Discovery Tools                                        │
│                                                                 │
│  Static Discovery (from SHACL examples):                        │
│  - federated_endpoints(path) → Ref                              │
│  - endpoints_list(ref, limit) → [{name, url, example_count}]    │
│                                                                 │
│  Dynamic Discovery (from endpoints themselves):                 │
│  - service_desc(url) → Ref  (GET with content negotiation)      │
│  - service_desc_graphs(ref, limit) → [named graphs]             │
│  - service_desc_features(ref, limit) → [supported features]     │
│                                                                 │
│  Schema Exploration (from local ontology copies):               │
│  - ont_load(path) → Ref                                         │
│  - ont_classes(ref, limit) → [class URIs]                       │
│  - ont_properties(ref, limit) → [property URIs]                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SHACL Examples → Task Corpus                                   │
│                                                                 │
│  Examples are NOT procedural memory. They are TASKS:            │
│  - 636 competency questions (from UniProt SHACL examples)       │
│  - Agent runs on these → trajectories                           │
│  - Trajectories get judged → success/failure                    │
│  - Strategies extracted → L2 procedural memory                  │
│                                                                 │
│  What goes into L2:                                             │
│  - "When querying protein-disease associations, explore         │
│     up:Disease_Annotation class first" (STRATEGY)               │
│  NOT:                                                           │
│  - "Q: List proteins linked to Alzheimer's                      │
│     SPARQL: SELECT..." (RAW EXAMPLE)                            │
└─────────────────────────────────────────────────────────────────┘
```

### SPARQL 1.1 Service Description

Endpoints self-describe via [SPARQL 1.1 Service Description](https://www.w3.org/TR/sparql11-service-description/). This is accessed via HTTP GET on the endpoint URL with content negotiation:

```python
def service_desc(url: str) -> Ref:
    """Fetch endpoint service description.

    GET {url}
    Accept: text/turtle, application/rdf+xml;q=0.9

    Returns handle to parsed RDF graph.
    """
    resp = requests.get(
        url,
        headers={'Accept': 'text/turtle, application/rdf+xml;q=0.9'},
        timeout=30
    )
    g = Graph().parse(data=resp.text, format='turtle')

    # Return handle, not the graph
    return Ref(key, 'service_desc', len(g), len(resp.text), url)
```

The service description includes:
- `sd:namedGraph` - Available named graphs
- `sd:feature` - Supported features (UnionDefaultGraph, BasicFederatedQuery, etc.)
- `sd:defaultDataset` - Default dataset configuration
- `sd:resultFormat` - Supported result formats

### Tool Specifications (RLM Pattern)

All tools follow the established pattern:
- **Handles not payloads**: Return `Ref` with metadata
- **Two-phase retrieval**: Stats/list first, then bounded content
- **Source attribution**: All returns include `source`
- **Bounded returns**: Hard caps enforced
- **DSPy signatures**: `lambda args, kwargs:`

#### `tools/endpoint_tools.py` (~150 LOC)

```python
@dataclass
class Ref:
    key: str
    dtype: str      # 'service_desc', 'registry', 'ontology'
    rows: int       # triple/item count
    sz: int         # char count
    source: str     # URL or path for attribution

class EndpointTools:
    """RLM-friendly endpoint exploration tools."""

    # Static discovery (from SHACL examples)
    def federated_endpoints(self, ontology_path: str) -> Ref: ...
    def endpoints_list(self, ref_key: str, limit: int = 10) -> list[dict]: ...

    # Dynamic discovery (service description)
    def service_desc(self, url: str) -> Ref: ...
    def service_desc_stats(self, ref_key: str) -> dict: ...
    def service_desc_graphs(self, ref_key: str, limit: int = 20) -> dict: ...
    def service_desc_features(self, ref_key: str, limit: int = 20) -> dict: ...
    def service_desc_sample(self, ref_key: str, n: int = 10) -> dict: ...

    # DSPy-compatible interface
    def as_dspy_tools(self) -> dict[str, Callable]: ...
```

### SHACL Task Corpus

SHACL examples from `ontology/uniprot/examples/` become the **task corpus** for Phase 1 closed-loop learning:

#### `tools/shacl_tasks.py` (~80 LOC)

```python
@dataclass
class Task:
    id: str                    # Example filename
    query: str                 # Competency question (rdfs:comment)
    expected_sparql: str       # Reference SPARQL (sh:select)
    endpoint: str              # Target endpoint (schema:target)
    keywords: list[str]        # Tags (schema:keywords)

def load_shacl_tasks(ontology_path: str) -> list[Task]:
    """Load SHACL examples as tasks for ReasoningBank learning.

    These are NOT injected as context. They are TASKS the agent runs on.
    Successful trajectories get strategies extracted into L2.
    """
```

### Learning Flow

1. **Load task corpus**: `tasks = load_shacl_tasks('ontology/uniprot')`

2. **Agent runs on task**:
   ```python
   # Task: "List proteins associated with Alzheimer's disease"
   # Agent explores using tools:
   sd = service_desc('https://sparql.uniprot.org/sparql/')
   graphs = service_desc_graphs(sd.key)
   ont = ont_load('ontology/uniprot/core.owl')
   classes = ont_classes(ont.key, 20)
   # Agent constructs query based on exploration
   ```

3. **Judge trajectory**: Success/failure based on query validity and answer quality

4. **Extract strategy** (if successful):
   ```python
   Item(
       title="UniProt disease annotation pattern",
       content="""When querying protein-disease associations:
       1. Explore up:Disease_Annotation class
       2. Use up:annotation to link proteins to annotations
       3. Filter by annotation type
       Pattern: ?protein up:annotation ?ann . ?ann a up:Disease_Annotation""",
       src='success',
       tags=['uniprot', 'disease', 'annotation']
   )
   ```

5. **Store in L2**: Strategy becomes retrievable procedural memory

### File Structure (Updated)

```
experiments/reasoningbank/
├── tools/                       # SPARQL endpoint tools
│   ├── __init__.py
│   ├── endpoint_tools.py        # Service description + discovery (~150 LOC)
│   ├── shacl_tasks.py           # Task corpus loader (~80 LOC)
│   ├── discovery.py             # Federated endpoint discovery (EXISTS)
│   ├── uniprot_examples.py      # SHACL example parser (EXISTS)
│   └── sparql.py                # SPARQL query tools (EXISTS)
│
├── core/                        # Foundation (unchanged)
├── packers/                     # Layer packers (unchanged)
├── ctx/                         # Context builder (unchanged)
├── run/                         # Experiment runners (unchanged)
└── ...
```

### Integration with Phase 1 (E9-E12)

The SHACL task corpus enables closed-loop learning:

```python
# run/phase1.py (updated)

def run_closed_loop_sparql(
    ontology_path: str,
    mem: MemStore,
    max_tasks: int = 50
):
    """Run closed-loop learning on SHACL task corpus."""
    from tools.shacl_tasks import load_shacl_tasks

    tasks = load_shacl_tasks(ontology_path)[:max_tasks]

    for task in tasks:
        # Run with endpoint tools available
        res = run_with_endpoint_tools(task.query, task.endpoint, mem)

        # Judge (can compare to expected_sparql)
        j = judge_sparql(res, task.expected_sparql)

        # Extract strategy if successful
        if j['success']:
            items = extract_strategy(res, task)
            for item in items:
                mem.add(item)
```

### Why This Matters for Refusals

**The key insight**: Biomedical queries trigger refusals due to **role ambiguity**, not topic sensitivity.

- **Static preamble** approach: "You are a SPARQL query interface to UniProt..."
  - Still triggers refusals because the competency question appears without context

- **Agentic discovery** approach: Agent explores endpoints, discovers capabilities, constructs queries
  - The exploration trajectory provides natural context
  - Agent's actions demonstrate it's doing database retrieval, not giving medical advice
  - Successful trajectories teach strategies like "frame results as database records"

The strategies extracted from successful trajectories implicitly encode how to frame queries to minimize refusals, without explicit "role framing" text.

---

## Human-in-the-Loop Procedural Memory Augmentation

Beyond automatic extraction, procedural memory can be augmented through human-guided analysis of agent trajectories.

### Workflow

```
┌─────────────────────────────────────────────────────────┐
│  1. Review trajectory together                          │
│     (Claude Code explains agent behavior step by step)  │
│                        ↓                                │
│  2. Identify issue                                      │
│     ("Agent wasted iterations because X")               │
│                        ↓                                │
│  3. Craft procedural memory                             │
│     (Human dictates domain knowledge, tool records)     │
│                        ↓                                │
│  4. Re-run with memory                                  │
│     (See if behavior changes)                           │
│                        ↓                                │
│  5. Evaluate & iterate                                  │
└─────────────────────────────────────────────────────────┘
```

### Rationale

- **LLM extraction has gaps**: Automatic extraction may miss domain-specific patterns that a human expert recognizes
- **Technical nuances**: SPARQL/RDF patterns, ontology conventions, and API behaviors may not be in training data
- **Iterative refinement**: Testing memory impact on agent behavior validates the memory's usefulness
- **Scale concerns**: We don't yet know how the system behaves with large memory stores, so careful human curation helps

### Tool: `memory_reflect.py`

A minimal tool supporting the human-in-the-loop workflow:

```bash
# View trajectory for analysis
python tools/memory_reflect.py -t results/task.jsonl -m memories.json \
    --hint "describe" --verbose

# Add memory based on human insight
python tools/memory_reflect.py -t results/task.jsonl -m memories.json \
    --hint "The agent should retrieve all results before formatting answer" \
    --save memories.json --interactive

# Compare before/after trajectories
python tools/memory_reflect.py -t results/after.jsonl --compare results/before.jsonl \
    -m memories.json --hint "What made the second run faster?"
```

### Integration with Phase 1

Human-in-the-loop augmentation complements automatic extraction (E9):
- **E9 (automatic)**: Judge → extract → persist (append-only)
- **Human-guided**: Review → identify → craft → test → refine

Both feed into E10 (consolidation) and E11 (pruning) for memory management at scale.

---

## Recent Implementation Updates (2026-02)

### L1 Schema Enhancements ✅

**File**: `packers/l1_schema.py`

Enhanced to support:
1. **Property type separation**: ObjectProperty, DatatypeProperty, AnnotationProperty categorized separately
2. **SPARQL hints**: Generated tips like "Use `rdfs:subClassOf+` for transitive closure"
3. **NamedIndividuals extraction**: Enum-like values grouped by class type (e.g., UniProt Rank, Organelle)
4. **Schema.org pattern support**: Handles `domainIncludes`/`rangeIncludes` in addition to `rdfs:domain`/`rdfs:range`

**Tested on**: SIO (1140 props), DOLCE/DUL (178 props), GeoSPARQL (55 props), UniProt (138 props), SKOS (27 props), Schema.org (1507 props)

### SPARQL Tools Fixes ✅

**File**: `tools/sparql.py`

1. **Prefix handling fix**: Always prepend default prefixes (rdfs, owl, rdf, etc.) regardless of user-defined prefixes. Previously, property paths like `rdfs:subClassOf+` would fail if the query included ANY prefix declaration.

2. **API defaults fix**: Increased default limits to reduce wasted iterations:
   - `sparql_peek`: default 5 → 20 rows, hard cap 20 → 50
   - `sparql_slice`: default end 10 → `default_limit` (100)
   - `ResultStore.slice`: hard cap 50 → 100

**Impact**: protein_properties task improved from 10 → 5 iterations (50% reduction)

### UniProt Procedural Memory Baseline ✅

**File**: `results/phase1_uniprot_memory.json`

5 extracted memories from initial UniProt runs:
1. "Query Class Definition Using rdfs:comment Property"
2. "Finding Class Properties via rdfs:domain Pattern"
3. "Query Class Hierarchy with Transitive Subclass Pattern"
4. (2 near-duplicates to be consolidated)

### Iteration Comparison Results

| Task | No Memory | With Memory | With API Fix |
|------|-----------|-------------|--------------|
| protein_lookup | 6 | 4 | 4 |
| protein_properties | 9 | 10 | **5** |
| annotation_types | 12 | 12 | **8** |

The API fix had more impact than procedural memory for these tasks, indicating tool design is as important as memory content.
