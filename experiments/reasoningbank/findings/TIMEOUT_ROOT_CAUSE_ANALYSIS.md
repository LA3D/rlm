# SPARQL Timeout Root Cause Analysis

**Date**: 2026-02-06
**Context**: S3 experiment (100 trajectories) produced 90 timeout failures (73% of all 123 failures). V2 tool redesign did not reduce timeouts. This document investigates why.

---

## Executive Summary

The timeouts are **not a tool design problem**. They are caused by agents using **data-scan query patterns** on a 232-billion-triple dataset where only **ontology-level schema queries** are fast. UniProt runs QLever with only PSO and POS index permutations, meaning any query with an unbound predicate (`?s ?p ?o`) requires a full scan. The fix is not better tools — it is better query strategy guidance.

---

## Environment

### UniProt SPARQL Endpoint

- **Engine**: QLever (C++ SPARQL engine, University of Freiburg)
- **URL**: `https://sparql.uniprot.org/sparql`
- **Dataset size**: **232,229,579,911 triples** across 21 named graphs
- **Index**: PSO and POS permutations only (no SPO, SOP, OPS, OSP)
- **Server timeout**: 45 minutes (2700s)
- **Infrastructure**: Swiss Institute of Bioinformatics, fronted by Apache
- **Release**: 2026_01

### Client

- **Library**: `sparqlx` 0.7.0 (httpx-based, SPARQL 1.2 protocol) — installed in project
- **Experiment tools**: `prototype/tools/sparql.py` and `sparql_v2.py` use `urllib` directly
- **Client timeout**: 30 seconds (configured in `EndpointConfig`)

### QLever Index Permutations

QLever can build up to six permutations of (S, P, O). UniProt builds only two:

| Permutation | Built? | Fast when... |
|---|---|---|
| **PSO** | Yes | Predicate bound, then Subject → Objects |
| **POS** | Yes | Predicate bound, then Object → Subjects |
| SPO | No | Subject bound → arbitrary predicates |
| SOP | No | — |
| OPS | No | — |
| OSP | No | — |

**Consequence**: Queries where the predicate is **bound** (`?s up:disease ?o`) use the PSO/POS index and are fast. Queries where the predicate is a **variable** (`?s ?p ?o`) cannot use the index efficiently and require scanning.

---

## Empirical Query Timing Results

All queries run against `https://sparql.uniprot.org/sparql` on 2026-02-06 with 30-45s client timeout.

### Fast Patterns (< 1 second)

| Query Pattern | Time | Results | Why Fast |
|---|---|---|---|
| Official bacteria taxa example: `?taxon rdfs:subClassOf taxon:2 ; up:scientificName ?name` | **0.48s** | 20 | Predicate bound, known subject hierarchy |
| Official disease example: `?annotation a up:Disease_Annotation ; rdfs:comment ?text` | **0.64s** | 20 | Type + predicate both bound |
| Properties of one instance: `<P05067> ?p ?o` | **0.36s** | 30 | Subject fully bound → POS lookup |
| Annotation types via ontology: `?annType rdfs:subClassOf up:Annotation` | **0.36s** | 26 | Ontology schema, tiny result set |
| Disease predicate via ontology: `?prop a owl:ObjectProperty; FILTER(CONTAINS(..., "disease"))` | **0.37s** | 1 | Small ontology class, not data scan |
| Class enumeration: `?s a ?class GROUP BY ?class` | **0.59s** | 50 | QLever optimizes `rdf:type` grouping |

### Slow Patterns (> 10 seconds)

| Query Pattern | Time | Why Slow |
|---|---|---|
| Properties of `up:Taxon` (3M instances): `?s a up:Taxon . ?s ?p ?o` DISTINCT `?p` | **10.2s** | 3M subjects × all predicates, unbound ?p |
| Classes in taxonomy graph: `FROM <taxonomy> { ?s a ?class } GROUP BY` | **37.9s** | Named graph `FROM` clause adds overhead |

### Timeout Patterns (> 30 seconds)

| Query Pattern | Agent Intent | Why Timeout |
|---|---|---|
| `?s a up:Protein . ?s ?p ?o` GROUP BY `?p` | Discover protein properties | ~250B triples to scan (Protein is largest class) |
| `FILTER(CONTAINS(STR(?predicate), "disease"))` on `?protein ?predicate ?obj` | Find disease-related predicates | Full scan + string comparison on every triple |
| `?s ?p ?o GROUP BY ?p` (all properties) | Enumerate all predicates | 232B triples, unbound ?p |
| `GRAPH ?g { ?s ?p ?o }` (named graph listing) | Discover named graphs | Full scan across all graphs |
| V2 `sparql_schema('properties')`: `?s ?p ?o GROUP BY ?p ORDER BY DESC(?usage)` | Schema discovery tool | Same as above — guaranteed timeout |

---

## Why V2 Tools Did Not Help

### V2 Validation Results (8 trajectories, Feb 6)

| Task | V1 Failures | V2 Failures | V1 Iters | V2 Iters |
|---|---|---|---|---|
| bacteria_taxa rollout 1 | 2 | 1 | 7 | 6 |
| bacteria_taxa rollout 2 | 1 | 2 | 8 | 7 |
| proteins_diseases rollout 1 | 3 | **4** | 8 | **10** |
| proteins_diseases rollout 2 | 3 | 2 | 8 | **10** |

V2 fixed argument mismatch errors (24 of 123 in S3) but **introduced new timeouts** through its own `sparql_schema('properties')` tool. The dominant failure mode — agents constructing broad exploratory queries — is unchanged.

### V2's Own Timeout-Prone Queries

`sparql_schema('properties')` executes:

```sparql
SELECT ?p (COUNT(*) AS ?usage)
WHERE { ?s ?p ?o }
GROUP BY ?p
ORDER BY DESC(?usage)
LIMIT 50
```

This scans 232B triples. It **will always timeout** on UniProt.

`sparql_schema('overview')` calls `sparql_count("SELECT DISTINCT ?p WHERE { ?s ?p ?o }")` which has the same problem.

`sparql_schema('classes')` works (0.59s) because QLever has a special optimization for `?s a ?class GROUP BY ?class`.

---

## Timeout Pattern Taxonomy

From analysis of 17 timeout events across 8 validation trajectories:

### Pattern 1: FILTER CONTAINS on predicates (47% of timeouts)

```sparql
-- Agent wants to find disease-related predicates
SELECT DISTINCT ?predicate WHERE {
    ?protein a up:Protein .
    ?protein ?predicate ?obj .
    FILTER(CONTAINS(STR(?predicate), "disease"))
}
LIMIT 20
```

**Why it fails**: Even with `LIMIT 20`, QLever must scan all Protein triples (billions) testing each predicate string. The FILTER runs after pattern matching.

**Fast alternative** (0.37s):

```sparql
-- Query the ontology schema instead
SELECT ?prop ?domain ?range WHERE {
    ?prop a owl:ObjectProperty .
    OPTIONAL { ?prop rdfs:domain ?domain }
    OPTIONAL { ?prop rdfs:range ?range }
    FILTER(CONTAINS(LCASE(STR(?prop)), "disease"))
}
```

### Pattern 2: Schema tool enumeration (24% of timeouts)

```sparql
-- V2 sparql_schema('properties')
SELECT ?p (COUNT(*) AS ?usage)
WHERE { ?s ?p ?o }
GROUP BY ?p
```

**Why it fails**: Unbound `?p` with no PSO/POS optimization path. Full 232B triple scan.

**Fast alternative** (0.36s):

```sparql
-- Describe a single representative instance
SELECT DISTINCT ?p ?o WHERE {
    <http://purl.uniprot.org/uniprot/P05067> ?p ?o
}
LIMIT 30
```

### Pattern 3: Broad string matching (18% of timeouts)

```sparql
-- Agent searching for any triple mentioning "disease"
SELECT DISTINCT ?predicate WHERE {
    ?s ?predicate ?disease .
    FILTER(CONTAINS(LCASE(STR(?disease)), "disease"))
}
```

**Why it fails**: No type constraints on `?s`. Scans entire dataset.

**Fast alternative** (0.36s):

```sparql
-- Use the ontology to find annotation types
SELECT ?annType WHERE {
    ?annType rdfs:subClassOf up:Annotation
}
```

### Pattern 4: Property discovery on large classes (12% of timeouts)

```sparql
-- Agent wants to know what predicates Protein has
SELECT DISTINCT ?p (COUNT(?o) AS ?usage) WHERE {
    ?s a up:Protein .
    ?s ?p ?o .
}
GROUP BY ?p
```

**Why it fails**: Protein has ~250B associated triples. Scanning all of them to find distinct predicates is impossibly expensive.

**Fast alternative** (0.36s):

```sparql
-- Pick a sample instance and describe it
SELECT DISTINCT ?p WHERE {
    <http://purl.uniprot.org/uniprot/P05067> ?p ?o
}
LIMIT 30
```

---

## The Discovery Strategy Problem

The fundamental issue is that agents default to a **data-scan discovery strategy**:

```
1. "What predicates exist?" → SELECT ?p WHERE { ?s ?p ?o } → TIMEOUT
2. "Which ones mention disease?" → FILTER(CONTAINS(...)) → TIMEOUT
3. "What properties does Protein have?" → ?s a up:Protein . ?s ?p ?o → TIMEOUT
```

The correct strategy for a 232B-triple endpoint is **ontology-first discovery**:

```
1. "What annotation types exist?" → ?t rdfs:subClassOf up:Annotation → 0.36s (26 types)
2. "What is the disease predicate?" → ?p a owl:ObjectProperty; domain/range → 0.37s (1 result)
3. "What does a protein look like?" → <P05067> ?p ?o → 0.36s (30 properties)
4. Construct query using known predicates → official example patterns → 0.5-0.7s
```

### Why Agents Use the Wrong Strategy

1. **No guidance in context**: The L0 sense card and L1 schema constraints describe the ontology but don't warn about query patterns that timeout.
2. **FILTER CONTAINS is natural language**: Agents default to string search because it maps directly from the question ("find disease-related...").
3. **Works on small datasets**: The data-scan approach works fine on local ontology files (thousands of triples). Agents don't know they're hitting 232B triples.
4. **Tool API encourages it**: `sparql_schema('properties')` and `sparql_peek` suggest that broad exploration is safe.

---

## QLever-Specific Considerations

### Features Available

- **Full SPARQL 1.1 compliance** (verified June 2025)
- **`rdf:type` GROUP BY optimization**: `?s a ?class GROUP BY ?class` is handled efficiently
- **Cost-based query optimizer**: Dynamic programming planner with cardinality estimation
- **LRU result cache**: Repeated identical queries served from cache

### Features NOT Available on UniProt's Instance

- **`application/qlever-results+json`**: Returns HTTP 400. UniProt's Apache frontend does not pass through QLever's custom format, so we cannot access `resultsize` or `runtimeInformation`.
- **`ql:has-predicate`**: QLever extension for efficient predicate listing — not confirmed available (endpoint returns non-JSON for this query).
- **`ql:contains-word` / `ql:contains-entity`**: Require a text index built at index time. Not confirmed on UniProt.
- **Per-query timeout parameter**: QLever does not expose this in its HTTP API. The 45-minute timeout is server-side only.
- **`X-Total-Results` header**: Not returned by UniProt's endpoint.

### What This Means for Tool Design

1. We cannot get result size estimates before execution
2. We cannot get query execution plans
3. We cannot use QLever text search extensions (unconfirmed)
4. The only timeout knob is the client-side `httpx`/`urllib` timeout
5. String filtering (`FILTER CONTAINS`) will always be slow — no index support

---

## The `sparqlx` Gap

The project has two SPARQL execution paths:

### 1. `rlm/sparql_handles.py` (nbdev-generated, uses `sparqlx`)

- Uses `sparqlx.SPARQLWrapper` (httpx-based, SPARQL 1.2 protocol)
- Proper `SPARQLResultHandle` with handle semantics
- LIMIT injection via `_inject_limit()`
- Configurable timeout via `client_config=dict(timeout=...)`
- `convert=True` returns typed results (list[dict], rdflib.Graph, bool)
- Integrated with dataset memory (`DatasetMeta`, prov logging)

### 2. `experiments/reasoningbank/prototype/tools/sparql.py` and `sparql_v2.py` (uses `urllib`)

- Raw `urllib.request.urlopen` with manual JSON parsing
- Re-implements handle pattern (`Ref`, `ResultStore`)
- Manual LIMIT injection
- No streaming, no async
- DSPy tool wrapper complexity (dual calling convention)

These two paths implement the same concepts independently. The experiment prototype does not use `sparqlx` at all.

---

## Recommendations

### Immediate: Fix V2 Schema Discovery

Remove or guard queries that are guaranteed to timeout:

| V2 Method | Current Query | Fix |
|---|---|---|
| `sparql_schema('properties')` | `?s ?p ?o GROUP BY ?p` | **Remove** or replace with single-instance describe |
| `sparql_schema('overview')` property count | `SELECT DISTINCT ?p WHERE { ?s ?p ?o }` | **Remove** or use VoID metadata |
| `sparql_peek(resource, output_mode='schema')` | `?s a {resource} . ?s ?p ?o GROUP BY ?p` | Only safe for classes < 100K instances |

### Immediate: Add Query Pattern Guidance to Context

Inject into the agent's context (L0 or L1 layer):

```
## Query Safety Rules for UniProt (232B triples)

NEVER use these patterns — they will timeout:
- `?s ?p ?o` with unbound predicate (scans 232B triples)
- `FILTER(CONTAINS(STR(?x), "..."))` on data (no text index)
- `SELECT DISTINCT ?p WHERE { ?s a <LargeClass> . ?s ?p ?o }` (scans all instances)

INSTEAD use:
- Ontology queries: `?type rdfs:subClassOf up:Annotation` (26 types, 0.3s)
- Instance describe: `<specific_URI> ?p ?o LIMIT 30` (0.3s)
- Known predicates from context (up:disease, up:organism, up:annotation, etc.)
- Official UniProt example patterns with bound predicates
```

### Medium-term: Align on `sparqlx`

Converge the experiment tools onto `sparqlx.SPARQLWrapper` instead of raw `urllib`. This gives:

- httpx with proper timeout handling
- Async support for parallel queries
- Streaming for large results
- SPARQL 1.2 protocol compliance
- Reuse of `SPARQLResultHandle` from `rlm/sparql_handles.py`

### Medium-term: Pre-compute Schema Metadata

Since schema discovery queries are expensive, pre-compute and cache:

- Class list with counts (from the fast `?s a ?class GROUP BY` query)
- Property lists per class (by describing representative instances)
- Named graph inventory (from VoID description)
- Annotation type hierarchy (from `rdfs:subClassOf`)

Store this as a static artifact (JSON/TTL) shipped with the ontology context, not queried at runtime.

### Long-term: UniProt Example Query Integration

UniProt publishes 25 official example queries at `https://sparql.uniprot.org/.well-known/sparql-examples/`. These are curated, fast, and correct. They should be:

1. Parsed and stored as procedural memory seeds
2. Used as templates in the L1/L2 context
3. Referenced in query safety guidance

---

## Appendix: UniProt Named Graphs

From VoID description (`https://sparql.uniprot.org/.well-known/void`):

| Graph | Approx Triples | Content |
|---|---|---|
| `uniparc` | 170.4B | Protein archive |
| `uniprot` | 48.5B | Core protein data |
| `uniref` | 10.5B | Reference clusters |
| `obsolete` | 2.1B | Obsolete entries |
| `citationmapping` | 625.5M | Citation mappings |
| `taxonomy` | 60.5M | Taxonomic data |
| `proteomes` | 34.9M | Proteome data |
| `citations` | 31.3M | Citation records |
| `diseases` | ~1M | Disease records |
| `keywords` | ~1M | Keyword hierarchy |
| `enzymes`, `go`, `chebi`, `rhea`, etc. | various | Cross-references |

**All graphs are also in the default graph** (232B total). Queries without `FROM` or `GRAPH` search everything.

## Appendix: UniProt Official Example Queries (Selected)

These patterns are fast and safe:

**Bacterial taxa** (Task 2 equivalent):
```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?taxon ?name
WHERE {
    ?taxon a up:Taxon .
    ?taxon up:scientificName ?name .
    ?taxon rdfs:subClassOf taxon:2 .
}
```

**Human proteins with disease annotations** (Task 121 equivalent):
```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?name ?text
WHERE {
    ?protein a up:Protein .
    ?protein up:organism taxon:9606 .
    ?protein up:encodedBy ?gene .
    ?gene skos:prefLabel ?name .
    ?protein up:annotation ?annotation .
    ?annotation a up:Disease_Annotation .
    ?annotation rdfs:comment ?text
}
```

**Disease-protein cellular location** (complex join, still fast):
```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?protein ?disease ?location_inside_cell ?cellcmpt
WHERE {
    ?protein up:annotation ?diseaseAnnotation , ?subcellAnnotation .
    ?diseaseAnnotation up:disease/skos:prefLabel ?disease .
    ?subcellAnnotation up:locatedIn/up:cellularComponent ?cellcmpt .
    ?cellcmpt skos:prefLabel ?location_inside_cell .
}
```

All use **bound predicates** and **type constraints**. None use `FILTER(CONTAINS(...))` for discovery.
