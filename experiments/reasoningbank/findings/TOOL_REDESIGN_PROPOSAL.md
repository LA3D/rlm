# SPARQL Tool Redesign Proposal

**Date**: 2026-02-04
**Based on**: Claude Code tool design patterns + S3 failure analysis (123 failures)

---

## Executive Summary

Our current SPARQL tools have **123 failures across 100 trajectories** (73% timeouts, 20% argument mismatches). By applying Claude Code's tool design principles, we can:

1. **Prevent 88% of failures** through bounded defaults and consistent APIs
2. **Improve agent discovery** through output modes and metadata
3. **Enable two-phase patterns** (search → retrieve) that prevent context bloat

---

## Core Principles from Claude Code

### 1. **Bounded by Default**
Every Claude Code tool has built-in limits:
- `Read`: `limit` parameter (lines), 2000 char line truncation
- `Grep`: `head_limit`, `output_mode` controls verbosity
- `Glob`: Returns paths, not content

**Current SPARQL Problem**: `sparql_query` has no default LIMIT → 90 timeouts

### 2. **Progressive Disclosure via Output Modes**
Grep supports:
- `files_with_matches` - Just file names (fast)
- `count` - Just counts (summary)
- `content` - Full matches with context (detailed)

**Current SPARQL Problem**: Tools only have one mode - dump everything

### 3. **Metadata-Rich Returns**
Claude Code tools return:
- `truncated: bool` - Was output cut?
- `total_count: int` - How many total?
- Context about what was returned

**Current SPARQL Problem**: Agents don't know if results are complete

### 4. **Two-Phase Discovery**
```
Phase 1: Glob "*.py" → file paths (cheap)
Phase 2: Read file.py limit=50 → first 50 lines (targeted)
Phase 3: Read file.py offset=50 limit=50 → next 50 lines (pagination)
```

**Current SPARQL Problem**: Agents go directly to unbounded queries

### 5. **Handles, Not Payloads**
- Glob returns paths (handles), not file contents
- Agent chooses which to Read

**Current SPARQL Tools**: Already use handles (`results_0`), but API is confusing

---

## Proposed Tool Redesign

### Tool 1: `sparql_query` (CRITICAL - 90 failures)

**Current Signature**:
```python
def sparql_query(query: str) -> Dict
```

**Problems**:
- No default LIMIT → timeouts
- No validation → expensive queries execute
- No metadata → agent doesn't know result size

**Proposed Signature**:
```python
def sparql_query(
    query: str,
    limit: int = 100,           # Auto-add LIMIT if missing
    timeout: int = 30,          # Timeout in seconds
    validate: bool = True,      # Check for expensive patterns
    explain: bool = False       # Return query plan, not results
) -> Dict[str, Any]:
    """Execute SPARQL query against endpoint.

    IMPORTANT: Queries without LIMIT will have LIMIT auto-added.
    Use explain=True to check query plan before executing.

    Args:
        query: SPARQL query string
        limit: If query lacks LIMIT, add this (default: 100)
        timeout: Max execution time in seconds
        validate: Warn about expensive patterns before execution
        explain: Return query plan instead of results

    Returns:
        {
            'key': 'results_0',           # Handle for sparql_slice
            'rows': 100,                  # Rows returned
            'total_available': 3116860,   # Total matching (if known)
            'truncated': True,            # Was LIMIT applied?
            'limit_applied': 100,         # What LIMIT was used
            'execution_time_ms': 145,
            'preview': 'taxon=http://...',
            'usage': 'Call sparql_slice(key) to get rows'
        }

    Example:
        # Good: Explicit LIMIT
        result = sparql_query('''
            SELECT ?protein WHERE { ?protein a up:Protein }
            LIMIT 50
        ''')

        # Also Good: Auto-limit
        result = sparql_query('''
            SELECT ?protein WHERE { ?protein a up:Protein }
        ''', limit=50)

        # Check before execute
        plan = sparql_query(expensive_query, explain=True)
        print(plan['estimated_rows'])  # See if it's too big

    Warnings:
        - Queries matching >100k rows will show warning
        - Patterns like '?s ?p ?o' trigger validation warning
        - FILTER after broad patterns is flagged as expensive
    """
```

**Key Changes**:
1. **Auto-LIMIT**: Prevents 90 timeout failures
2. **`explain` mode**: Check before execute (like EXPLAIN in SQL)
3. **`validate`**: Warn about expensive patterns
4. **Rich metadata**: `total_available`, `truncated`, `execution_time_ms`

---

### Tool 2: `sparql_slice` (17 failures)

**Current Signature**:
```python
def sparql_slice(key: str) -> List[Dict]  # But agents pass dict!
```

**Problems**:
- Agents pass `result` dict instead of `result['key']`
- No limit parameter (agents expect it)
- No pagination support

**Proposed Signature**:
```python
def sparql_slice(
    result: Union[str, Dict],   # Accept BOTH key string OR result dict
    offset: int = 0,
    limit: int = None           # None = all (but bounded by query LIMIT)
) -> Dict[str, Any]:
    """Get rows from a query result.

    Args:
        result: Either the result dict from sparql_query(), OR just the key string
                Both work: sparql_slice(result) and sparql_slice(result['key'])
        offset: Skip this many rows (for pagination)
        limit: Max rows to return (default: all available)

    Returns:
        {
            'rows': [...],              # List of result dicts
            'returned': 50,             # How many returned
            'total_available': 100,     # Total in result set
            'offset': 0,                # Current offset
            'has_more': True,           # More rows available?
            'next_offset': 50           # Use this for next page
        }

    Example:
        result = sparql_query("SELECT ...")

        # Both work now:
        rows = sparql_slice(result)           # Pass full dict
        rows = sparql_slice(result['key'])    # Pass just key

        # Pagination:
        page1 = sparql_slice(result, offset=0, limit=50)
        page2 = sparql_slice(result, offset=50, limit=50)

        # Check if more:
        if page1['has_more']:
            page2 = sparql_slice(result, offset=page1['next_offset'], limit=50)
    """
    # Implementation: accept both dict and string
    if isinstance(result, dict):
        key = result.get('key', result)
    else:
        key = result
    # ... rest of implementation
```

**Key Changes**:
1. **Accept both dict and string**: Prevents 4 type errors
2. **Add `limit` parameter**: Prevents 8 arg mismatch errors
3. **Pagination support**: `offset`, `has_more`, `next_offset`
4. **Rich metadata**: Agents know result size and position

---

### Tool 3: `sparql_peek` (9 failures)

**Current Signature**:
```python
def sparql_peek() -> List  # No parameters!
```

**Problems**:
- Agents expect `limit` parameter (8 failures)
- Agents expect `resource` parameter (1 failure)
- Returns raw list without metadata

**Proposed Signature**:
```python
def sparql_peek(
    resource: str = None,       # Class or resource to peek at
    limit: int = 5,             # How many instances
    properties: bool = True,    # Include property values?
    output_mode: str = 'sample' # 'sample', 'schema', 'count'
) -> Dict[str, Any]:
    """Peek at instances of a class or properties of a resource.

    Output Modes:
        'sample': Return sample instances with their properties (default)
        'schema': Return class structure (properties, types, no instances)
        'count': Return just the count of instances

    Args:
        resource: Class URI/prefix (e.g., 'up:Protein') or instance URI
        limit: Max instances to return (default: 5)
        properties: Include property values in sample mode
        output_mode: Controls verbosity of response

    Returns (sample mode):
        {
            'resource': 'up:Protein',
            'type': 'class',
            'instance_count': 3116860,
            'sample_instances': [
                {'uri': 'http://...', 'properties': {...}},
                ...
            ],
            'common_properties': ['up:mnemonic', 'up:organism', ...],
            'truncated': True
        }

    Returns (schema mode):
        {
            'resource': 'up:Protein',
            'type': 'class',
            'properties': [
                {'name': 'up:mnemonic', 'type': 'xsd:string', 'required': True},
                {'name': 'up:organism', 'type': 'up:Taxon', 'required': True},
                ...
            ],
            'superclasses': ['rdfs:Resource'],
            'related_classes': ['up:Taxon', 'up:Annotation']
        }

    Returns (count mode):
        {
            'resource': 'up:Protein',
            'count': 3116860
        }

    Example:
        # Sample instances
        proteins = sparql_peek('up:Protein', limit=10)

        # Just the schema
        schema = sparql_peek('up:Protein', output_mode='schema')

        # Just the count
        count = sparql_peek('up:Protein', output_mode='count')
    """
```

**Key Changes**:
1. **Add `limit` parameter**: Prevents 8 failures
2. **Add `output_mode`**: Progressive disclosure (count → schema → sample)
3. **Rich metadata**: `instance_count`, `common_properties`, `truncated`
4. **Schema mode**: Helps agents understand structure without instances

---

### Tool 4: `sparql_describe` (2 failures)

**Proposed Signature**:
```python
def sparql_describe(
    resource: str,
    limit: int = 20,            # Max triples to return
    direction: str = 'both',    # 'outgoing', 'incoming', 'both'
    output_mode: str = 'triples'  # 'triples', 'summary', 'grouped'
) -> Dict[str, Any]:
    """Describe a specific resource's properties and relationships.

    Output Modes:
        'triples': Raw subject-predicate-object triples
        'summary': Grouped by predicate with counts
        'grouped': Properties grouped by type (data vs object properties)

    Args:
        resource: URI or prefixed name to describe
        limit: Max triples to return
        direction: 'outgoing' (resource as subject), 'incoming' (resource as object), 'both'
        output_mode: Controls response format

    Returns (summary mode):
        {
            'resource': 'http://purl.uniprot.org/uniprot/P05067',
            'label': 'A4_HUMAN',
            'types': ['up:Protein', 'up:Reviewed_Protein'],
            'property_summary': {
                'up:mnemonic': {'count': 1, 'sample': 'A4_HUMAN'},
                'up:organism': {'count': 1, 'sample': 'Homo sapiens'},
                'up:annotation': {'count': 47, 'types': ['Disease', 'Function', ...]},
            },
            'incoming_links': 12,
            'total_triples': 156,
            'truncated': True
        }

    Example:
        # Quick summary of a protein
        desc = sparql_describe('uniprot:P05067', output_mode='summary')
        print(desc['property_summary'])

        # Full outgoing triples
        triples = sparql_describe('uniprot:P05067', direction='outgoing', limit=50)
    """
```

**Key Changes**:
1. **Add `limit` parameter**: Bounded by default
2. **Add `output_mode`**: Progressive disclosure
3. **Add `direction`**: Control scope (incoming vs outgoing)
4. **Rich metadata**: Counts, types, samples

---

### NEW Tool 5: `sparql_schema` (Discovery)

**Purpose**: Help agents understand ontology structure before querying

```python
def sparql_schema(
    output_mode: str = 'overview',  # 'overview', 'classes', 'properties', 'patterns'
    filter_prefix: str = None,      # e.g., 'up:' for UniProt only
    limit: int = 50
) -> Dict[str, Any]:
    """Get schema information about the endpoint.

    Output Modes:
        'overview': High-level summary (class count, property count, namespaces)
        'classes': List of classes with instance counts
        'properties': List of properties with domain/range
        'patterns': Common query patterns and templates

    Returns (overview mode):
        {
            'endpoint': 'https://sparql.uniprot.org/sparql',
            'name': 'UniProt',
            'class_count': 47,
            'property_count': 234,
            'namespaces': {
                'up': 'http://purl.uniprot.org/core/',
                'taxon': 'http://purl.uniprot.org/taxonomy/',
                ...
            },
            'top_classes': [
                {'name': 'up:Protein', 'count': 3116860},
                {'name': 'up:Taxon', 'count': 2847623},
                ...
            ]
        }

    Returns (patterns mode):
        {
            'common_patterns': [
                {
                    'name': 'Protein by mnemonic',
                    'description': 'Find protein by its mnemonic ID',
                    'template': 'SELECT ?protein WHERE { ?protein up:mnemonic "{{mnemonic}}" }',
                    'example': 'SELECT ?protein WHERE { ?protein up:mnemonic "A4_HUMAN" }'
                },
                ...
            ]
        }

    Example:
        # Start with overview
        overview = sparql_schema('overview')

        # Then explore classes
        classes = sparql_schema('classes', filter_prefix='up:', limit=20)

        # Get query templates
        patterns = sparql_schema('patterns')
    """
```

**Purpose**: Enables two-phase discovery without trial-and-error queries.

---

### NEW Tool 6: `list_tools` (Discovery)

**Purpose**: Help agents understand available tools

```python
def list_tools(
    category: str = None,  # 'query', 'explore', 'analyze', or None for all
    verbose: bool = False  # Include examples?
) -> str:
    """List available SPARQL tools with their signatures.

    Returns formatted string showing:
    - Tool names and purposes
    - Parameters with types and defaults
    - Brief examples (if verbose=True)

    Example:
        # Quick list
        print(list_tools())

        # Detailed with examples
        print(list_tools(verbose=True))

        # Just query tools
        print(list_tools(category='query'))
    """
```

---

## Two-Phase Discovery Pattern

Document this pattern for agents:

```markdown
## SPARQL Discovery Pattern

### Phase 1: Schema Discovery (cheap, bounded)
```python
# Get endpoint overview
overview = sparql_schema('overview')
print(f"Found {overview['class_count']} classes")

# Find relevant classes
classes = sparql_schema('classes', filter_prefix='up:', limit=10)
```

### Phase 2: Instance Exploration (targeted)
```python
# Peek at sample instances
proteins = sparql_peek('up:Protein', limit=5, output_mode='sample')

# Describe a specific instance
desc = sparql_describe('uniprot:P05067', output_mode='summary')
```

### Phase 3: Query Execution (bounded)
```python
# Check query plan first
plan = sparql_query(my_query, explain=True)
print(f"Estimated rows: {plan['estimated_rows']}")

# Execute with explicit limit
result = sparql_query(my_query, limit=100)
print(f"Got {result['rows']}/{result['total_available']} rows")

# Paginate if needed
if result['truncated']:
    rows = sparql_slice(result, offset=0, limit=50)
    while rows['has_more']:
        rows = sparql_slice(result, offset=rows['next_offset'], limit=50)
```
```

---

## Error Message Improvements

**Current**:
```
TypeError: unhashable type: 'dict'
```

**Proposed**:
```
SPARQLSliceError: Expected result key or result dict, got unhashable dict.

Did you mean to pass the result directly?
  rows = sparql_slice(result)        # Now works!
  rows = sparql_slice(result['key']) # Also works

The result dict contains: {'key': 'results_0', 'rows': 100, ...}
```

**Current**:
```
TimeoutError: The read operation timed out
```

**Proposed**:
```
SPARQLTimeoutError: Query exceeded 30 second timeout.

Your query may be too broad. Common causes:
1. Missing LIMIT clause (auto-added LIMIT 100 wasn't enough)
2. Expensive pattern: '?s ?p ?o' matches all triples
3. FILTER applied after broad match

Suggestions:
- Add a more specific type constraint: ?s a up:Protein
- Move FILTER conditions into WHERE patterns
- Use sparql_query(query, explain=True) to check query plan

Query that timed out:
  SELECT ?s ?p ?o WHERE { ?s ?p ?o . FILTER(...) } LIMIT 100
                         ^^^^^^^^^ matches millions of triples!
```

---

## Implementation Priority

### Phase 1: Critical Fixes (prevents 88% of failures)

1. **`sparql_query`**: Add auto-LIMIT, `limit` parameter
   - Impact: Prevents 90 timeout failures
   - Effort: 2 hours

2. **`sparql_slice`**: Accept both dict and string, add `limit`
   - Impact: Prevents 17 failures (type + arg mismatch)
   - Effort: 1 hour

3. **`sparql_peek`**: Add `limit` parameter
   - Impact: Prevents 9 failures
   - Effort: 30 minutes

### Phase 2: Enhanced Usability

4. **Output modes**: Add to all tools
   - Impact: Enables progressive disclosure
   - Effort: 4 hours

5. **Rich metadata**: Add `truncated`, `total_available`, `has_more`
   - Impact: Agents understand result scope
   - Effort: 2 hours

6. **Better error messages**: Actionable guidance
   - Impact: Faster agent recovery
   - Effort: 2 hours

### Phase 3: Discovery Tools

7. **`sparql_schema`**: New tool for ontology exploration
   - Impact: Enables two-phase discovery
   - Effort: 4 hours

8. **`list_tools`**: Self-documentation
   - Impact: Reduces trial-and-error
   - Effort: 1 hour

---

## Expected Impact

| Metric | Before | After (Phase 1) | After (All) |
|--------|--------|-----------------|-------------|
| Timeout failures | 90 | ~5 | ~0 |
| Arg mismatch | 24 | ~2 | ~0 |
| Type errors | 4 | 0 | 0 |
| Total failures | 123 | ~10 | ~5 |
| Success rate | 60-70% | 85-90% | 95%+ |
| Avg iterations | 6.7 | 5.0 | 4.0 |

---

## Summary

By applying Claude Code's tool design principles:

1. **Bounded by default** → Auto-LIMIT prevents timeouts
2. **Output modes** → Progressive disclosure (count → schema → sample → full)
3. **Consistent parameters** → `limit`, `offset` everywhere
4. **Rich metadata** → `truncated`, `total_available`, `has_more`
5. **Accept flexible inputs** → Dict or string both work
6. **Helpful errors** → Actionable guidance, not stack traces
7. **Two-phase discovery** → Schema → Peek → Query
8. **Self-documenting** → `list_tools()` for discoverability

These changes transform tools from "execute and hope" to **agent-friendly progressive exploration**.
