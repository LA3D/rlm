# Annotation Indexing Design

**Status:** Issue documented, implementation pending
**Priority:** Priority 2 (Correctness)
**Related:** Code review finding on label indexing (rlm/ontology.py:112-118)

## Problem Statement

The current `GraphMeta.labels` property only indexes `rdfs:label`, missing ontologies that use other annotation predicates for human-readable labels.

**Current implementation** (rlm/ontology.py:112-118):
```python
@property
def labels(self) -> dict:
    """Get label index: URI -> label string."""
    if self._labels is None:
        self._labels = {}
        for s, o in self.graph.subject_objects(RDFS.label):
            self._labels[str(s)] = str(o)
    return self._labels
```

**Impact:** Ontologies using `skos:prefLabel`, `dc:title`, `schema:name`, etc. will have empty or incomplete label indexes, breaking `search_entity()` functionality.

## Evidence from Real Ontologies

Analysis of ontologies in the repository shows varied label predicate usage:

| Ontology | rdfs:label | skos:prefLabel | schema:name | dcterms:title |
|----------|------------|----------------|-------------|---------------|
| GeoSPARQL | 0 | 65 | 9 | 1 |
| IDORG | 14 | 0 | 0 | 1 |
| DCAT-AP SHACL | 0 | 0 | 0 | 0 |

**Key finding:** GeoSPARQL uses `skos:prefLabel` exclusively - current indexing finds nothing.

## Common Label Predicates

Predicates commonly used for human-readable labels across ontology communities:

| Predicate | Namespace | Usage Context |
|-----------|-----------|---------------|
| `rdfs:label` | RDFS | Universal default |
| `skos:prefLabel` | SKOS | Vocabularies, thesauri |
| `skos:altLabel` | SKOS | Alternative/synonym labels |
| `dc:title` | Dublin Core | Document metadata |
| `dcterms:title` | DC Terms | Document metadata |
| `schema:name` | Schema.org | Web/SEO contexts |
| `foaf:name` | FOAF | Person/agent names |

**Domain-specific predicates** (harder to enumerate):
- `obo:hasExactSynonym` - OBO Foundry ontologies
- `sio:SIO_000300` - Semantic Science Integrated Ontology
- Custom vocabulary-specific predicates

## Design Options Considered

### Option 1: Hardcode Common Predicates

Always index all 7+ common predicates regardless of ontology content.

```python
LABEL_PREDICATES = [
    RDFS.label, SKOS.prefLabel, SKOS.altLabel,
    DC.title, DCTERMS.title, SCHEMA.name, FOAF.name
]
```

| Pros | Cons |
|------|------|
| Fast - single pass | Indexes predicates not used |
| Deterministic | Maintenance burden |
| Works offline | Misses domain-specific |

### Option 2: Prefix-Guided Indexing (Recommended)

Check which namespaces are bound, only index relevant predicates.

```python
NAMESPACE_LABEL_MAPPINGS = {
    'skos': [SKOS.prefLabel, SKOS.altLabel],
    'dc': [DC.title],
    'dcterms': [DCTERMS.title],
    'schema': [SCHEMA.name],
    'foaf': [FOAF.name],
}

def _build_label_index(self):
    # Always index rdfs:label
    for s, o in self.graph.subject_objects(RDFS.label):
        self._labels[str(s)] = str(o)

    # Prefix-guided: only check predicates for bound namespaces
    for prefix, predicates in NAMESPACE_LABEL_MAPPINGS.items():
        if prefix in self.namespaces:
            for pred in predicates:
                for s, o in self.graph.subject_objects(pred):
                    if str(s) not in self._labels:  # Don't overwrite
                        self._labels[str(s)] = str(o)
```

| Pros | Cons |
|------|------|
| Fast - O(1) namespace lookup | Still hardcodes mappings |
| Only scans likely predicates | Namespace bound ≠ predicate used |
| Leverages existing cached data | Misses domain-specific |
| No LLM calls | Requires maintaining mapping table |

### Option 3: Agentic Discovery

Let the agent discover label predicates through exploration.

```
Agent workflow:
1. Mount ontology with basic indexing
2. If search fails: "What annotation predicates does this ontology use?"
3. Examine ont_meta() output for Literal-valued predicates
4. LLM suggests which are "label-like"
5. Dynamically extend index
```

| Pros | Cons |
|------|------|
| Adapts to any ontology | 1-2 LLM calls per discovery |
| Discovers novel predicates | Slower, non-deterministic |
| Handles domain-specific | May hallucinate predicates |

### Option 4: Hybrid with Lazy LLM Discovery

Fast path for common cases, LLM discovery for edge cases.

```python
def build_label_index(meta: GraphMeta):
    # Fast path: prefix-guided for known namespaces
    _prefix_guided_indexing(meta)

    # Flag unknown namespaces for optional LLM discovery
    unknown = detect_unknown_annotation_namespaces(meta)
    if unknown:
        meta._pending_label_discovery = unknown
```

## Recommended Approach

**Option 2 (Prefix-Guided Indexing)** for initial indexing, with **Option 4 extension** for dynamic discovery.

### Rationale

1. **Infrastructure exists** - `GraphMeta.namespaces` is already cached
2. **Fast common case** - no LLM calls for standard vocabularies
3. **Covers 95%+ of cases** - 7 common predicates handle most ontologies
4. **Deterministic** - reproducible results, works offline
5. **Extensible** - easy to add new namespace mappings

### Agentic Discovery as Enhancement

For edge cases (domain-specific ontologies, unfamiliar vocabularies), the agent can:

1. Mount with prefix-guided indexing (fast default)
2. If `search_entity()` returns poor results, explore annotations
3. Use existing `ont_meta()` to see all Literal-valued predicates
4. Request dynamic index extension for specific predicates

This preserves fast common-path performance while enabling agentic flexibility.

## Implementation Plan

### Phase 1: Prefix-Guided Indexing

**Files to modify:**
- `nbs/01_ontology.ipynb` → `rlm/ontology.py`

**Changes:**

1. Add namespace-to-predicate mapping constant
2. Modify `GraphMeta.labels` property to use prefix-guided indexing
3. Add `GraphMeta.label_sources` property to track which predicates were indexed
4. Update tests to verify multi-predicate indexing

**Estimated scope:** ~50 lines of code changes

### Phase 2: Dynamic Index Extension

**New capabilities:**

1. `extend_label_index(meta, predicates)` - add custom predicates to index
2. `discover_label_predicates(meta)` - analyze graph for label-like predicates
3. Integration with agentic workflow for on-demand discovery

**Estimated scope:** ~100 lines of code changes

### Phase 3: LLM-Assisted Discovery (Optional)

For truly unfamiliar ontologies:

1. Extract Literal-valued predicates from `ont_meta()`
2. LLM classifies which are "label-like" vs data properties
3. Dynamically extend index based on LLM recommendations

**Considerations:**
- Should be opt-in (not default behavior)
- Cache results to avoid repeated LLM calls
- Provide manual override for known domain-specific predicates

## API Design

### Current API (unchanged)
```python
meta.labels          # URI -> label dict
meta.by_label        # label -> [URIs] inverted index
search_entity(...)   # Uses labels for search
```

### Extended API (Phase 1)
```python
meta.labels          # Now includes skos:prefLabel, dc:title, etc.
meta.label_sources   # Dict showing which predicate provided each label
meta.label_predicates_indexed  # List of predicates that were indexed
```

### Extended API (Phase 2)
```python
# Dynamic extension
extend_label_index(meta, [OBO.hasExactSynonym, CUSTOM.myLabel])

# Discovery helper
candidates = discover_label_predicates(meta)
# Returns: [{'predicate': 'obo:hasExactSynonym', 'count': 450, 'sample': '...'}]
```

## Testing Strategy

### Unit Tests

1. Test prefix-guided indexing with mock graphs
2. Verify rdfs:label always indexed (even without rdfs prefix bound)
3. Verify skos:prefLabel indexed when skos prefix present
4. Verify no double-indexing (first label wins)
5. Test dynamic extension API

### Integration Tests

1. Load GeoSPARQL vocabulary, verify skos:prefLabel indexed
2. Load IDORG ontology, verify rdfs:label indexed
3. Search functionality works across label types
4. Mixed ontology with multiple label predicates

## Migration Notes

### Backward Compatibility

- Existing code using `meta.labels` continues to work
- Labels indexed from rdfs:label still present
- Additional labels are additive, not replacement

### Potential Breaking Changes

- `len(meta.labels)` may increase (more labels indexed)
- Label value for URI may differ if skos:prefLabel exists but not rdfs:label
- Performance: slightly slower indexing (scanning more predicates)

## Related Issues

- **ont_describe() unbounded** - Uses labels for display, benefits from richer index
- **SHACL keyword extraction** - Could use same label predicates for keywords
- **search_entity() quality** - Primary beneficiary of this enhancement

## References

- [SKOS Reference](https://www.w3.org/TR/skos-reference/)
- [Dublin Core Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
- [Schema.org name property](https://schema.org/name)
- [OBO Foundry annotation properties](http://www.obofoundry.org/)

---

**Document created:** 2024-01-18
**Last updated:** 2024-01-18
**Author:** Code review analysis with Claude
