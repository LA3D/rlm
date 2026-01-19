# Recursive Language Models with the Solveit Stack

This document summarizes how the Recursive Language Model (RLM) approach to context engineering can be implemented using Solveit's existing infrastructure.

## Background

### The RLM Paradigm

Recursive Language Models (Zhang et al., 2025) introduce a paradigm shift in handling long contexts:

> "Long prompts should not be fed into the neural network directly but should instead be treated as part of the environment that the LLM can symbolically interact with."

**Key insight**: Replace `llm.completion(prompt)` with `rlm.completion(prompt)` where the prompt is offloaded as a variable in a REPL environment that the LM can programmatically examine, decompose, and recursively call itself over.

### Why This Matters

Traditional approaches hit a fundamental limitation: even with agentic decomposition, **the input itself cannot scale beyond the context window**. RLMs solve this by:

1. **Externalizing context**: The context lives in the REPL, not in the LLM's attention
2. **Programmatic access**: The model decides *what* parts of context to look at and *when*
3. **Recursive delegation**: Sub-LLMs handle chunks, results are aggregated
4. **Infinite scaling**: Can handle inputs 2 orders of magnitude beyond model context windows

## Solveit's Existing Capabilities

Solveit already has much of the infrastructure needed for RLM-style context engineering:

### Symbol Manipulation (dialoghelper/inspecttools)

| Tool | Purpose | RLM Equivalent |
|------|---------|----------------|
| `resolve(sym)` | Navigate dotted paths to Python objects | `context` variable access |
| `symlen(sym)` | Get length of symbol | `len(context)` |
| `symslice(sym, start, end)` | Slice contents | `context[start:end]` |
| `symsearch(sym, term, regex)` | Search with regex | `re.finditer(...)` |
| `gettype(sym)` | Get type | `type(context)` |
| `getdir(sym)` | List attributes | `dir(context)` |
| `getval(sym)` | Get repr of value | `print(repr(...))` |
| `getnth(sym, n)` | Get nth value from dict | Indexing |
| `_last` | Chain results | Variable persistence |

### Source Inspection (dialoghelper/tracefunc)

Solveit has capabilities RLM lacks:

| Tool | Purpose |
|------|---------|
| `symsrc(sym)` | Get source code of any symbol |
| `tracetool(sym, args, kwargs, target_func)` | Trace execution with per-line variable snapshots |
| `showsrc(sym)` | Add source to dialog as note |

### What's Missing

The key RLM capability not yet in Solveit:

1. **`llm_query(prompt)`** - Spawn sub-LLM calls from within tool execution
2. **`llm_query_batched(prompts)`** - Concurrent sub-LLM calls for parallel processing

## Implementation with Claudette

Claudette (https://claudette.answer.ai) provides the LLM interface for Solveit. Here's how to implement the missing pieces:

### llm_query - Single Sub-LLM Call

```python
#| export
def llm_query(
    prompt: str,           # The prompt to send to the sub-LLM
    model: str = None,     # Model to use (default: claude-sonnet-4-20250514)
    max_tokens: int = 4096 # Maximum response tokens
) -> str:
    """Query a sub-LLM from within tool execution.

    Use for analyzing chunks of context that are too large to fit in main context.
    The sub-LLM has a fresh context window (~500K chars) for processing.

    Examples:
    - `llm_query(f"Summarize this section: {chunk}")`
    - `llm_query(f"Extract all dates from: {document}")`
    - `llm_query(f"Answer based on this evidence: {context}", model="claude-opus-4-20250514")`
    """
    from claudette import Client
    client = Client(model or "claude-sonnet-4-20250514")
    response = client([prompt], maxtok=max_tokens)
    return response.content[0].text
```

### llm_query_batched - Parallel Sub-LLM Calls

```python
#| export
def llm_query_batched(
    prompts: list[str],    # List of prompts to process concurrently
    model: str = None,     # Model to use for all queries
    max_tokens: int = 4096 # Maximum response tokens per query
) -> list[str]:
    """Query sub-LLM with multiple prompts concurrently.

    Much faster than sequential llm_query calls when you have multiple
    independent queries. Results are returned in the same order as input prompts.

    Examples:
    - Process 10 document chunks in parallel:
      `answers = llm_query_batched([f"Summarize: {c}" for c in chunks])`
    - Extract info from multiple sections:
      `results = llm_query_batched([f"Find dates in: {s}" for s in sections])`
    """
    import asyncio
    from claudette import AsyncChat

    model = model or "claude-sonnet-4-20250514"

    async def _query(p: str) -> str:
        chat = AsyncChat(model)
        r = await chat(p, maxtok=max_tokens)
        return r.content[0].text

    async def _run_all():
        return await asyncio.gather(*[_query(p) for p in prompts])

    # Handle case where we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
        # If in a running loop, create tasks
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(_run_all())
    except RuntimeError:
        return asyncio.run(_run_all())
```

### Optional: Depth Tracking for Recursion Limits

```python
#| export
import threading

_depth_local = threading.local()

def _get_depth() -> int:
    return getattr(_depth_local, 'depth', 0)

def _set_depth(d: int):
    _depth_local.depth = d

def llm_query_recursive(
    prompt: str,
    model: str = None,
    max_depth: int = 2
) -> str:
    """Query sub-LLM with depth tracking to prevent infinite recursion.

    When max_depth is reached, falls back to direct completion without
    further recursive capability.
    """
    current_depth = _get_depth()
    if current_depth >= max_depth:
        # At max depth, just do a simple completion
        from claudette import Client
        client = Client(model or "claude-sonnet-4-20250514")
        return client([prompt]).content[0].text

    # Increment depth for sub-call
    _set_depth(current_depth + 1)
    try:
        return llm_query(prompt, model)
    finally:
        _set_depth(current_depth)
```

## Context Management Strategies

The RLM paper identifies several effective strategies that work well with Solveit's tools:

### 1. Iterative Chunking

```python
# Using Solveit tools + llm_query
chunks = symslice('context', 0, 10000)  # First chunk
buffer = llm_query(f"Extract key facts from: {chunks}")

# Continue with next chunk, building on buffer
next_chunk = symslice('context', 10000, 20000)
buffer = llm_query(f"Previous findings: {buffer}\n\nExtract more from: {next_chunk}")
```

### 2. Parallel Analysis with Batching

```python
# Split context into chunks
context_len = symlen('context')
chunk_size = context_len // 10
chunks = [symslice('context', i*chunk_size, (i+1)*chunk_size) for i in range(10)]

# Analyze all chunks in parallel
prompts = [f"Summarize this section:\n{chunk}" for chunk in chunks]
summaries = llm_query_batched(prompts)

# Aggregate results
final = llm_query(f"Combine these summaries into a coherent answer:\n" +
                  "\n---\n".join(summaries))
```

### 3. Structure-Aware Chunking

```python
# Use symsearch to find structure
headers = symsearch('context', r'^## .+$', regex=True)

# Extract sections between headers
sections = []
for i, (match, start, end) in enumerate(headers):
    section_start = start
    section_end = headers[i+1][1] if i+1 < len(headers) else symlen('context')
    sections.append(symslice('context', section_start, section_end))

# Process each section
results = llm_query_batched([f"Analyze section '{h}':\n{s}"
                             for (h,_,_), s in zip(headers, sections)])
```

### 4. Combining with tracetool for Code Analysis

```python
# Trace a function to understand behavior
trace = tracetool('target_function', args=[test_input])

# Use sub-LLM to explain the trace
explanation = llm_query(f"""
Analyze this execution trace and explain what the function does:
{trace}

Focus on:
1. What inputs it receives
2. How it transforms data
3. What it returns
""")
```

## Architecture Comparison

| Aspect | Original RLM | Solveit Implementation |
|--------|--------------|------------------------|
| **REPL Environment** | Sandboxed exec() | Jupyter kernel (persistent) |
| **Context Storage** | File + variable | Dialog context + symbols |
| **Sub-LLM Interface** | Socket to LMHandler | Direct claudette API |
| **Iteration Control** | Auto until FINAL() | User-driven dialog |
| **Tool Discovery** | Hardcoded in prompt | `&tool` syntax + schemas |
| **Source Inspection** | Not available | `symsrc`, `tracetool` |
| **Cost Tracking** | Per-handler | `client.cost` per call |

## Advantages of Solveit Approach

1. **Richer introspection**: `tracefunc` provides execution traces RLM lacks
2. **Persistent state**: Jupyter kernel maintains variables across interactions
3. **User control**: Dialog-driven rather than autonomous loop
4. **Tool composability**: Chain `_last` results between tools
5. **Visibility**: All tool calls visible in dialog history

## Trade-offs

1. **Manual orchestration**: User guides the decomposition (vs RLM's auto-loop)
2. **No automatic depth limiting**: Must implement if recursive sub-calls needed
3. **Context still visible**: Main model sees tool results (vs RLM's externalization)

## Application: Ontology-Based SPARQL Query Construction

A compelling application of RLM is **ontology-guided SPARQL query construction**, where an LLM agent uses the ontology to understand how to construct valid queries.

### The Challenge

Ontologies present a perfect RLM use case:

| Challenge | Why RLM Helps |
|-----------|---------------|
| **Size** | Ontologies can have thousands of classes/properties—too large for context |
| **Structure** | Hierarchical (subClassOf, subPropertyOf) requires navigation |
| **Vocabulary discovery** | Must find correct URIs for concepts in natural language |
| **Domain/Range constraints** | Properties have type restrictions that must be respected |
| **Query validation** | Generated SPARQL must be syntactically and semantically valid |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Natural Language Query                  │
│              "Find all proteins that interact with ACE2"         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Root LLM Agent                            │
│  • Analyzes query intent                                         │
│  • Orchestrates ontology exploration                             │
│  • Constructs SPARQL incrementally                               │
└─────────────────────────────────────────────────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │ Ontology     │    │ Schema       │    │ Query        │
    │ Explorer     │    │ Analyzer     │    │ Validator    │
    │ (sub-LLM)    │    │ (sub-LLM)    │    │ (tool)       │
    └──────────────┘    └──────────────┘    └──────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Externalized Ontology Context                   │
    │  • Classes, properties, restrictions                         │
    │  • Loaded as navigable Python objects                        │
    │  • Too large for direct LLM context                          │
    └─────────────────────────────────────────────────────────────┘
```

### Ontology Exploration Tools

```python
#| export
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

def load_ontology(path_or_url: str) -> Graph:
    """Load an ontology into an RDFLib graph for exploration."""
    g = Graph()
    g.parse(path_or_url)
    return g

def onto_classes(graph: Graph, limit: int = 100) -> list[dict]:
    """Get all classes in the ontology with labels and comments."""
    query = """
    SELECT ?class ?label ?comment WHERE {
        ?class a owl:Class .
        OPTIONAL { ?class rdfs:label ?label }
        OPTIONAL { ?class rdfs:comment ?comment }
    } LIMIT ?limit
    """.replace("?limit", str(limit))
    return [{"uri": str(r[0]), "label": str(r[1] or ""), "comment": str(r[2] or "")}
            for r in graph.query(query)]

def onto_properties(graph: Graph, limit: int = 100) -> list[dict]:
    """Get all properties with domain/range information."""
    query = """
    SELECT ?prop ?label ?domain ?range WHERE {
        { ?prop a owl:ObjectProperty } UNION { ?prop a owl:DatatypeProperty }
        OPTIONAL { ?prop rdfs:label ?label }
        OPTIONAL { ?prop rdfs:domain ?domain }
        OPTIONAL { ?prop rdfs:range ?range }
    } LIMIT ?limit
    """.replace("?limit", str(limit))
    return [{"uri": str(r[0]), "label": str(r[1] or ""),
             "domain": str(r[2] or ""), "range": str(r[3] or "")}
            for r in graph.query(query)]

def onto_search(graph: Graph, term: str, search_type: str = "class") -> list[dict]:
    """Search for classes or properties matching a term (case-insensitive)."""
    if search_type == "class":
        query = f"""
        SELECT ?entity ?label ?comment WHERE {{
            ?entity a owl:Class .
            ?entity rdfs:label ?label .
            FILTER(CONTAINS(LCASE(?label), LCASE("{term}")))
            OPTIONAL {{ ?entity rdfs:comment ?comment }}
        }}
        """
    else:
        query = f"""
        SELECT ?entity ?label ?domain ?range WHERE {{
            {{ ?entity a owl:ObjectProperty }} UNION {{ ?entity a owl:DatatypeProperty }}
            ?entity rdfs:label ?label .
            FILTER(CONTAINS(LCASE(?label), LCASE("{term}")))
            OPTIONAL {{ ?entity rdfs:domain ?domain }}
            OPTIONAL {{ ?entity rdfs:range ?range }}
        }}
        """
    return [dict(zip(["uri", "label", "comment"] if search_type == "class"
                     else ["uri", "label", "domain", "range"],
                     [str(x) if x else "" for x in r]))
            for r in graph.query(query)]

def onto_class_hierarchy(graph: Graph, class_uri: str, depth: int = 2) -> dict:
    """Get superclasses and subclasses of a class."""
    uri = URIRef(class_uri)

    def get_supers(cls, d):
        if d == 0: return []
        supers = list(graph.objects(cls, RDFS.subClassOf))
        return [{"uri": str(s), "supers": get_supers(s, d-1)} for s in supers if isinstance(s, URIRef)]

    def get_subs(cls, d):
        if d == 0: return []
        subs = list(graph.subjects(RDFS.subClassOf, cls))
        return [{"uri": str(s), "subs": get_subs(s, d-1)} for s in subs if isinstance(s, URIRef)]

    return {"class": class_uri, "superclasses": get_supers(uri, depth), "subclasses": get_subs(uri, depth)}

def onto_properties_for_class(graph: Graph, class_uri: str) -> list[dict]:
    """Get all properties where the class is in the domain."""
    query = f"""
    SELECT ?prop ?label ?range WHERE {{
        ?prop rdfs:domain <{class_uri}> .
        OPTIONAL {{ ?prop rdfs:label ?label }}
        OPTIONAL {{ ?prop rdfs:range ?range }}
    }}
    """
    return [{"uri": str(r[0]), "label": str(r[1] or ""), "range": str(r[2] or "")}
            for r in graph.query(query)]
```

### SPARQL Query Construction Tool

```python
#| export
def sparql_query(
    endpoint: str,
    query: str,
    timeout: int = 30
) -> dict:
    """Execute a SPARQL query against an endpoint.

    Returns:
        {"success": True, "results": [...]} or
        {"success": False, "error": "..."}
    """
    from SPARQLWrapper import SPARQLWrapper, JSON

    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(timeout)

    try:
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])
        return {"success": True, "results": bindings, "count": len(bindings)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def validate_sparql(query: str) -> dict:
    """Validate SPARQL syntax without executing."""
    from rdflib.plugins.sparql import prepareQuery
    try:
        prepareQuery(query)
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "error": str(e)}
```

### RLM-Style Query Construction Workflow

```python
# Example: Constructing a SPARQL query with RLM approach

# 1. Load ontology as external context (not in LLM attention)
ontology = load_ontology("https://example.org/biomedical.owl")

# 2. User's natural language query
user_query = "Find all proteins that interact with ACE2"

# 3. Use sub-LLM to identify key concepts
concepts = llm_query(f"""
Extract the key domain concepts from this query that we need to find in an ontology:
Query: {user_query}

Return as JSON: {{"concepts": ["concept1", "concept2"], "relationships": ["rel1"]}}
""")
# Result: {"concepts": ["protein", "ACE2"], "relationships": ["interacts with"]}

# 4. Search ontology for each concept (parallel)
search_prompts = []
for concept in ["protein", "ACE2", "interacts with"]:
    # Search returns subset of ontology matching term
    class_matches = onto_search(ontology, concept, "class")
    prop_matches = onto_search(ontology, concept, "property")
    search_prompts.append(f"""
    For the concept "{concept}", which of these ontology terms is the best match?

    Classes: {class_matches[:10]}
    Properties: {prop_matches[:10]}

    Return the URI of the best match, or "NOT_FOUND".
    """)

matches = llm_query_batched(search_prompts)
# Result: ["http://onto.org/Protein", "http://onto.org/ACE2", "http://onto.org/interactsWith"]

# 5. Get schema details for matched terms
protein_props = onto_properties_for_class(ontology, "http://onto.org/Protein")
ace2_hierarchy = onto_class_hierarchy(ontology, "http://onto.org/ACE2")

# 6. Use sub-LLM to construct query with schema context
sparql = llm_query(f"""
Construct a SPARQL query to answer: {user_query}

Use these ontology terms:
- Protein class: http://onto.org/Protein
- ACE2 class: http://onto.org/ACE2
- interactsWith property: http://onto.org/interactsWith

Properties available on Protein: {protein_props}

ACE2 hierarchy (it may be a subclass): {ace2_hierarchy}

Return only the SPARQL query, no explanation.
""")

# 7. Validate before executing
validation = validate_sparql(sparql)
if not validation["valid"]:
    # Use sub-LLM to fix
    sparql = llm_query(f"""
    This SPARQL query has an error: {validation["error"]}

    Query: {sparql}

    Fix the query and return only the corrected SPARQL.
    """)

# 8. Execute
results = sparql_query("https://sparql.example.org/query", sparql)
```

### Solveit Tool Integration

These tools integrate with Solveit's existing inspecttools pattern:

```python
#| export
def onto_explore(
    sym: str,  # Symbol path to RDFLib Graph object
    action: str,  # "classes", "properties", "search", "hierarchy", "props_for"
    **kwargs
) -> str:
    """Explore an ontology loaded as a Python symbol.

    Actions:
    - classes: List all classes (limit=100)
    - properties: List all properties (limit=100)
    - search: Search for term (term=str, search_type="class"|"property")
    - hierarchy: Get class hierarchy (class_uri=str, depth=2)
    - props_for: Get properties for class (class_uri=str)

    Examples:
    - onto_explore("my_onto", "search", term="protein", search_type="class")
    - onto_explore("my_onto", "hierarchy", class_uri="http://onto.org/Gene")
    """
    import json
    graph = resolve(sym)

    if action == "classes":
        return json.dumps(onto_classes(graph, kwargs.get("limit", 100)), indent=2)
    elif action == "properties":
        return json.dumps(onto_properties(graph, kwargs.get("limit", 100)), indent=2)
    elif action == "search":
        return json.dumps(onto_search(graph, kwargs["term"], kwargs.get("search_type", "class")), indent=2)
    elif action == "hierarchy":
        return json.dumps(onto_class_hierarchy(graph, kwargs["class_uri"], kwargs.get("depth", 2)), indent=2)
    elif action == "props_for":
        return json.dumps(onto_properties_for_class(graph, kwargs["class_uri"]), indent=2)
    else:
        return f"Unknown action: {action}"
```

### Why RLM Excels Here

| Traditional Approach | RLM Approach |
|---------------------|--------------|
| Stuff entire ontology in prompt | Ontology externalized, explored on-demand |
| Hope LLM remembers all classes | Sub-LLM searches specific subsets |
| Single-shot query generation | Iterative: find terms → get schema → construct → validate |
| Fails on large ontologies (>1000 classes) | Scales to arbitrary ontology size |
| No validation feedback | Validate and fix with sub-LLM |

### Foundational Graph Manipulation Tools

The RLM paper provides tools for strings and lists. Graphs require analogous operations:

| String/List Operation | Graph Equivalent | Purpose |
|-----------------------|------------------|---------|
| `len(context)` | `graph_size(g)` | Count triples, nodes, edges |
| `context[start:end]` | `graph_slice(g, pattern)` | Extract subgraph by pattern |
| `re.search(pattern, context)` | `graph_search(g, term)` | Find nodes matching criteria |
| `context[i]` | `graph_get(g, uri)` | Get all triples for a subject |
| `for chunk in chunks` | `graph_iter(g, type)` | Iterate over classes/properties |
| `"\n".join(parts)` | `graph_serialize(g, format)` | Convert to readable format |

#### Graph Size and Statistics

```python
#| export
def graph_size(graph: Graph) -> dict:
    """Get size statistics for a graph - the graph equivalent of len().

    Returns counts that help the LLM understand the graph's scale
    and plan appropriate chunking strategies.
    """
    # Count triples
    n_triples = len(graph)

    # Count distinct subjects, predicates, objects
    subjects = set(graph.subjects())
    predicates = set(graph.predicates())
    objects = set(graph.objects())

    # Count by type
    classes = set(graph.subjects(RDF.type, OWL.Class))
    obj_props = set(graph.subjects(RDF.type, OWL.ObjectProperty))
    data_props = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    individuals = set(graph.subjects(RDF.type, None)) - classes - obj_props - data_props

    return {
        "triples": n_triples,
        "subjects": len(subjects),
        "predicates": len(predicates),
        "objects": len(objects),
        "classes": len(classes),
        "object_properties": len(obj_props),
        "datatype_properties": len(data_props),
        "individuals": len(individuals),
        "namespaces": len(list(graph.namespaces()))
    }

def graph_namespaces(graph: Graph) -> dict:
    """Get all namespace prefixes - essential for constructing valid SPARQL."""
    return {prefix: str(uri) for prefix, uri in graph.namespaces()}
```

#### Graph Slicing - Extract Subgraphs

```python
#| export
def graph_slice(
    graph: Graph,
    subject: str = None,      # URI pattern to match subjects
    predicate: str = None,    # URI pattern to match predicates
    object: str = None,       # URI or literal pattern to match objects
    type_uri: str = None,     # Get all instances of this type
    depth: int = 1,           # How many hops to include from matched nodes
    limit: int = 100          # Maximum triples to return
) -> Graph:
    """Extract a subgraph matching a pattern - the graph equivalent of slicing.

    Like context[start:end] but for graphs. Returns a smaller graph
    containing only relevant triples.

    Examples:
    - graph_slice(g, type_uri="http://onto.org/Protein") - all proteins
    - graph_slice(g, predicate="rdfs:label") - all labels
    - graph_slice(g, subject="http://onto.org/ACE2", depth=2) - ACE2 neighborhood
    """
    from rdflib import Graph as RDFGraph
    subgraph = RDFGraph()

    # Bind same namespaces
    for prefix, ns in graph.namespaces():
        subgraph.bind(prefix, ns)

    matched_subjects = set()

    # Match by type
    if type_uri:
        for s in graph.subjects(RDF.type, URIRef(type_uri)):
            matched_subjects.add(s)

    # Match by pattern
    s_pattern = URIRef(subject) if subject else None
    p_pattern = URIRef(predicate) if predicate else None
    o_pattern = URIRef(object) if object and object.startswith('http') else (
        Literal(object) if object else None
    )

    if s_pattern or p_pattern or o_pattern:
        for s, p, o in graph.triples((s_pattern, p_pattern, o_pattern)):
            matched_subjects.add(s)

    # If no patterns specified, can't slice
    if not matched_subjects:
        return subgraph

    # Collect triples for matched subjects (and neighbors up to depth)
    def collect(subjects, current_depth):
        if current_depth > depth or len(subgraph) >= limit:
            return
        next_subjects = set()
        for subj in subjects:
            for s, p, o in graph.triples((subj, None, None)):
                if len(subgraph) >= limit:
                    break
                subgraph.add((s, p, o))
                if isinstance(o, URIRef):
                    next_subjects.add(o)
        if next_subjects and current_depth < depth:
            collect(next_subjects, current_depth + 1)

    collect(matched_subjects, 0)
    return subgraph

def graph_slice_sparql(graph: Graph, construct_query: str) -> Graph:
    """Extract subgraph using a SPARQL CONSTRUCT query - flexible slicing.

    For complex slicing patterns that can't be expressed with simple parameters.
    """
    return graph.query(construct_query).graph
```

#### Graph Search - Find Nodes

```python
#| export
def graph_search(
    graph: Graph,
    term: str,                    # Search term
    search_in: str = "labels",    # "labels", "uris", "comments", "all"
    case_sensitive: bool = False,
    limit: int = 50
) -> list[dict]:
    """Search for nodes matching a term - the graph equivalent of regex search.

    Returns matching nodes with their types and labels.
    """
    results = []
    term_lower = term.lower() if not case_sensitive else term

    seen = set()

    for s, p, o in graph:
        if len(results) >= limit:
            break

        match_found = False
        matched_on = None

        # Search in URIs
        if search_in in ("uris", "all"):
            uri_str = str(s)
            check = uri_str if case_sensitive else uri_str.lower()
            if term_lower in check:
                match_found = True
                matched_on = "uri"

        # Search in labels
        if not match_found and search_in in ("labels", "all"):
            if p == RDFS.label:
                label = str(o)
                check = label if case_sensitive else label.lower()
                if term_lower in check:
                    match_found = True
                    matched_on = "label"

        # Search in comments
        if not match_found and search_in in ("comments", "all"):
            if p == RDFS.comment:
                comment = str(o)
                check = comment if case_sensitive else comment.lower()
                if term_lower in check:
                    match_found = True
                    matched_on = "comment"

        if match_found and s not in seen:
            seen.add(s)
            # Get additional info about the match
            labels = [str(o) for o in graph.objects(s, RDFS.label)]
            types = [str(o) for o in graph.objects(s, RDF.type)]
            results.append({
                "uri": str(s),
                "labels": labels,
                "types": types,
                "matched_on": matched_on
            })

    return results
```

#### Graph Navigation - Traverse Relationships

```python
#| export
def graph_get(
    graph: Graph,
    uri: str,
    include_incoming: bool = False
) -> dict:
    """Get all information about a specific node - the graph equivalent of indexing.

    Returns all triples where the URI is the subject (and optionally object).
    """
    node = URIRef(uri)

    # Outgoing edges (this node as subject)
    outgoing = {}
    for p, o in graph.predicate_objects(node):
        pred_str = str(p)
        if pred_str not in outgoing:
            outgoing[pred_str] = []
        outgoing[pred_str].append(str(o))

    result = {"uri": uri, "outgoing": outgoing}

    # Incoming edges (this node as object)
    if include_incoming:
        incoming = {}
        for s, p in graph.subject_predicates(node):
            pred_str = str(p)
            if pred_str not in incoming:
                incoming[pred_str] = []
            incoming[pred_str].append(str(s))
        result["incoming"] = incoming

    return result

def graph_neighbors(
    graph: Graph,
    uri: str,
    predicate: str = None,
    direction: str = "outgoing"  # "outgoing", "incoming", "both"
) -> list[str]:
    """Get neighboring nodes - for graph traversal."""
    node = URIRef(uri)
    pred = URIRef(predicate) if predicate else None
    neighbors = set()

    if direction in ("outgoing", "both"):
        for o in graph.objects(node, pred):
            if isinstance(o, URIRef):
                neighbors.add(str(o))

    if direction in ("incoming", "both"):
        for s in graph.subjects(pred, node):
            neighbors.add(str(s))

    return list(neighbors)

def graph_path(
    graph: Graph,
    start_uri: str,
    end_uri: str,
    max_depth: int = 5
) -> list[list[str]] | None:
    """Find paths between two nodes - useful for understanding relationships."""
    from collections import deque

    start = URIRef(start_uri)
    end = URIRef(end_uri)

    # BFS for shortest path
    queue = deque([(start, [start_uri])])
    visited = {start}

    while queue:
        node, path = queue.popleft()

        if len(path) > max_depth:
            continue

        for p, o in graph.predicate_objects(node):
            if isinstance(o, URIRef):
                if o == end:
                    return path + [str(p), str(o)]
                if o not in visited:
                    visited.add(o)
                    queue.append((o, path + [str(p), str(o)]))

    return None
```

#### Graph Iteration - Chunking for Sub-LLM Calls

```python
#| export
def graph_iter_by_type(
    graph: Graph,
    type_uri: str,
    chunk_size: int = 10
) -> list[Graph]:
    """Iterate over instances of a type in chunks - for parallel sub-LLM processing.

    Like chunking a list, but groups graph nodes by type.
    """
    instances = list(graph.subjects(RDF.type, URIRef(type_uri)))
    chunks = []

    for i in range(0, len(instances), chunk_size):
        chunk_instances = instances[i:i + chunk_size]
        chunk_graph = Graph()
        for prefix, ns in graph.namespaces():
            chunk_graph.bind(prefix, ns)

        for inst in chunk_instances:
            for s, p, o in graph.triples((inst, None, None)):
                chunk_graph.add((s, p, o))

        chunks.append(chunk_graph)

    return chunks

def graph_iter_by_predicate(
    graph: Graph,
    chunk_size: int = 100
) -> dict[str, Graph]:
    """Split graph by predicate - useful for analyzing different relationship types."""
    by_pred = {}

    for s, p, o in graph:
        pred_str = str(p)
        if pred_str not in by_pred:
            by_pred[pred_str] = Graph()
            for prefix, ns in graph.namespaces():
                by_pred[pred_str].bind(prefix, ns)
        by_pred[pred_str].add((s, p, o))

    return by_pred
```

#### Graph Serialization - For Sub-LLM Context

```python
#| export
def graph_serialize(
    graph: Graph,
    format: str = "turtle",     # "turtle", "n3", "nt", "json-ld", "xml"
    limit: int = None,          # Limit triples (for large graphs)
    subjects: list[str] = None  # Only serialize specific subjects
) -> str:
    """Serialize graph to string - for passing to sub-LLM.

    Turtle format is most readable for LLMs.
    """
    if subjects or limit:
        # Create filtered graph
        filtered = Graph()
        for prefix, ns in graph.namespaces():
            filtered.bind(prefix, ns)

        count = 0
        subject_set = {URIRef(s) for s in subjects} if subjects else None

        for s, p, o in graph:
            if subject_set and s not in subject_set:
                continue
            filtered.add((s, p, o))
            count += 1
            if limit and count >= limit:
                break

        return filtered.serialize(format=format)

    return graph.serialize(format=format)

def graph_describe(
    graph: Graph,
    uri: str,
    format: str = "turtle"
) -> str:
    """Get a human-readable description of a single node.

    Like getting a 'page' about one entity.
    """
    node = URIRef(uri)
    desc = Graph()
    for prefix, ns in graph.namespaces():
        desc.bind(prefix, ns)

    for s, p, o in graph.triples((node, None, None)):
        desc.add((s, p, o))

    return desc.serialize(format=format)
```

#### Solveit Integration - Graph Symbol Tools

```python
#| export
def graphlen(sym: str) -> dict:
    """Get size statistics for a graph symbol - like symlen for graphs."""
    return graph_size(resolve(sym))

def graphslice(
    sym: str,
    subject: str = None,
    predicate: str = None,
    object: str = None,
    type_uri: str = None,
    depth: int = 1,
    limit: int = 100
) -> str:
    """Slice a graph and return as Turtle - like symslice for graphs."""
    g = resolve(sym)
    subgraph = graph_slice(g, subject, predicate, object, type_uri, depth, limit)
    return graph_serialize(subgraph, "turtle")

def graphsearch(
    sym: str,
    term: str,
    search_in: str = "labels",
    limit: int = 50
) -> str:
    """Search a graph for matching nodes - like symsearch for graphs."""
    import json
    return json.dumps(graph_search(resolve(sym), term, search_in, limit=limit), indent=2)

def graphget(sym: str, uri: str, include_incoming: bool = False) -> str:
    """Get all triples for a URI - like resolve but for graph nodes."""
    import json
    return json.dumps(graph_get(resolve(sym), uri, include_incoming), indent=2)

def graphpath(sym: str, start: str, end: str, max_depth: int = 5) -> str:
    """Find path between two nodes in a graph."""
    import json
    path = graph_path(resolve(sym), start, end, max_depth)
    return json.dumps(path) if path else "No path found"

def graphdesc(sym: str, uri: str) -> str:
    """Get Turtle description of a node - like getval for graph nodes."""
    return graph_describe(resolve(sym), uri)
```

#### Example: RLM-Style Graph Exploration

```python
# 1. Check graph size to plan chunking strategy
stats = graphlen('ontology')
# {"triples": 50000, "classes": 1200, "properties": 350, ...}

# 2. Search for relevant concepts
matches = graphsearch('ontology', 'protein', search_in='labels')
# Returns list of matching URIs with labels and types

# 3. Get details about a specific class
details = graphget('ontology', 'http://onto.org/Protein', include_incoming=True)
# Shows all properties and relationships

# 4. Slice out relevant subgraph for sub-LLM
protein_subgraph = graphslice('ontology', type_uri='http://onto.org/Protein', depth=1, limit=500)
# Returns Turtle string small enough for sub-LLM context

# 5. Use sub-LLM to analyze the slice
analysis = llm_query(f"""
Analyze this ontology fragment about proteins:

{protein_subgraph}

What properties are available for querying proteins?
""")

# 6. Find relationships between concepts
path = graphpath('ontology', 'http://onto.org/Protein', 'http://onto.org/Disease')
# ["http://onto.org/Protein", "http://onto.org/associatedWith", "http://onto.org/Disease"]
```

### Advanced: Multi-Ontology Federation

For queries spanning multiple ontologies:

```python
# Load multiple ontologies
ontologies = {
    "uniprot": load_ontology("uniprot.owl"),
    "go": load_ontology("go.owl"),
    "chebi": load_ontology("chebi.owl")
}

# Use sub-LLM to determine which ontologies are relevant
relevant = llm_query(f"""
Which of these ontologies would be needed to answer: "{user_query}"?
Available: {list(ontologies.keys())}
Return as JSON list.
""")

# Search across relevant ontologies in parallel
all_searches = []
for onto_name in json.loads(relevant):
    onto = ontologies[onto_name]
    for concept in concepts:
        all_searches.append((onto_name, concept, onto_search(onto, concept, "class")))

# Construct federated query using matched terms from multiple ontologies
```

## Future Directions

1. **Automatic chunking tool**: Analyze context and suggest optimal decomposition
2. **Answer accumulator**: RLM-style `answer` variable with `ready` flag
3. **Cost aggregation**: Track total cost across all sub-LLM calls
4. **Caching**: Use claudette's prompt caching for repeated context patterns
5. **Ontology-aware query templates**: Pre-built patterns for common query types
6. **Query explanation**: Use sub-LLM to explain generated SPARQL in natural language

## References

- Zhang, A. L., Kraska, T., & Khattab, O. (2025). Recursive Language Models. arXiv:2512.24601
- Prime Intellect Blog: https://www.primeintellect.ai/blog/rlm
- Claudette Documentation: https://claudette.answer.ai
- Solveit Features: https://www.fast.ai/posts/2025-11-07-solveit-features.html
