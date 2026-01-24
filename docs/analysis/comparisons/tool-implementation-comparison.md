# Tool Implementation Comparison: Simple vs RLM

## Side-by-Side Code Comparison

### Tool 1: SPARQL Query Execution

#### Simple Approach (swtools.py - 71 lines)

```python
def sparql_query(query:str,
    endpoint:str="https://dbpedia.org/sparql",
    max_results:int=100,
    name:str='res',
    ns:dict=None):
    """Execute SPARQL query, store results in REPL, return summary

    Remember to think through the needed prefixes. For example
    Wikidata queries, include these prefixes for label service:
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    ...

    **Understanding Graph Structure:**
        - Run simple queries first to discover what properties exist
        - Properties themselves are entities with labels/descriptions
        - Use `FILTER(STRSTARTS(STR(?property), "namespace"))` to focus

    **Label Resolution:**
        - Labels may be federated (external SERVICE) or local (rdfs:label)
        - If SERVICE fails, fall back to direct label queries

    **Query Strategy:**
        - Start broad, then filter
        - Use LIMIT for exploration
        - CONSTRUCT gives more control than DESCRIBE

    **Discovering Affordances:**
        - Query an entity's properties to see what questions you can ask
        - Follow property relationships to explore the graph
        - Look for temporal properties for historical queries

    **Endpoint Differences:**
        - Test label resolution approach per endpoint
        - Check if federated queries work
        - Some endpoints pre-include labels, others require explicit queries
    """
    if ns is None: ns = globals()
    max_results = int(max_results)
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)

    query_upper = query.upper()
    if 'CONSTRUCT' in query_upper or 'DESCRIBE' in query_upper:
        sparql.setReturnFormat(XML)
        response = sparql.query()
        g = Graph()
        g.parse(data=response.response.read(), format='xml')
        triples = [(str(s), str(p), str(o)) for s,p,o in g]
        if len(triples) > max_results: triples = triples[:max_results]
        ns[name] = triples
        return f"Stored {len(triples)} triples into '{name}'"
    else:
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        bindings = results.get('results', {}).get('bindings', [])
        if len(bindings) > max_results: bindings = bindings[:max_results]
        cols = results.get('head', {}).get('vars', [])
        ns[name] = bindings
        return f"Stored {len(bindings)} results into '{name}': columns {cols}"
```

**Key design patterns:**
1. **Rich docstring guidance** - Teaches the LLM how to use SPARQL effectively
2. **Endpoint parameter** - Works with any SPARQL endpoint (UniProt, Wikidata, etc.)
3. **Namespace storage** - Results stored in dict, not returned directly
4. **Summary return** - Returns "Stored 15 results into 'res': columns ['protein', 'gene']"
5. **Handles-not-dumps** - Results referenced by handle ('res'), inspected later
6. **CONSTRUCT/SELECT support** - Different handling for graph vs table results

#### RLM Approach (rlm_runtime/tools/ontology_tools.py)

```python
def make_sparql_select_tool(meta: GraphMeta):
    """Create SPARQL SELECT tool for local graph."""

    def sparql_select(query: str, limit: int = 10) -> str:
        """Execute SPARQL SELECT query on the ontology graph.

        Args:
            query: SPARQL SELECT query string
            limit: Maximum results to return (default 10)

        Returns:
            Formatted table of results
        """
        try:
            # Add LIMIT if not present
            if 'LIMIT' not in query.upper():
                query = query.rstrip()
                if query.endswith('}'):
                    query = f"{query} LIMIT {limit}"

            results = list(meta.graph.query(query))

            if not results:
                return "No results found"

            # Format as table
            if results and isinstance(results[0], tuple):
                # Get column names from query
                cols = _extract_vars_from_select(query)

                # Build table
                rows = []
                for row in results[:limit]:
                    formatted = [str(v) for v in row]
                    rows.append(formatted)

                return _format_table(cols, rows)

            return str(results[:limit])

        except Exception as e:
            return f"Query error: {e}"

    return sparql_select
```

**Key design patterns:**
1. **Minimal docstring** - Basic usage, no SPARQL teaching
2. **Local graph only** - Queries pre-loaded rdflib Graph
3. **Direct return** - Returns formatted table as string (no handle)
4. **Auto-LIMIT** - Adds LIMIT if missing (bounded results)
5. **Error handling** - Catches exceptions, returns error message
6. **No namespace** - Results returned directly, not stored

### Tool 2: Entity Search

#### Simple Approach

**No dedicated search tool** - Agent uses `rg` to search files directly:

```python
# Example usage from notebook:
rg("-l 'AGENT_GUIDE' ./ontology/wikipathways")
# Returns: list of files containing "AGENT_GUIDE"

# Or reads files directly:
view("./ontology/uniprot/AGENT_GUIDE.md")
# Returns: full file contents
```

**Pattern:** Agent explores filesystem to discover documentation, then reads it.

#### RLM Approach

```python
def make_search_entity_tool(meta: GraphMeta):
    """Create entity search tool."""

    def search_entity(pattern: str, limit: int = 10) -> str:
        """Search for entities by label or URI pattern.

        Args:
            pattern: Text to search for in labels/URIs (case-insensitive)
            limit: Maximum results to return (default 10)

        Returns:
            Formatted list of matching entities with labels
        """
        pattern_lower = pattern.lower()
        matches = []

        # Search labels
        for s, p, o in meta.graph:
            if p in [RDFS.label, SKOS.prefLabel, DC.title, DCTERMS.title]:
                if pattern_lower in str(o).lower():
                    matches.append((s, p, o))
            # Search URIs
            elif pattern_lower in str(s).lower():
                label = _get_label(meta.graph, s)
                matches.append((s, RDFS.label, label or s))

        # Deduplicate and limit
        unique = {}
        for s, p, o in matches:
            if s not in unique:
                unique[s] = (s, p, o)

        results = list(unique.values())[:limit]
        return _format_entity_list(results)

    return search_entity
```

**Pattern:** Agent searches pre-loaded graph for entities by label/URI.

## Comparison Matrix

| Feature | Simple Approach | RLM Approach |
|---------|----------------|--------------|
| **SPARQL Target** | Remote endpoints | Local rdflib graph |
| **Result Storage** | Namespace dict (handles) | Direct string return |
| **Documentation** | Rich docstrings + AGENT_GUIDE.md | Minimal docstrings + sense card |
| **Discovery** | Filesystem tools (view/rg) | Pre-indexed search |
| **Context Size** | Tool docstrings (~800 chars) | Sense card + meta summary (~1000 chars) |
| **Flexibility** | Any endpoint | Single loaded graph |
| **Progressive Disclosure** | Via handle inspection | Via bounded results |
| **Guidance** | In tool docstrings | In separate context injection |

## Key Philosophical Differences

### Simple Approach Philosophy
```
"Give the LLM general tools and teach it how to use them via docstrings.
Let it explore the filesystem to find documentation.
Trust the LLM to read and understand rich documentation (AGENT_GUIDE.md)."
```

**Assumes:**
- LLMs can navigate filesystems effectively
- Good documentation exists or can be written
- General tools > specialized tools
- Docstrings are sufficient teaching mechanism

### RLM Approach Philosophy
```
"Pre-process ontologies into bounded affordances (sense cards).
Provide specialized tools that work on pre-loaded graphs.
Inject context in structured layers (sense + meta + memory + reasoning)."
```

**Assumes:**
- Pre-processing reduces cognitive load
- Local graphs are faster than remote endpoints
- Bounded tools prevent errors
- Layered context provides better grounding

## Convergence Points

Both approaches implement **handles-not-dumps**:

**Simple:**
```python
sparql_query(..., name='res')  # Stores in namespace
# Later: inspect 'res' variable
```

**RLM:**
```python
# Results stored in interpreter namespace implicitly
res = sparql_select("SELECT ...")
# Can inspect 'res' in subsequent code
```

## Critical Question: What's the Right Abstraction?

### Option 1: General Tools + Rich Documentation (Simple)
- **Pros:** Simpler, more flexible, works with any endpoint
- **Cons:** Requires good documentation, more filesystem access

### Option 2: Specialized Tools + Compact Affordances (RLM)
- **Pros:** Bounded, predictable, no filesystem needed
- **Cons:** More complex, less flexible, requires pre-loading

### Option 3: Hybrid
- **Best of both:**
  - Use filesystem tools when AGENT_GUIDE.md exists
  - Generate AGENT_GUIDE.md from GraphMeta when it doesn't
  - Keep procedural memory from RLM approach
  - Keep Think-Act-Verify-Reflect reasoning structure
  - Drop sense cards (replaced by AGENT_GUIDE.md)
  - Drop specialized tools (replaced by general sparql_query)

## Example Session Comparison

### Simple Approach Session
```
[Agent reads context with tool docstrings]

1. view("./ontology") → sees uniprot/ directory
2. view("./ontology/uniprot/AGENT_GUIDE.md") → reads full 387-line guide
3. sparql_query("SELECT ?p WHERE { ?p a up:Protein } LIMIT 5",
                endpoint="https://sparql.uniprot.org/sparql",
                name="proteins")
   → "Stored 5 results into 'proteins': columns ['p']"
4. [Inspect proteins] → sees URIs
5. sparql_query("SELECT ?p ?label WHERE { ?p a up:Protein ; rdfs:label ?label } LIMIT 5",
                name="proteins_labeled")
   → "Stored 5 results into 'proteins_labeled': columns ['p', 'label']"
...
```

**Characteristics:**
- Explicit documentation reading step
- Direct SPARQL to remote endpoint
- Handle-based result inspection
- Full flexibility in queries

### RLM Approach Session
```
[Agent receives context: sense card + GraphMeta + reasoning guidance]

Context includes:
  Classes: up:Protein, up:Taxon (50 total)
  Properties: up:organism, up:sequence (200 total)
  Annotations: rdfs:label, rdfs:comment (RDFS vocab)

1. search_entity("protein", limit=5)
   → Returns formatted list of 5 protein classes
2. sparql_select("SELECT ?p WHERE { ?p a up:Protein } LIMIT 5")
   → Returns formatted table of results
3. sparql_select("SELECT ?p ?label WHERE { ?p a up:Protein ; rdfs:label ?label } LIMIT 5")
   → Returns formatted table
...
```

**Characteristics:**
- No documentation reading (pre-digested in sense card)
- Local graph queries (faster)
- Direct result returns (no handles)
- Bounded tools with auto-limits

## Performance Implications

### Simple Approach
- **Query latency:** Higher (remote endpoint roundtrips)
- **Initial setup:** Lower (no graph loading)
- **Memory usage:** Lower (no local graph)
- **Documentation overhead:** Higher (reads 387-line file)

### RLM Approach
- **Query latency:** Lower (local graph)
- **Initial setup:** Higher (parse + load ontology)
- **Memory usage:** Higher (full graph in memory)
- **Documentation overhead:** Lower (pre-compressed sense card)

## Recommendation

**Test hypothesis:** For well-documented ontologies, the simple approach may achieve:
- Equal or better success rates (rich documentation > compact sense card)
- Comparable iteration counts (docstring guidance compensates for latency)
- Better generalization (works with any SPARQL endpoint)

**If hypothesis holds:**
- Simplify RLM to use general tools + AGENT_GUIDE.md pattern
- Keep procedural memory (unique RLM contribution)
- Drop sense cards (replaced by dynamic docs)
- Support both local and remote modes

**If hypothesis fails:**
- Keep current RLM approach
- Document why pre-processing is necessary
- Quantify the benefit of sense cards vs full docs
