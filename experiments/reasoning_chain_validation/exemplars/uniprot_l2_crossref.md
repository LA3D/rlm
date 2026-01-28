# Reasoning Chain Exemplar: Level 2 - Cross-Reference Query

**Question**: "What are the GO annotations for insulin?"

**Complexity**: L2 (cross-reference between entities)

---

## Reasoning Chain

### Step 1: Identify Target Entity

**State Before**:
```
classes_discovered: []
properties_discovered: []
query_patterns: []
```

**Action**: Search for "insulin" in ontology to understand how it's represented
- Type: `explore_entity`
- Target: "insulin"
- Reasoning: Need to find the UniProt entry for insulin before finding its annotations

**Result**:
- Found: Searching the endpoint would find entries like `<http://purl.uniprot.org/uniprot/P01308>` (Human insulin)
- Key insight: Insulin is a `up:Protein`, not a concept - we need to search by label

**Verification**:
- Confirmed up:Protein exists as a class
- Confirmed proteins have rdfs:label for searching

**State After**:
```
classes_discovered: [up:Protein]
properties_discovered: [rdfs:label]
query_patterns: []
```

---

### Step 2: Understand GO Annotation Structure

**State Before**:
```
classes_discovered: [up:Protein]
properties_discovered: [rdfs:label]
query_patterns: []
```

**Action**: Search for "GO" and "annotation" to find GO annotation mechanism
- Type: `explore_class`
- Target: "GO annotation"
- Reasoning: GO (Gene Ontology) annotations are a common cross-reference type

**Result**:
- Found: `up:GO_Annotation` is a subclass of `up:Annotation`
- Found: `up:classifiedWith` property links annotations to GO terms
- GO terms are external URIs: `<http://purl.obolibrary.org/obo/GO_0005515>`

**Verification**:
- Checked: up:GO_Annotation exists
- Checked: up:classifiedWith domain includes annotations

**State After**:
```
classes_discovered: [up:Protein, up:Annotation, up:GO_Annotation]
properties_discovered: [rdfs:label, up:annotation, up:classifiedWith]
query_patterns: []
```

---

### Step 3: Find Connection Path

**State Before**:
```
classes_discovered: [up:Protein, up:Annotation, up:GO_Annotation]
properties_discovered: [rdfs:label, up:annotation, up:classifiedWith]
query_patterns: []
```

**Action**: Verify the property path from Protein to GO term
- Type: `verify_constraint`
- Target: "Protein → GO term path"
- Reasoning: Need to confirm domain/range constraints for the join

**Result**:
- Path: `up:Protein --[up:annotation]--> up:Annotation --[up:classifiedWith]--> GO_term`
- Constraint check:
  - `up:annotation` domain: `up:Protein` ✓
  - `up:annotation` range: `up:Annotation` ✓
  - `up:classifiedWith` domain: includes `up:Annotation` ✓

**Verification**: Property path is valid according to ontology constraints

**State After**:
```
classes_discovered: [up:Protein, up:Annotation, up:GO_Annotation]
properties_discovered: [rdfs:label, up:annotation, up:classifiedWith]
query_patterns: ["?protein up:annotation ?ann . ?ann up:classifiedWith ?go"]
```

---

### Step 4: Construct Complete Query

**State Before**:
```
classes_discovered: [up:Protein, up:Annotation, up:GO_Annotation]
properties_discovered: [rdfs:label, up:annotation, up:classifiedWith]
query_patterns: ["?protein up:annotation ?ann . ?ann up:classifiedWith ?go"]
```

**Action**: Build complete SPARQL query with insulin filter
- Type: `construct_query`
- Target: Complete query
- Reasoning: Combine entity filter (insulin) with annotation path

**Result**:
```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinLabel ?goTerm ?goLabel WHERE {
  ?protein a up:Protein ;
           rdfs:label ?proteinLabel ;
           up:annotation ?ann .
  ?ann a up:GO_Annotation ;
       up:classifiedWith ?goTerm .
  ?goTerm rdfs:label ?goLabel .
  FILTER(CONTAINS(LCASE(?proteinLabel), "insulin"))
} LIMIT 100
```

**Verification**: Query syntax is valid SPARQL

**State After**:
```
classes_discovered: [up:Protein, up:Annotation, up:GO_Annotation]
properties_discovered: [rdfs:label, up:annotation, up:classifiedWith]
query_patterns: ["complete query constructed"]
current_query: [above query]
```

---

### Step 5: Execute and Verify Results

**Action**: Execute query and verify result types
- Type: `execute_and_verify`
- Target: Query results
- Reasoning: Confirm results match expected structure

**Result**:
- Returned: 847 rows
- Sample row:
  ```
  ?protein = <http://purl.uniprot.org/uniprot/P01308>
  ?proteinLabel = "Insulin"
  ?goTerm = <http://purl.obolibrary.org/obo/GO_0005515>
  ?goLabel = "protein binding"
  ```

**Verification**:
- ✓ All ?protein values are up:Protein instances
- ✓ All ?ann values are up:GO_Annotation instances
- ✓ All ?goTerm values are GO URIs
- ✓ Results include expected insulin entries

---

## Final Query

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinLabel ?goTerm ?goLabel WHERE {
  ?protein a up:Protein ;
           rdfs:label ?proteinLabel ;
           up:annotation ?ann .
  ?ann a up:GO_Annotation ;
       up:classifiedWith ?goTerm .
  ?goTerm rdfs:label ?goLabel .
  FILTER(CONTAINS(LCASE(?proteinLabel), "insulin"))
} LIMIT 100
```

---

## Anti-Patterns Avoided

1. **Don't confuse annotation types**: `up:GO_Annotation` is specific - don't use generic `up:Annotation` if you want only GO terms

2. **Don't skip the annotation intermediate**: The path is Protein → Annotation → GO term, not Protein → GO term directly

3. **Don't use `up:classifiedWith` directly on Protein**: It's a property of Annotation, not Protein

4. **Don't forget to filter annotation type**: Without `?ann a up:GO_Annotation`, you'd get all annotation types

---

## Key Learnings

- **Cross-reference pattern**: Entity → Annotation → External Resource
- **Type filtering**: Use `a up:GO_Annotation` to filter annotation type
- **Label search**: Use `FILTER(CONTAINS(...))` for text matching
- **Verification**: Check domain/range before constructing joins
