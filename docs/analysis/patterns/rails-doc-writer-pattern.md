# Rails Doc Writer Pattern Analysis

**Source:** https://gist.githubusercontent.com/dbreunig/bab62de16f173f040bb51453b32c6aa2/raw/6737e9ca9ce08f8ba75fa4bbe80e39d84919bd58/rails_doc_writer.py

## The Approach

```python
import dspy

# Load ENTIRE source tree into memory
def load_source_tree(root_dir: str) -> dict[str, Any]:
    """Recursively load the folder into a nested dict."""
    tree = {}
    for entry in os.listdir(root_dir):
        path = os.path.join(root_dir, entry)
        if os.path.isdir(path):
            tree[entry] = load_source_tree(path)  # Recursive
        else:
            with open(path, "r") as f:
                tree[entry] = f.read()  # Load entire file
    return tree

# Pass entire tree to RLM
class DocWriter(dspy.Signature):
    source_tree: dict[str, Any] = dspy.InputField()
    documentation: str = dspy.OutputField()

doc_writer = dspy.RLM(DocWriter, max_iterations=10, verbose=True)
result = doc_writer(source_tree=source_tree)
```

**Key characteristics:**
- **Load everything upfront** - Entire directory tree in memory
- **Pass as structured data** - Dict of files/dirs
- **No tools needed** - Everything accessible via dict traversal
- **Let RLM explore** - Agent can inspect any file via dict keys

## Comparison Matrix

| Aspect | Rails Doc Writer | Fabric Demo (Simple) | Current RLM |
|--------|-----------------|---------------------|-------------|
| **Data loading** | Load ALL files into dict | None (filesystem tools) | Load ontology into GraphMeta |
| **Context size** | Entire codebase | Minimal (instructions) | Sense card + meta summary |
| **Exploration** | Dict traversal in code | Filesystem tools (view/rg) | Bounded tools (search/sparql) |
| **Tools** | None | 3 general (view/rg/sparql) | 2 specialized (search/sparql) |
| **Progressive disclosure** | Manual (agent writes code) | Automatic (tool calls) | Automatic (tool calls) |
| **Memory usage** | High (all in RAM) | Low (read on demand) | Medium (ontology in RAM) |

## Applying This Pattern to Ontology Query Construction

### Option 1: Load Entire Ontology + Examples + Docs

```python
def load_ontology_context(ontology_dir: str) -> dict:
    """Load ontology, examples, and documentation into structured dict."""
    context = {
        'ontology': {},
        'examples': {},
        'documentation': {}
    }

    # Load core ontology
    context['ontology']['core'] = open(f'{ontology_dir}/core.ttl').read()

    # Load all example queries
    for example_file in glob(f'{ontology_dir}/examples/**/*.ttl'):
        name = example_file.stem
        context['examples'][name] = open(example_file).read()

    # Load documentation
    if exists(f'{ontology_dir}/AGENT_GUIDE.md'):
        context['documentation']['guide'] = open(f'{ontology_dir}/AGENT_GUIDE.md').read()

    return context

# Pass to RLM
class OntologyQueryConstructor(dspy.Signature):
    query: str = dspy.InputField(desc="User question")
    ontology_context: dict = dspy.InputField(desc="Full ontology context")

    answer: str = dspy.OutputField()
    sparql: str = dspy.OutputField()
    evidence: dict = dspy.OutputField()

rlm = dspy.RLM(OntologyQueryConstructor, max_iterations=8)
result = rlm(query="What is Activity?", ontology_context=ontology_context)
```

**Advantages:**
- Everything available to agent
- No tool surface needed
- Agent can traverse structure naturally
- Rich context (ontology + examples + docs)

**Disadvantages:**
- Large context window usage
- Doesn't work with remote endpoints
- May overwhelm model with too much data

---

### Option 2: Hybrid - Load Docs, Provide Tools for Data

```python
def load_documentation_context(ontology_dir: str) -> dict:
    """Load ONLY documentation, not the data."""
    context = {
        'guide': None,
        'example_queries': [],
        'prefixes': None
    }

    # Load agent guide
    guide_path = f'{ontology_dir}/AGENT_GUIDE.md'
    if exists(guide_path):
        context['guide'] = open(guide_path).read()

    # Load example queries (SPARQL only, not data)
    for example in glob(f'{ontology_dir}/examples/**/*.ttl'):
        # Extract just the sh:select query, not results
        context['example_queries'].append(extract_sparql_from_shacl(example))

    # Load prefixes
    context['prefixes'] = open(f'{ontology_dir}/examples/prefixes.ttl').read()

    return context

# Tools for querying
tools = {
    'sparql_query': make_sparql_query_tool(endpoint)
}

class OntologyQueryConstructor(dspy.Signature):
    query: str = dspy.InputField()
    documentation: dict = dspy.InputField(desc="Guides, examples, prefixes")

    answer: str = dspy.OutputField()
    sparql: str = dspy.OutputField()
    evidence: dict = dspy.OutputField()

rlm = dspy.RLM(
    OntologyQueryConstructor,
    max_iterations=8,
    tools=tools
)

result = rlm(
    query="What is Activity?",
    documentation=load_documentation_context('ontology/uniprot')
)
```

**Advantages:**
- Documentation in context (no tool calls needed to read)
- Tools for actual data querying
- Lower memory than loading everything
- Works with remote endpoints

**Disadvantages:**
- Agent can't explore file structure
- Requires curated documentation

---

### Option 3: Structured Ontology Dict (RLM Paper Style)

Following the Rails pattern more closely:

```python
def load_ontology_as_dict(ontology_path: str) -> dict:
    """Load ontology as structured dict, not RDF graph."""
    from rdflib import Graph

    g = Graph()
    g.parse(ontology_path)

    # Structure as dict
    ontology_dict = {
        'classes': {},
        'properties': {},
        'examples': {},
        'metadata': {}
    }

    # Extract classes
    for cls in g.subjects(RDF.type, OWL.Class):
        ontology_dict['classes'][str(cls)] = {
            'label': get_label(g, cls),
            'comment': get_comment(g, cls),
            'subClassOf': [str(p) for p in g.objects(cls, RDFS.subClassOf)],
            'examples': []
        }

    # Extract properties
    for prop in g.subjects(RDF.type, OWL.ObjectProperty):
        ontology_dict['properties'][str(prop)] = {
            'label': get_label(g, prop),
            'domain': [str(d) for d in g.objects(prop, RDFS.domain)],
            'range': [str(r) for r in g.objects(prop, RDFS.range)]
        }

    # Load examples from files
    for example_file in glob('ontology/uniprot/examples/**/*.ttl'):
        example = parse_shacl_example(example_file)
        ontology_dict['examples'][example['id']] = example

    return ontology_dict

# No tools needed - everything in dict
class OntologyExplorer(dspy.Signature):
    query: str = dspy.InputField()
    ontology: dict = dspy.InputField(desc="Structured ontology dict")

    answer: str = dspy.OutputField()
    sparql: str = dspy.OutputField()
    evidence: dict = dspy.OutputField()

rlm = dspy.RLM(OntologyExplorer, max_iterations=8)
result = rlm(query="What is Activity?", ontology=load_ontology_as_dict('prov.ttl'))
```

**Advantages:**
- Clean structured access
- No RDF graph queries needed
- Agent can traverse naturally: `ontology['classes']['prov:Activity']`
- Examples embedded in structure

**Disadvantages:**
- Pre-processing required
- Doesn't scale to massive ontologies
- Limited to local ontologies

---

## Key Insight from Rails Pattern

**The Rails doc writer approach eliminates tool surface entirely.**

Instead of:
```python
# Tool-based approach
view("app/models/user.rb")  # Tool call
rg("class User")            # Tool call
```

It does:
```python
# Dict-based approach
source_tree['app']['models']['user.rb']  # Direct access
```

**For ontology query construction:**

Instead of:
```python
# Current RLM
search_entity("Activity")         # Tool call
sparql_select("SELECT ...")       # Tool call
```

Or:
```python
# Simple approach
view("ontology/prov.ttl")         # Tool call
rg("Activity ontology/")          # Tool call
sparql_query("SELECT ...")        # Tool call
```

We could do:
```python
# Rails pattern
ontology['classes']['prov:Activity']            # Dict access
ontology['documentation']['guide']              # Dict access
ontology['examples']['entity_discovery_001']    # Dict access
```

**But wait - we still need SPARQL execution!**

The Rails pattern works because code writing doesn't require external execution. But SPARQL queries need to run against:
- Local graph (current RLM)
- Remote endpoint (simple approach)

So a pure Rails pattern isn't sufficient - we need SOME tool for SPARQL execution.

---

## Hybrid Architecture: Rails Pattern + Minimal Tools

**Best of both worlds:**

```python
def load_full_context(ontology_dir: str, endpoint: str = None) -> dict:
    """Load everything - docs, ontology, examples."""
    return {
        # Documentation (loaded in full)
        'documentation': {
            'agent_guide': open(f'{ontology_dir}/AGENT_GUIDE.md').read(),
            'prefixes': parse_prefixes(f'{ontology_dir}/examples/prefixes.ttl')
        },

        # Ontology (structured)
        'ontology': load_ontology_as_dict(f'{ontology_dir}/core.ttl'),

        # Examples (with SPARQL + descriptions)
        'examples': load_example_queries(f'{ontology_dir}/examples/'),

        # Endpoint info
        'endpoint': endpoint or 'local'
    }

# ONE tool: sparql_query
tools = {
    'sparql_query': make_sparql_query_tool(endpoint)
}

class QueryConstructor(dspy.Signature):
    query: str = dspy.InputField()
    context: dict = dspy.InputField(desc="Full ontology context (docs, schema, examples)")

    answer: str = dspy.OutputField()
    sparql: str = dspy.OutputField()
    evidence: dict = dspy.OutputField()

rlm = dspy.RLM(QueryConstructor, max_iterations=8, tools=tools)

# All context in one place, one tool for execution
result = rlm(
    query="What is Activity?",
    context=load_full_context('ontology/prov', endpoint='https://...')
)
```

**Agent workflow:**
```
1. Inspect context['documentation']['agent_guide']
   → Read: "prov:Activity is a class representing activities"

2. Inspect context['ontology']['classes']['prov:Activity']
   → See: properties, domains, ranges

3. Inspect context['examples']
   → Find: Example query for entity discovery

4. Construct SPARQL query
   → Based on examples + ontology structure

5. Execute: sparql_query("SELECT ?activity WHERE { ?activity a prov:Activity }")
   → Results stored in namespace

6. SUBMIT answer + evidence
```

**Advantages:**
- All documentation in context (no file reading tools needed)
- Structured ontology access (no schema exploration needed)
- Examples embedded (no SHACL parsing needed)
- One tool (sparql_query) for execution
- Works with remote endpoints

**Disadvantages:**
- Large context window usage
- Pre-processing required
- Doesn't scale to huge ontologies/docs

---

## Recommendations Based on Rails Pattern

### For Small-to-Medium Ontologies (< 10MB)

**Use Rails pattern:**
1. Load AGENT_GUIDE.md into context
2. Load structured ontology dict into context
3. Load example queries into context
4. Provide ONE tool: `sparql_query()`

**Expected result:**
- **Zero schema exploration** (everything in context)
- **Zero file reading** (docs loaded upfront)
- **Minimal tool calls** (just sparql_query for execution)
- **Fast convergence** (2-3 iterations)

### For Large Ontologies (> 10MB)

**Use hybrid pattern:**
1. Load AGENT_GUIDE.md into context (documentation only)
2. Provide filesystem tools (view/rg) for exploration
3. Provide `sparql_query()` for execution

**This is the simple approach we already identified.**

### For Massive Ontologies (> 100MB)

**Use current RLM pattern:**
1. Generate sense card (compressed affordances)
2. Provide bounded tools
3. Local graph for performance

---

## Critical Question: What Problem Does Rails Pattern Solve?

**Rails doc writer problem:**
- Need to understand code structure
- Need to see multiple files
- Need to cross-reference components
- **Solution:** Load everything, let agent explore

**Ontology query construction problem:**
- Need to understand ontology structure ← Same!
- Need to see examples ← Same!
- Need to construct SPARQL ← Different (requires execution)
- **Solution:** Load docs + ontology, provide ONE execution tool

**The insight:** Loading documentation + schema into context eliminates exploration overhead.

---

## Proposed Experiment

Implement **Rails-inspired approach** for ontology query construction:

```python
def run_rails_rlm(query: str, ontology_dir: str, endpoint: str):
    """Rails pattern: Load everything, minimal tools."""

    # Load full context
    context = {
        'guide': open(f'{ontology_dir}/AGENT_GUIDE.md').read(),
        'ontology': load_ontology_as_dict(f'{ontology_dir}/core.ttl'),
        'examples': load_example_queries(f'{ontology_dir}/examples/')
    }

    # ONE tool
    tools = {'sparql_query': make_sparql_query_tool(endpoint)}

    # RLM with rich context
    rlm = dspy.RLM(QueryConstructorSig, max_iterations=8, tools=tools)

    return rlm(query=query, full_context=context)
```

**Compare three approaches:**
1. **Rails pattern** - Everything in context, one tool
2. **Simple pattern** - Filesystem tools, docs on demand
3. **Current RLM** - Sense card, bounded tools

**Hypothesis:**
- Rails pattern wins for small ontologies (< 10MB)
- Simple pattern wins for medium ontologies (10-100MB)
- Current RLM wins for massive ontologies (> 100MB)

---

## Conclusion

The Rails doc writer pattern suggests a **fourth architecture option**:

**Load everything upfront, provide minimal execution tools.**

This could be the sweet spot:
- **Better than current RLM:** Full docs instead of sense card
- **Better than simple approach:** No file reading overhead
- **Trade-off:** Context window usage vs tool call overhead

**Recommended next step:** Prototype Rails pattern and compare all three approaches on eval tasks.
