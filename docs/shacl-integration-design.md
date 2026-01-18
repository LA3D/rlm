# SHACL Integration Design for RLM

This document captures design decisions for integrating SHACL (Shapes Constraint Language) with the RLM system, extending our existing rdflib-based architecture.

**Implementation Status (2026-01-18):**
- ✅ **Layer 1-2:** Shape detection, indexing, and bounded views (IMPLEMENTED)
- 🔵 **Layer 3-4:** Validation and inference APIs (FUTURE WORK - see sections marked below)

## Background

RLM currently uses rdflib for RDF graph manipulation with:
- **Handles** - Wrappers exposing metadata/summaries, not bulk data
- **Bounded views** - Progressive disclosure via `res_head()`, `res_sample()`, etc.
- **Dataset with named graphs** - `mem`, `prov`, `work/*`, `onto/*`
- **Namespace-based storage** - Results stored by name in REPL

pySHACL is built on rdflib and provides validation, inference, and constraint checking capabilities.

## Two Paradigms for SHACL + Ontology

### Paradigm 1: Separate Ontology + SHACL Validation

**Examples:** UniProt, WikiPathways, most biomedical ontologies

```
ontology.owl  →  OWL/RDFS classes, properties, axioms
shapes.ttl    →  SHACL constraints for validation
```

- Ontology defines **what things ARE** (semantics, reasoning)
- SHACL defines **what data MUST look like** (validation, constraints)
- Can be developed independently
- SHACL validates against ontology expectations

**Use case:** Existing OWL ontologies that add SHACL for data quality checking.

### Paradigm 2: SHACL-First Combined Model

**Examples:** DCAT-AP, application profiles, TopBraid EDG models

```
model.ttl  →  Classes ARE shapes (dash:ShapeClass or sh:ShapeClass)
           →  Properties defined via sh:property
           →  Constraints baked into class definitions
```

- Class definition and constraints unified
- Uses `dash:ShapeClass` or upcoming `sh:ShapeClass` (SHACL 1.2)
- Simpler mental model - "define what values should be"
- No OWL reasoning complexity

**Key insight from TopQuadrant:**
> "When you create a model in SHACL, you do not need to think whether you should use `rdfs:subClassOf` or `owl:equivalentClass`... You simply define what the values should be."

### World Assumption Differences

| Aspect | OWL | SHACL |
|--------|-----|-------|
| **World assumption** | Open (missing ≠ false) | Closed (missing = false) |
| **Primary purpose** | Classification, inference | Validation, constraints |
| **Missing data** | Infer to satisfy constraints | Report as violation |
| **Design goal** | Semantic reasoning | Data quality |

**Key insight:** OWL and SHACL can work together - OWL engines infer triples, then SHACL validates the result.

## Three Dimensions of SHACL in RLM

### Dimension 1: SHACL as Validator

```
validate(data_graph, shapes_graph) → (conforms, results_graph, results_text)
```

- "Does my data conform to these constraints?"
- "What's wrong with this data?"
- **Reactive** - checking existing data
- Results in SHACL Validation Report vocabulary

### Dimension 2: SHACL as Ontology/Schema

Shapes **define** domain structure:
- `sh:targetClass` - what class this shape describes
- `sh:property` - what properties instances should have
- `sh:datatype`, `sh:class` - expected value types
- `sh:minCount`, `sh:maxCount` - cardinality constraints

**Use case:** Query shapes as documentation to understand "what properties does X have?"

### Dimension 3: SHACL-AF as Inference Engine

SHACL Advanced Features rules (`sh:rule`, `sh:SPARQLRule`, `sh:TripleRule`):

```turtle
ex:PersonLabelRule a sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:rule [
        a sh:SPARQLRule ;
        sh:construct """
            CONSTRUCT { $this rdfs:label ?label }
            WHERE { $this ex:firstName ?fn ; ex:lastName ?ln .
                    BIND(CONCAT(?fn, " ", ?ln) AS ?label) }
        """
    ] .
```

- **Generative** - producing new triples from patterns
- Auto-classify entities based on properties
- Derive inverse relationships
- Materialize commonly-needed views
- Apply domain-specific business rules

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Unified Ontology Handling                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  mount_ontology(path, name)                                      │
│      │                                                           │
│      ├─→ Detect content type:                                    │
│      │   • Pure OWL/RDFS → index classes, properties             │
│      │   • Pure SHACL shapes → index shapes, target classes      │
│      │   • Combined (dash:ShapeClass) → index as unified model   │
│      │   • Mixed OWL + SHACL files → index both                  │
│      │                                                           │
│      └─→ Store in onto/{name}                                    │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Introspection (query shapes AS documentation):                  │
│      • "What properties does dcat:Dataset expect?"               │
│      • "What are the cardinality constraints?"                   │
│      • "What controlled vocabularies are required?"              │
│      → SPARQL on shapes graph (existing primitives work)         │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Validation (pySHACL):                                           │
│      shacl_validate(data, shapes) → ValidationResultHandle       │
│      • Bounded views on results                                  │
│      • Store in work/validation_{id}                             │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Inference (SHACL-AF):                                           │
│      shacl_infer(shapes, data) → inferred triples                │
│      • Store in work/, promote to mem                            │
│      • Provenance tracking                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Proposed API Surface

### Layer 1: Mounting (extend existing)

```python
mount_ontology(ds_meta, ns, path, ont_name, index_shacl=True)
    # Loads into onto/{ont_name}
    # If index_shacl=True and SHACL detected: builds SHACLIndex, stores in ns['{ont_name}_shacl']
    # Returns: "Mounted {ont_name}: {n} triples. SHACL: {n} shapes, {n} keywords"
```

**Note:** Class/property indexing happens separately via GraphMeta (ontology.py), not during mount_ontology.
Extended to optionally detect and index SHACL patterns.

### Layer 2: Introspection (mostly SPARQL)

Existing `sparql_local()` can query shapes:

```sparql
SELECT ?shape ?targetClass ?property ?datatype WHERE {
  ?shape a sh:NodeShape ;
         sh:targetClass ?targetClass ;
         sh:property [ sh:path ?property ; sh:datatype ?datatype ] .
}
```

**Optional convenience function:**
```python
describe_shape(shape_uri, ns, name='shape_desc')
    # Returns bounded summary of shape constraints
```

### Layer 3: Validation (FUTURE WORK - Stage 5+)

**Status:** Not yet implemented. Design proposal below.

```python
shacl_validate(data, shapes, ns, name='validation')
    # Runs pySHACL validate()
    # Stores results graph in work/validation_{name}
    # Returns: "Validation: conforms=False, 3 violations, 1 warning"
```

**Bounded views on validation results:**

```python
validation_summary(handle)
    # Returns: counts by severity (Violation/Warning/Info)

validation_violations(handle, n=5)
    # Returns: first N violations with details

validation_for_node(handle, uri)
    # Returns: all issues for specific focus node

validation_by_severity(handle, severity='Violation')
    # Returns: all results of given severity
```

### Layer 4: Inference (new)

```python
shacl_infer(shapes, data, ds_meta, task_id)
    # Runs pySHACL shacl_rules()
    # Stores in work/{task_id}
    # Records provenance in ds_meta.prov
    # Returns: "Inferred 47 triples into work/{task_id}"
```

**Status:** Not yet implemented. Design proposal above.

Then existing `work_to_mem()` promotes if desired.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Support both paradigms? | **Yes** | Real ontologies use both; detect and adapt |
| Where do shapes live? | `onto/{name}` | Unified ontology namespace |
| How to query shapes? | SPARQL (existing) | Shapes are RDF, no special API needed |
| Unified class/shape index? | **Yes** | "What properties does X have?" regardless of encoding |
| Where do validation results go? | `work/validation_{id}` | Ephemeral by default |
| Where do inferred triples go? | `work/` first, promote to `mem` | Explicit commit pattern |
| Track inference provenance? | `prov` graph entries | Consistent with existing provenance |
| New handle types? | **No** (except lightweight SHACLIndex) | Reuse Graph patterns - shapes/results are just RDF. SHACLIndex is a small REPL-resident index (~30 lines), not a bulky result handle |
| DASH vocabulary needed? | **Yes** | For `dash:ShapeClass` pattern recognition |

## Validation Report Structure

SHACL Validation Reports follow a standard vocabulary:

```turtle
[] a sh:ValidationReport ;
   sh:conforms false ;
   sh:result [
       a sh:ValidationResult ;
       sh:focusNode <http://example.org/Alice> ;
       sh:resultPath schema:email ;
       sh:resultMessage "Value does not match pattern" ;
       sh:resultSeverity sh:Violation ;
       sh:sourceConstraintComponent sh:PatternConstraintComponent ;
       sh:value "not-an-email"
   ] .
```

This structure enables natural bounded views:
- Group by `sh:resultSeverity`
- Group by `sh:focusNode`
- Filter by `sh:sourceConstraintComponent`
- Sample N results

## Example Ontologies for Testing

### DCAT-AP 3.0 (Paradigm 2 - SHACL-First)

**Repository:** https://github.com/SEMICeu/dcat-ap_shacl

**Why it's good:**
- Modern, well-structured, actively maintained
- Defines Dataset, Distribution, Catalog as shapes
- Includes cardinality, controlled vocabularies, value constraints
- Multiple national variants show extensibility
- Real-world usage at scale

**Files to download:**
- `shacl/dcat-ap-SHACL.ttl` - Main shapes
- `resources/` - Controlled vocabulary shapes

### PROV-O + SHACL (Paradigm 1 - Separate)

We already have PROV-O in `ontology/`. Could add companion SHACL constraints to demonstrate the separate model pattern.

## RLM Invariants Preserved

This design maintains core RLM principles:

1. **Context externalization** - Validation results and inferred graphs live in REPL, not root LLM context
2. **Bounded views** - Validation results exposed via summaries and progressive disclosure
3. **REPL-first discovery** - Model queries shapes, doesn't receive bulk shape definitions
4. **Handle pattern** - Results stored by name, accessed via bounded operations

## Implementation Phases

### Phase 1: Detection and Mounting
- Extend `mount_ontology()` to detect SHACL content
- Index shapes alongside OWL classes
- Add SHACL namespace handling

### Phase 2: Shape Introspection
- Verify existing SPARQL primitives work on shapes
- Add optional `describe_shape()` convenience function
- Test with DCAT-AP shapes

### Phase 3: Validation
- Integrate pySHACL `validate()`
- Create `shacl_validate()` wrapper
- Implement bounded views for validation results
- Store results in work graphs

### Phase 4: Inference
- Integrate pySHACL `shacl_rules()`
- Create `shacl_infer()` wrapper
- Add provenance tracking for inferred triples
- Test promotion workflow to mem

## Dependencies

```
pyshacl>=0.25.0  # SHACL validation and SHACL-AF rules
```

pySHACL already depends on rdflib, so no conflict with existing dependencies.

## References

- [TopQuadrant: Why I Use SHACL for Ontology Models](https://archive.topquadrant.com/shacl-blog/)
- [SHACL and OWL Compared](https://spinrdf.org/shacl-and-owl.html)
- [W3C SHACL Specification](https://www.w3.org/TR/shacl/)
- [W3C SHACL Advanced Features](https://w3c.github.io/data-shapes/shacl-af/)
- [pySHACL Documentation](https://github.com/RDFLib/pySHACL)
- [DCAT-AP SHACL Repository](https://github.com/SEMICeu/dcat-ap_shacl)
- [DASH Data Shapes Vocabulary](https://datashapes.org/dash.html)
- [Holger Knublauch: Ontology Modeling with SHACL](https://www.linkedin.com/pulse/ontology-modeling-shacl-getting-started-holger-knublauch-iwlrf)

## Open Questions

1. **Validation on write?** Should we auto-validate when adding to `mem`? Or always explicit?

2. **Inference iteration bounds?** SHACL-AF can iterate until fixpoint. Should we bound iterations?

3. **Distinguishing inferred triples?** Should inferred triples in `mem` be marked differently from asserted triples?

4. **Shape versioning?** How to handle ontology/shape updates when data was validated against older version?
