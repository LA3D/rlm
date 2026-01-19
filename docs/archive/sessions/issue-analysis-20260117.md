# Issue Analysis from External Review

## Summary

Investigated 10 points of feedback. Found **6 actual bugs** that need fixing, 2 design decisions, and 2 confirmations.

---

## ✅ NOT ISSUES (Confirmations)

### 1. Trajectory alignment looks good
**Status:** ✓ Confirmation - no action needed
- rlm/core.py:130 implements rlmpaper-style loop correctly
- Bounded views approach confirmed working

### 2. Core fix is correct
**Status:** ✓ Confirmation - no action needed
- llm_query returning actual response (rlm/core.py:54)
- Executable FINAL_VAR (rlm/core.py:157-173)

---

## 🤔 DESIGN DECISIONS (Not Bugs)

### 3. Missing default answer fallback
**Location:** rlm/core.py:234
**Current:** `return None, iterations, ns`
**Claim:** Should synthesize answer if no FINAL appears

**Analysis:**
- Returning `None` is explicit about failure
- Caller can inspect `iterations` to understand what happened
- Adding synthesis would be a **feature addition**, not a bug fix

**Decision:** NOT A BUG - This is a design choice
- Current behavior is clear and predictable
- If user wants fallback, they can implement it in calling code
- **Action:** Document this behavior, no code change needed

### 6b. GraphMeta.labels only uses rdfs:label
**Location:** rlm/ontology.py:108
**Current:** Only indexes `rdfs:label` triples

**Analysis:**
- This is a **limitation**, not a bug
- Supporting skos:prefLabel, language tags, etc. would be feature additions
- Current implementation works for simple ontologies

**Decision:** NOT A BUG - Document as limitation
- **Action:** Add note in docstring about label sources
- Could be enhanced later if needed

---

## 🐛 ACTUAL BUGS (Need Fixing)

### 4. exec_code captures namespace by reference
**Location:** rlm/core.py:122
**Severity:** MEDIUM - Affects debugging, not execution

**Problem:**
```python
REPLResult(..., locals=ns)  # Same object reference
```

When inspecting old iterations:
```python
iterations[0].code_blocks[0].result.locals  # Shows FINAL state, not iteration 0 state!
```

**Impact:** Confusing for post-run inspection/debugging

**Fix:** Copy namespace snapshot:
```python
REPLResult(..., locals=dict(ns))  # Snapshot at this iteration
```

---

### 5. Multi-ontology composition breaks
**Location:** rlm/ontology.py:464-466
**Severity:** HIGH - If using multiple ontologies

**Problem:**
```python
# First ontology
ns['search_by_label'] = partial(search_by_label, prov_meta)

# Second ontology OVERWRITES first!
ns['search_by_label'] = partial(search_by_label, sio_meta)
```

**Impact:** Can't use helpers for both ontologies

**Fix Options:**
1. Namespace helpers by ontology name:
   ```python
   ns['prov_search_by_label'] = partial(search_by_label, prov_meta)
   ns['sio_search_by_label'] = partial(search_by_label, sio_meta)
   ```

2. Or use meta objects directly:
   ```python
   # No global helpers, use meta methods
   ns['prov_meta'].search_by_label('Activity')
   ```

**Recommendation:** Option 2 (use meta objects) - cleaner, already partially implemented

---

### 6a. describe_entity ignores limit parameter
**Location:** rlm/ontology.py:232
**Severity:** LOW - Wrong but usually harmless

**Problem:**
```python
def describe_entity(meta: GraphMeta, uri: str, limit: int = 20) -> dict:
    ...
    outgoing = []
    for p, o in list(meta.graph.predicate_objects(entity))[:limit]:  # Respects limit here
        outgoing.append((str(p), str(o)))

    return {
        ...
        'outgoing_sample': outgoing[:10]  # BUG: Hardcoded to 10!
    }
```

**Impact:** Always returns max 10 triples, even if limit=100

**Fix:**
```python
'outgoing_sample': outgoing[:limit]  # Use the limit parameter
```

---

### 7a. mem_add only handles http: URIs
**Location:** rlm/dataset.py:144-146
**Severity:** HIGH - Data corruption risk

**Problem:**
```python
s = URIRef(subject) if isinstance(subject, str) and subject.startswith('http') else subject
```

**Impact:**
- `urn:uuid:123` remains as Python string → breaks rdflib expectations
- `urn:example:foo` as object → becomes Literal instead of URIRef

**Examples that break:**
```python
mem_add('urn:uuid:123', 'rdf:type', 'http://ex.org/Thing')  # Subject is string!
mem_add('http://ex.org/alice', 'owl:sameAs', 'urn:uuid:456')  # Object is Literal!
```

**Fix:**
```python
def _to_rdf_term(value):
    """Convert value to appropriate RDF term."""
    if isinstance(value, (URIRef, Literal, BNode)):
        return value  # Already an RDF term
    if isinstance(value, str):
        # Check if it looks like a URI (has scheme)
        if ':' in value and not value.startswith('_:'):
            return URIRef(value)
        # Otherwise literal
        return Literal(value)
    if isinstance(value, (int, float, bool)):
        return Literal(value)
    return value

s = _to_rdf_term(subject)
p = URIRef(predicate) if isinstance(predicate, str) else predicate
o = _to_rdf_term(obj)
```

---

### 7b. DatasetMeta.summary() onto-graph counting wrong
**Location:** rlm/dataset.py:82
**Severity:** LOW - Cosmetic issue

**Problem:**
```python
f"onto graphs: {len([g for g in self.graph_stats.keys() if '/onto/' in g])}"
```

**Graph URIs are:** `urn:rlm:ds:onto/prov`
**Pattern checks for:** `/onto/` (never matches!)
**Should check for:** `:onto/` or `onto/`

**Impact:** Always reports "onto graphs: 0" even when ontologies loaded

**Fix:**
```python
f"onto graphs: {len([g for g in self.graph_stats.keys() if ':onto/' in g])}"
```

---

### 7c. load_snapshot treats .ttl as TriG
**Location:** rlm/dataset.py:401
**Severity:** MEDIUM - File format confusion

**Problem:**
```python
format = 'trig' if ext in ['.trig', '.ttl'] else 'nquads'
```

**Impact:**
- Turtle (.ttl) and TriG (.trig) are DIFFERENT formats
- Turtle = single-graph RDF
- TriG = multi-graph RDF (Turtle + named graphs)
- Loading .ttl as TriG might work sometimes but is semantically wrong

**Fix:**
```python
if ext == '.trig':
    format = 'trig'
elif ext == '.ttl':
    format = 'turtle'  # Proper format for .ttl
elif ext in ['.nq', '.nquads']:
    format = 'nquads'
else:
    # Try to guess
    format = 'trig'  # Default for datasets
```

---

## Priority Ranking

### P0 - Critical (Must Fix Now)
1. **7a: mem_add URI coercion** - Data corruption risk
2. **5: Multi-ontology composition** - Breaks documented use case

### P1 - Important (Fix Soon)
3. **4: exec_code namespace reference** - Debugging confusion
4. **7c: load_snapshot format** - File format bugs

### P2 - Nice to Have (Can Wait)
5. **6a: describe_entity limit** - Minor inconsistency
6. **7b: onto-graph counting** - Cosmetic only

### Documentation Only
7. **3: No default answer** - Document as design choice
8. **6b: rdfs:label only** - Document limitation

---

## Recommended Action Plan

1. **Immediate:** Fix P0 bugs (7a, 5)
2. **Soon:** Fix P1 bugs (4, 7c)
3. **Eventually:** Fix P2 bugs (6a, 7b)
4. **Document:** Add notes for #3 and #6b

## Test Coverage Needed

After fixes:
- Test urn: URIs in mem_add
- Test multiple ontology loading
- Test .ttl vs .trig snapshot loading
- Test iteration.result.locals snapshots
