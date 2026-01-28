# Reasoning Chain Exemplar: Level 1 - Basic Entity Query

**Question**: "What is the protein with accession P12345?"

**Complexity**: L1 (single entity retrieval)

---

## Reasoning Chain

### Step 1: Understand the Query

**State Before**:
```
classes_discovered: []
properties_discovered: []
query_patterns: []
```

**Action**: Identify what information is needed
- Type: `analyze_question`
- Target: "protein with accession P12345"
- Reasoning: User wants to retrieve a specific protein by its UniProt accession number

**Result**:
- Query type: Entity retrieval by identifier
- Entity: Protein
- Identifier: P12345 (UniProt accession)

**Verification**: This is a basic lookup query - no joins needed

**State After**:
```
classes_discovered: []
properties_discovered: []
query_patterns: ["lookup by accession"]
```

---

### Step 2: Find Protein Class

**State Before**:
```
classes_discovered: []
properties_discovered: []
query_patterns: ["lookup by accession"]
```

**Action**: Search for the protein class in ontology
- Type: `explore_class`
- Target: "protein"
- Reasoning: Need to confirm the class URI for proteins

**Result**:
- Found: `up:Protein` (full URI: `http://purl.uniprot.org/core/Protein`)
- It's a core class in the UniProt ontology
- Proteins are identified by URIs like `http://purl.uniprot.org/uniprot/P12345`

**Verification**:
- Class exists: ✓
- UniProt accessions are encoded in the URI itself

**State After**:
```
classes_discovered: [up:Protein]
properties_discovered: []
query_patterns: ["lookup by accession"]
```

---

### Step 3: Understand Identifier Pattern

**State Before**:
```
classes_discovered: [up:Protein]
properties_discovered: []
query_patterns: ["lookup by accession"]
```

**Action**: Determine how accessions are represented
- Type: `verify_constraint`
- Target: "accession representation"
- Reasoning: Need to know if accession is a property or part of URI

**Result**:
- UniProt accessions ARE the URI local name
- Pattern: `http://purl.uniprot.org/uniprot/{ACCESSION}`
- So P12345 = `<http://purl.uniprot.org/uniprot/P12345>`
- Can directly construct the URI without searching

**Verification**: URI pattern confirmed from ontology documentation

**State After**:
```
classes_discovered: [up:Protein]
properties_discovered: []
query_patterns: ["URI construction from accession"]
```

---

### Step 4: Identify Useful Properties

**State Before**:
```
classes_discovered: [up:Protein]
properties_discovered: []
query_patterns: ["URI construction from accession"]
```

**Action**: Find properties to return useful information
- Type: `explore_properties`
- Target: "up:Protein properties"
- Reasoning: User likely wants more than just confirming existence

**Result**:
- `rdfs:label` - Human readable name
- `up:mnemonic` - Short name (e.g., "INS_HUMAN")
- `up:organism` - Link to organism
- `up:sequence` - Link to protein sequence

**Verification**: These properties have up:Protein in their domain

**State After**:
```
classes_discovered: [up:Protein]
properties_discovered: [rdfs:label, up:mnemonic, up:organism]
query_patterns: ["URI construction from accession"]
```

---

### Step 5: Construct Query

**State Before**:
```
classes_discovered: [up:Protein]
properties_discovered: [rdfs:label, up:mnemonic, up:organism]
query_patterns: ["URI construction from accession"]
```

**Action**: Build SPARQL query
- Type: `construct_query`
- Target: Complete query
- Reasoning: Combine URI construction with property retrieval

**Result**:
```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX uniprot: <http://purl.uniprot.org/uniprot/>

SELECT ?label ?mnemonic ?organism WHERE {
  uniprot:P12345 a up:Protein ;
                  rdfs:label ?label ;
                  up:mnemonic ?mnemonic ;
                  up:organism ?organism .
}
```

**Verification**:
- Uses correct URI construction
- Verifies type (a up:Protein) for safety
- Returns meaningful properties

**State After**:
```
classes_discovered: [up:Protein]
properties_discovered: [rdfs:label, up:mnemonic, up:organism]
query_patterns: ["complete"]
current_query: [above]
```

---

### Step 6: Execute and Verify

**Action**: Execute query and verify results
- Type: `execute_and_verify`
- Target: Query results
- Reasoning: Confirm query works and returns expected data

**Result**:
- Returned: 1 row
- Sample:
  ```
  ?label = "Insulin"
  ?mnemonic = "INS_HUMAN"
  ?organism = <http://purl.uniprot.org/taxonomy/9606>
  ```

**Verification**:
- ✓ Single result (expected for specific accession)
- ✓ Label is human-readable protein name
- ✓ Organism is a taxonomy URI (can be followed for more info)

---

## Final Query

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX uniprot: <http://purl.uniprot.org/uniprot/>

SELECT ?label ?mnemonic ?organism WHERE {
  uniprot:P12345 a up:Protein ;
                  rdfs:label ?label ;
                  up:mnemonic ?mnemonic ;
                  up:organism ?organism .
}
```

---

## Anti-Patterns Avoided

1. **Don't search by label for known accessions**: If you have the accession, construct the URI directly - don't do `FILTER(CONTAINS(?label, "P12345"))`

2. **Don't forget type verification**: Adding `a up:Protein` confirms the URI is actually a protein (protects against typos)

3. **Don't return just the URI**: Users asking "what is X" want descriptive information, not just confirmation

---

## Key Learnings

- **URI construction**: UniProt accessions can be directly converted to URIs
- **Type verification**: Always good to verify `a up:Protein` for safety
- **Useful properties**: `rdfs:label`, `up:mnemonic`, `up:organism` are commonly wanted
- **Simple queries**: L1 queries rarely need joins - direct property access on a known URI
