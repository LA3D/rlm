# UniProt Ontology Agent Guide

## 1. Overview

The UniProt ontology is a comprehensive semantic representation of protein-related information, designed to provide a structured and machine-readable way to describe biological entities, their characteristics, annotations, and relationships. It serves as a critical knowledge representation for bioinformatics research, enabling complex queries and data integration across protein databases.

### Key Characteristics
- Namespace: `http://purl.uniprot.org/core/`
- Total Triples: 2,816
- Classes: 214
- Properties: 163
- Individuals: 45

## 2. Key Classes

### Core Biological Entities
- `Protein`: Central class representing protein molecules
- `Enzyme`: Specialized protein with catalytic activity
- `Cellular_Component`: Subcellular location and context
- `Taxon`: Biological classification and taxonomy

### Annotation Classes
- `Annotation`: Base class for protein-related descriptions
- `Biophysicochemical_Annotation`: Physical and chemical properties
- `Catalytic_Activity_Annotation`: Enzyme reaction details
- `Site_Annotation`: Specific protein region descriptions
- `Alternative_Products_Annotation`: Protein variant information

### Citation and Reference Classes
- `Citation`: Scientific publication references
- `Book_Citation`: Book-based references
- `Attribution`: Source and credit information

### Structural Classes
- `Secondary_Structure_Annotation`: Protein structural elements
- `Binding_Site_Annotation`: Interaction and binding regions
- `Modified_Sequence`: Protein sequence variations

## 3. Important Properties

### Object Properties
- `activity`: Links enzymes to catalytic activities
- `annotation`: Connects proteins with their annotations
- `cellularComponent`: Relates entities to their subcellular location
- `citation`: Connects proteins to scientific references
- `classifiedWith`: Assigns taxonomic or functional classifications

### Datatype Properties
- `abstract`: Textual description
- `alias`: Alternative names
- `author`: Publication author information
- `begin/end`: Sequence position markers

## 4. Class Hierarchies

### Annotation Hierarchy
```
Annotation
├── Biophysicochemical_Annotation
│   └── Absorption_Annotation
├── Site_Annotation
│   ├── Active_Site_Annotation
│   └── Binding_Site_Annotation
└── Alternative_Products_Annotation
    ├── Alternative_Initiation_Annotation
    └── Alternative_Splicing_Annotation
```

### Structural Hierarchy
```
Annotation
└── Secondary_Structure_Annotation
    └── Beta_Strand_Annotation
```

## 5. Common Patterns

1. **Protein Description**
   - Annotate protein with multiple annotations
   - Link to cellular components
   - Provide citations and references

2. **Enzyme Characterization**
   - Define catalytic activity
   - Specify reaction mechanisms
   - Annotate binding sites

3. **Sequence Variation**
   - Track alternative splicing
   - Describe modified sequences
   - Capture sequence variants

## 6. Practical SPARQL Examples

### 1. Find Proteins with Catalytic Activity
```sparql
SELECT ?protein ?activity
WHERE {
  ?protein a uniprot:Protein ;
           uniprot:activity ?activity .
}
```

### 2. Retrieve Cellular Locations
```sparql
SELECT ?protein ?location
WHERE {
  ?protein uniprot:cellularComponent ?location .
}
```

### 3. Get Protein Annotations
```sparql
SELECT ?protein ?annotation ?type
WHERE {
  ?protein uniprot:annotation ?annotation .
  ?annotation a ?type .
}
```

### 4. Find Enzymes by Reaction
```sparql
SELECT ?enzyme ?reaction
WHERE {
  ?enzyme a uniprot:Enzyme ;
          uniprot:catalyzedReaction ?reaction .
}
```

### 5. Protein Citations
```sparql
SELECT ?protein ?citation ?author
WHERE {
  ?protein uniprot:citation ?citation .
  ?citation uniprot:author ?author .
}
```

### 6. Alternative Product Variants
```sparql
SELECT ?protein ?variant
WHERE {
  ?protein uniprot:annotation ?annotation .
  ?annotation a uniprot:Alternative_Products_Annotation ;
              uniprot:alternativeName ?variant .
}
```

### 7. Binding Site Details
```sparql
SELECT ?protein ?site ?description
WHERE {
  ?protein uniprot:annotation ?annotation .
  ?annotation a uniprot:Binding_Site_Annotation ;
              uniprot:description ?description .
}
```

### 8. Protein Taxonomy Classification
```sparql
SELECT ?protein ?taxon
WHERE {
  ?protein uniprot:classifiedWith ?taxon .
}
```

## 7. Usage Tips

1. **Prefixes**: Always define `uniprot` namespace prefix
2. **Validation**: Use `rdf:type` to confirm class membership
3. **Completeness**: Check multiple annotation types
4. **Performance**: Use LIMIT and OFFSET for large datasets
5. **Inference**: Enable OWL reasoning for comprehensive results

### Recommended Tools
- Apache Jena
- Blazegraph
- GraphDB
- Virtuoso

### Best Practices
- Use typed queries
- Leverage class hierarchies
- Combine multiple property constraints
- Handle potential null values

**Caution**: Some relationships might be incomplete or have missing ranges/domains.

---

This guide provides a comprehensive overview of the UniProt ontology, enabling researchers and developers to effectively query and analyze protein-related semantic data.