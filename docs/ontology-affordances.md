# Ontology Affordances for SPARQL Query Construction

> How ontology structure translates to query capabilities

## Overview

An **affordance** in the context of ontologies is a capability that the ontology's structure provides for querying and reasoning. When an LLM builds a "sense" of an ontology, it should understand not just *what* is in the ontology, but *what kinds of questions can be answered* and *how to construct queries* for them.

This document describes:
1. OWL-based affordances (class hierarchy, property characteristics)
2. SHACL-based affordances (constraints as query hints)
3. Pattern-based affordances (reification, measurement, provenance)
4. Detection strategies for sense-building

## 1. OWL-Based Affordances

### 1.1 Class Hierarchy (rdfs:subClassOf)

**Detection:** Look for `rdfs:subClassOf` triples between classes

**Affordance:** Enables hierarchical queries at any granularity level

| Question Type | SPARQL Pattern | Notes |
|---------------|----------------|-------|
| Find all X | `?x rdf:type/rdfs:subClassOf* :Class` | Transitive closure |
| Find specific subtype | `?x rdf:type :SubClass` | Direct type |
| Get type hierarchy | `?type rdfs:subClassOf* :Class` | All subtypes |
| Polymorphic query | `VALUES ?type { :Type1 :Type2 }` | Multiple types |

**Example:**
```sparql
# Find all activities (including Create, Modify, etc.)
SELECT ?activity WHERE {
  ?activity rdf:type/rdfs:subClassOf* prov:Activity .
}
```

### 1.2 Inverse Properties (owl:inverseOf)

**Detection:** Look for `owl:inverseOf` triples

**Affordance:** Enables bidirectional navigation

| Property Pair | Forward Query | Inverse Query |
|---------------|---------------|---------------|
| `generated` / `wasGeneratedBy` | "What did X generate?" | "What generated Y?" |
| `used` / `wasUsedBy` | "What did X use?" | "What used Y?" |
| `hasPart` / `partOf` | "What are X's parts?" | "What contains Y?" |

**Query Optimization:** If you have both directions, choose the one with better selectivity.

### 1.3 Transitive Properties (owl:TransitiveProperty)

**Detection:** Look for `rdf:type owl:TransitiveProperty`

**Affordance:** Enables path traversal without manual recursion

| Property | Query Pattern | Result |
|----------|---------------|--------|
| `partOf` | `?part :partOf+ ?whole` | All ancestors |
| `subClassOf` | `?sub rdfs:subClassOf* ?super` | Full hierarchy |
| `wasDerivedFrom` | `?entity prov:wasDerivedFrom+ ?source` | Full lineage |

**Important:** Use `+` for "one or more" hops, `*` for "zero or more" hops.

### 1.4 Symmetric Properties (owl:SymmetricProperty)

**Detection:** Look for `rdf:type owl:SymmetricProperty`

**Affordance:** Query either direction, same result

| Property | Implication |
|----------|-------------|
| `owl:sameAs` | `A sameAs B` ≡ `B sameAs A` |
| `skos:related` | Bidirectional relationship |

### 1.5 Functional Properties (owl:FunctionalProperty)

**Detection:** Look for `rdf:type owl:FunctionalProperty`

**Affordance:** Guaranteed single value - enables simpler queries

| Property | Implication |
|----------|-------------|
| Functional | No need for `GROUP BY` or `DISTINCT` |
| Can use in `FILTER` | Safe equality comparisons |
| Assignment | Can bind directly without aggregation |

### 1.6 Domain/Range Constraints

**Detection:** Look for `rdfs:domain` and `rdfs:range` triples

**Affordance:** Know what can connect to what

| Constraint | Query Implication |
|------------|-------------------|
| `domain(P) = C` | Only instances of C can have property P |
| `range(P) = D` | Values of P are instances of D |

**Validation:** Use domain/range to prevent constructing invalid queries.

### 1.7 Disjointness (owl:disjointWith)

**Detection:** Look for `owl:disjointWith` or `owl:AllDisjointClasses`

**Affordance:** Know what cannot overlap

| Disjointness | Implication |
|--------------|-------------|
| `Activity ⊥ Entity` | Nothing is both an Activity and Entity |
| Exclusive types | Can use for validation/debugging |

---

## 2. SHACL-Based Affordances

SHACL (Shapes Constraint Language) provides additional structural information beyond OWL that directly translates to query capabilities.

### 2.1 Cardinality Constraints

**Detection:** `sh:minCount`, `sh:maxCount` on property shapes

| Constraint | Query Affordance |
|------------|------------------|
| `sh:minCount 1` | Property is required - always present |
| `sh:maxCount 1` | Single value - no need for aggregation |
| `sh:minCount 0` | Property is optional - use `OPTIONAL` |

**Example:**
```turtle
:ProfileShape sh:property [
    sh:path dct:title ;
    sh:minCount 1 ;
    sh:maxCount 1 ;
] .
```

**Query implication:** Every Profile has exactly one title.
```sparql
SELECT ?profile ?title WHERE {
  ?profile a prof:Profile ;
           dct:title ?title .  # Guaranteed to exist, single value
}
```

### 2.2 Datatype Constraints

**Detection:** `sh:datatype` on property shapes

| Constraint | Query Affordance |
|------------|------------------|
| `sh:datatype xsd:string` | String functions available |
| `sh:datatype xsd:integer` | Numeric comparison/aggregation |
| `sh:datatype xsd:dateTime` | Temporal functions |

**Query implication:** Use appropriate SPARQL functions.
```sparql
# If sh:datatype xsd:dateTime
FILTER (?time > "2024-01-01T00:00:00"^^xsd:dateTime)
```

### 2.3 Pattern Constraints

**Detection:** `sh:pattern` (regex) on property shapes

| Constraint | Query Affordance |
|------------|------------------|
| `sh:pattern "^[a-z]+"` | Can use REGEX in FILTER |
| Known format | Parse/extract components |

**Example:**
```turtle
:ProfileShape sh:property [
    sh:path prof:hasToken ;
    sh:pattern "^[a-z0-9\\-]+/v[0-9]+\\.[0-9]+\\.[0-9]+$" ;
] .
```

**Query implication:** Token follows `name/vX.Y.Z` pattern.
```sparql
SELECT ?name ?version WHERE {
  ?profile prof:hasToken ?token .
  BIND(STRBEFORE(?token, "/v") AS ?name)
  BIND(STRAFTER(?token, "/v") AS ?version)
}
```

### 2.4 Value Constraints

**Detection:** `sh:in`, `sh:hasValue`, `sh:class`

| Constraint | Query Affordance |
|------------|------------------|
| `sh:in (A B C)` | Enumerated values - use `VALUES` |
| `sh:hasValue X` | Fixed value - can omit from query |
| `sh:class C` | Value is instance of C |

**Example:**
```sparql
# If sh:in (:Draft :Published :Archived)
VALUES ?status { :Draft :Published :Archived }
```

### 2.5 Node Kind Constraints

**Detection:** `sh:nodeKind`

| Constraint | Query Affordance |
|------------|------------------|
| `sh:IRI` | Value is a URI - can dereference |
| `sh:Literal` | Value is a literal - string functions |
| `sh:BlankNode` | Value is blank node - nested pattern |

### 2.6 Property Paths in SHACL

**Detection:** `sh:path` with complex path expressions

| Path | SPARQL Equivalent |
|------|-------------------|
| `sh:path :p` | `:p` |
| `sh:path (sh:alternativePath (:p1 :p2))` | `:p1 \| :p2` |
| `sh:path (sh:zeroOrMorePath :p)` | `:p*` |
| `sh:path (sh:oneOrMorePath :p)` | `:p+` |
| `sh:path (:p1 :p2)` | `:p1/:p2` (sequence) |
| `sh:path (sh:inversePath :p)` | `^:p` |

**Query implication:** Complex paths are pre-defined navigation patterns.

---

## 3. Pattern-Based Affordances

Beyond individual axioms, certain patterns in ontologies enable specific query capabilities.

### 3.1 Reification / Qualified Relations

**Detection:** Classes that represent relationships with additional attributes

**Pattern in PROV:**
```turtle
prov:Attribution a owl:Class .
prov:qualifiedAttribution a owl:ObjectProperty ;
    rdfs:domain prov:Entity ;
    rdfs:range prov:Attribution .
prov:agent a owl:ObjectProperty ;
    rdfs:domain prov:Attribution ;
    rdfs:range prov:Agent .
```

**Affordance:** Query relationship metadata

| Question | Simple Query | Qualified Query |
|----------|--------------|-----------------|
| "Who created X?" | `X prov:wasAttributedTo ?agent` | N/A |
| "Who created X, in what role?" | N/A | `X prov:qualifiedAttribution [ prov:agent ?agent ; prov:hadRole ?role ]` |
| "When was X attributed?" | N/A | `X prov:qualifiedAttribution [ prov:agent ?agent ; prov:atTime ?time ]` |

### 3.2 Measurement / Observation Pattern

**Detection:** SOSA/SSN or similar observation patterns

**Pattern:**
```turtle
sosa:Observation
    sosa:hasFeatureOfInterest → Feature
    sosa:observedProperty → Property
    sosa:hasResult → Result
    sosa:resultTime → Time
```

**Affordance:** Query measurements with context

```sparql
SELECT ?value ?time ?sensor WHERE {
  ?obs a sosa:Observation ;
       sosa:observedProperty :Temperature ;
       sosa:hasSimpleResult ?value ;
       sosa:resultTime ?time ;
       sosa:madeBySensor ?sensor .
}
```

### 3.3 Part-Whole Pattern

**Detection:** `hasPart` / `partOf` properties, often transitive

**Affordance:** Compositional queries

```sparql
# All components (recursive)
SELECT ?part WHERE {
  :Assembly :hasPart+ ?part .
}

# Bill of materials
SELECT ?part (COUNT(?subpart) AS ?subcount) WHERE {
  :Assembly :hasPart ?part .
  OPTIONAL { ?part :hasPart ?subpart }
} GROUP BY ?part
```

### 3.4 Provenance Pattern (PROV)

**Detection:** PROV-O classes and properties

**Affordance:** Trace lineage, attribution, delegation

| Question | Query Pattern |
|----------|---------------|
| "What is X derived from?" | `X prov:wasDerivedFrom+ ?source` |
| "Who is responsible for X?" | `X prov:wasAttributedTo ?agent` |
| "What activities produced X?" | `X prov:wasGeneratedBy ?activity` |
| "Full provenance trace" | Combine derivation + generation + attribution |

### 3.5 SKOS Concept Scheme Pattern

**Detection:** SKOS vocabulary usage

**Affordance:** Concept navigation and multi-lingual labels

```sparql
# Find concept by any label
SELECT ?concept WHERE {
  ?concept skos:prefLabel|skos:altLabel ?label .
  FILTER(CONTAINS(LCASE(?label), "search term"))
}

# Broader concepts (hierarchy)
SELECT ?broader WHERE {
  :Concept skos:broader+ ?broader .
}

# Multi-lingual
SELECT ?label WHERE {
  :Concept skos:prefLabel ?label .
  FILTER(LANG(?label) = "en")
}
```

---

## 4. Affordance Detection for Sense-Building

When building a "sense document" for an ontology, detect and report affordances in these categories:

### 4.1 Navigation Affordances

```yaml
navigation:
  hierarchical:
    subClassOf_chains: true
    max_depth: 5
    root_classes: [Entity, Activity, Agent]
  bidirectional:
    inverse_pairs:
      - [generated, wasGeneratedBy]
      - [used, wasUsedBy]
  transitive:
    properties: [wasDerivedFrom, partOf]
    enables: "path queries with + and *"
```

### 4.2 Constraint Affordances

```yaml
constraints:
  cardinality:
    required_properties: [dct:title, dct:publisher]
    single_valued: [prov:atTime, dct:identifier]
  datatypes:
    temporal: [prov:atTime, prov:startedAtTime]
    numeric: [qudt:numericValue]
    string: [rdfs:label, skos:prefLabel]
  patterns:
    version_format: "^[0-9]+\\.[0-9]+\\.[0-9]+$"
```

### 4.3 Query Pattern Affordances

```yaml
query_patterns:
  supported:
    - hierarchical: "Find all X where X is subtype of Y"
    - provenance: "Trace lineage of entity X"
    - temporal: "Filter by time range"
    - qualified: "Get relationship metadata"
  not_supported:
    - geospatial: "No spatial predicates detected"
    - measurement: "No SOSA/SSN pattern detected"
```

### 4.4 Annotation Affordances

```yaml
annotations:
  label_properties:
    - rdfs:label
    - skos:prefLabel
    - skos:altLabel
  description_properties:
    - rdfs:comment
    - skos:definition
    - dct:description
  multilingual: false  # No language tags detected
```

---

## 5. SHACL Detection Strategy

To detect SHACL affordances during sense-building:

### 5.1 Check for SHACL Presence

```sparql
ASK { ?shape a sh:NodeShape }
```

### 5.2 Extract Property Constraints

```sparql
SELECT ?class ?property ?minCount ?maxCount ?datatype ?pattern WHERE {
  ?shape a sh:NodeShape ;
         sh:targetClass ?class ;
         sh:property ?propShape .
  ?propShape sh:path ?property .
  OPTIONAL { ?propShape sh:minCount ?minCount }
  OPTIONAL { ?propShape sh:maxCount ?maxCount }
  OPTIONAL { ?propShape sh:datatype ?datatype }
  OPTIONAL { ?propShape sh:pattern ?pattern }
}
```

### 5.3 Extract Value Constraints

```sparql
SELECT ?class ?property ?valueClass ?nodeKind WHERE {
  ?shape a sh:NodeShape ;
         sh:targetClass ?class ;
         sh:property ?propShape .
  ?propShape sh:path ?property .
  OPTIONAL { ?propShape sh:class ?valueClass }
  OPTIONAL { ?propShape sh:nodeKind ?nodeKind }
}
```

---

## 6. Example Affordance Summary

For the PROV ontology, an affordance summary might look like:

```markdown
## PROV Ontology Affordances

### Navigation
- **Hierarchical**: 3 main branches (Entity, Activity, Agent) with 15+ subclasses
- **Bidirectional**: 4 inverse property pairs (generated/wasGeneratedBy, etc.)
- **Transitive**: wasDerivedFrom enables lineage tracing

### Constraints
- **Required**: All influences have agent/entity
- **Temporal**: atTime, startedAtTime, endedAtTime (xsd:dateTime)

### Query Patterns Supported
1. ✅ "Who created X?" → wasAttributedTo
2. ✅ "What is X derived from?" → wasDerivedFrom+
3. ✅ "When did X happen?" → atTime properties
4. ✅ "What role did agent play?" → qualifiedAttribution pattern
5. ✅ "Trace full provenance" → Combine derivation + generation

### Annotation Properties
- Labels: rdfs:label (161 entities labeled)
- Descriptions: rdfs:comment (107 entities documented)
```

---

## References

- [OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-overview/)
- [SHACL Specification](https://www.w3.org/TR/shacl/)
- [SPARQL 1.1 Property Paths](https://www.w3.org/TR/sparql11-property-paths/)
- [PROV-O Ontology](https://www.w3.org/TR/prov-o/)
- [Widoco Metadata Guide](https://github.com/dgarijo/Widoco/blob/master/doc/metadataGuide/guide.md)
