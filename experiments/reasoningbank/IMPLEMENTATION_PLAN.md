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

### 5. `packers/l0_sense.py` - Ontology Sense Card

```python
from rdflib import Graph, RDF, RDFS, OWL, SKOS

def extract(g:Graph) -> dict:
    "Extract ontology metadata via rdflib."
    # Detect label property
    label_prop = 'rdfs:label'
    if list(g.triples((None, SKOS.prefLabel, None))): label_prop = 'skos:prefLabel'

    # Detect desc property
    desc_prop = 'rdfs:comment'
    if list(g.triples((None, SKOS.definition, None))): desc_prop = 'skos:definition'

    # Detect formalism
    n_restrict = len(list(g.subjects(RDF.type, OWL.Restriction)))
    n_disjoint = len(list(g.triples((None, OWL.disjointWith, None))))
    if n_restrict > 0 or n_disjoint > 0: formalism = 'OWL-DL'
    elif list(g.subjects(RDF.type, OWL.Class)):      formalism = 'OWL-Lite'
    elif list(g.triples((None, RDFS.subClassOf, None))): formalism = 'RDFS'
    else: formalism = 'RDF'

    return {
        'triples': len(g),
        'classes': len(list(g.subjects(RDF.type, OWL.Class))),
        'props': len(list(g.subjects(RDF.type, OWL.ObjectProperty))),
        'label': label_prop,
        'desc': desc_prop,
        'formalism': formalism,
    }

def pack(g:Graph, budget:int=600) -> str:
    "Pack sense card into bounded markdown."
    s = extract(g)
    lines = [
        f"**Size**: {s['triples']} triples, {s['classes']} classes, {s['props']} properties",
        f"**Formalism**: {s['formalism']}",
        f"**Labels**: use `{s['label']}`",
        f"**Descriptions**: use `{s['desc']}`",
    ]
    return '\n'.join(lines)[:budget]
```

### 6. `packers/l1_schema.py` - Schema Constraints

```python
from rdflib import Graph, RDFS, OWL

def extract(g:Graph) -> dict:
    "Extract domain/range constraints from ontology."
    dr = []
    for p in g.subjects(RDFS.domain, None):
        doms = list(g.objects(p, RDFS.domain))
        rngs = list(g.objects(p, RDFS.range))
        if doms and rngs:
            dr.append((str(p).split('/')[-1], str(doms[0]).split('/')[-1], str(rngs[0]).split('/')[-1]))

    disj = [(str(a).split('/')[-1], str(b).split('/')[-1])
            for a,_,b in g.triples((None, OWL.disjointWith, None))]

    func = [str(p).split('/')[-1] for p in g.subjects(RDF.type, OWL.FunctionalProperty)]

    return {'domain_range': dr, 'disjoint': disj, 'functional': func}

def pack(g:Graph, budget:int=1000) -> str:
    "Pack constraints as bullet list."
    c = extract(g)
    lines = ['**Schema Constraints**:']
    for p,d,r in c['domain_range'][:15]:
        lines.append(f"- `{p}`: {d} → {r}")
    if c['disjoint']:
        lines.append(f"**Disjoint**: {', '.join(f'{a}⊥{b}' for a,b in c['disjoint'][:5])}")
    if c['functional']:
        lines.append(f"**Functional**: {', '.join(c['functional'][:5])}")
    return '\n'.join(lines)[:budget]
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

    def tools(self, store:Store, g:Graph) -> dict:
        "Build tool dict for dspy.RLM."
        G._store = store
        ref = G.g_load.__wrapped__(g) if hasattr(G.g_load, '__wrapped__') else None
        # Pre-load graph if path provided
        return {
            'g_stats': G.g_stats,
            'g_query': G.g_query,
            'g_sample': G.g_sample,
            'g_classes': G.g_classes,
            'g_props': G.g_props,
            'g_describe': G.g_describe,
            'ctx_peek': store.peek,
            'ctx_slice': store.slice,
            'ctx_stats': store.stats,
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

### Unit Tests
```bash
pytest experiments/reasoningbank/core/test_blob.py
pytest experiments/reasoningbank/core/test_mem.py
pytest experiments/reasoningbank/packers/test_packers.py
```

### Integration Test (E1 Baseline)
```bash
python -m experiments.reasoningbank.run.phase0 \
    --exp E1 --ont ontology/prov.ttl --out results/
```

### Layer Ablation Validation (E1-E6)
```bash
# Run all Phase 0 layer ablation experiments
python -m experiments.reasoningbank.run.phase0 \
    --exp E1,E2,E3,E4,E5,E6 --ont ontology/prov.ttl --out results/

# Compare: E1 (baseline) vs E2-E5 (single layers) vs E6 (full layer cake)
# Expected: E6 >= max(E2, E3, E4, E5) for quality; check cost tradeoffs
```

### Prompt Leakage Validation (E7)
```bash
# Run E7 with both conditions
python -m experiments.reasoningbank.run.phase0 \
    --exp E7a,E7b --ont ontology/prov.ttl --out results/

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

## Key Differences from Original Plan

| Original | Updated |
|----------|---------|
| Wrap `rlm_runtime/memory/sqlite_backend.py` | Fresh `MemStore` (~80 LOC) |
| Wrap `rlm_runtime/ontology/sense_card.py` | Fresh `l0_sense.py` (~60 LOC) |
| Use `run_dspy_rlm()` | Direct `dspy.RLM()` |
| Complex curriculum retrieval | Simple word overlap search |
| MemoryItem with 12+ fields | Minimal `Item` (6 fields) |
| Verbose naming (`memory_store`, `context_config`) | Huffman naming (`mem`, `cfg`) |

**Why**: The existing code embodies assumptions (curriculum levels, TAVR fields, verification feedback) that are experimental variables, not baseline infrastructure.
