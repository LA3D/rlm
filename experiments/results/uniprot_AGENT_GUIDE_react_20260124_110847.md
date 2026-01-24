# UniProt Ontology Agent Guide

## Overview

The UniProt ontology is a comprehensive semantic framework for representing protein data and annotations from the UniProt knowledge base. It provides structured vocabulary for describing proteins, their functions, locations, interactions, and various biological annotations. This ontology is essential for bioinformatics applications, protein research, and biological data integration.

**Namespace**: `http://purl.uniprot.org/core/`

## Core Classes

### 1. Protein (`core:Protein`)
**When to use**: The central entity representing any protein entry
**Why important**: All protein-related information connects to this class
```sparql
# Example protein instance
<http://purl.uniprot.org/uniprot/P06017> a core:Protein .
```

### 2. Annotation (`core:Annotation`)
**When to use**: Base class for all types of protein annotations
**Why important**: Provides the foundation for describing protein features, functions, and properties
**Subclasses include**:
- `Active_Site_Annotation` - Amino acids involved in enzyme activity
- `Binding_Site_Annotation` - Sites that bind other molecules
- `Catalytic_Activity_Annotation` - Enzymatic activities
- `Cellular_Component` - Subcellular locations
- `Alternative_Products_Annotation` - Splice variants and isoforms

### 3. Specialized Annotation Types
**Active_Site_Annotation**: Use for enzyme active sites
**Binding_Site_Annotation**: Use for molecular binding sites
**Catalytic_Activity_Annotation**: Use for enzymatic functions
**Cellular_Component**: Use for subcellular localization
**Alternative_Products_Annotation**: Use for protein variants

## Key Properties

### Object Properties

#### `core:annotation`
**Usage**: Links proteins to their annotations
```sparql
?protein core:annotation ?annotation .
```

#### `core:activity` / `core:catalyticActivity`
**Usage**: Links proteins to their catalytic activities
```sparql
?protein core:activity ?activity .
```

#### `core:cellularComponent`
**Usage**: Specifies where a protein is located in the cell
```sparql
?protein core:cellularComponent ?location .
```

#### `core:citation`
**Usage**: Links to bibliographic references
```sparql
?annotation core:citation ?citation .
```

### Datatype Properties

#### `core:abstract`
**Usage**: Textual descriptions and abstracts
```sparql
?citation core:abstract ?abstract .
```

#### `core:author`
**Usage**: Author information for citations
```sparql
?citation core:author ?authorName .
```

#### `core:begin` / `core:end`
**Usage**: Sequence positions for annotations
```sparql
?annotation core:begin ?startPosition ;
           core:end ?endPosition .
```

## Query Patterns

### 1. Find All Annotations for a Protein
```sparql
SELECT ?annotation ?type ?label WHERE {
  <http://purl.uniprot.org/uniprot/P06017> core:annotation ?annotation .
  ?annotation a ?type .
  OPTIONAL { ?annotation rdfs:label ?label }
}
```

### 2. Find Proteins with Specific Catalytic Activity
```sparql
SELECT ?protein ?activity WHERE {
  ?protein a core:Protein ;
           core:activity ?activity .
  ?activity rdfs:label ?activityLabel .
  FILTER(CONTAINS(LCASE(?activityLabel), "kinase"))
}
```

### 3. Get Active Sites for Enzymes
```sparql
SELECT ?protein ?activeSite ?position WHERE {
  ?protein a core:Protein ;
           core:annotation ?activeSite .
  ?activeSite a core:Active_Site_Annotation ;
              core:begin ?position .
}
```

### 4. Find Proteins by Cellular Location
```sparql
SELECT ?protein ?component WHERE {
  ?protein a core:Protein ;
           core:cellularComponent ?component .
  ?component rdfs:label ?componentLabel .
  FILTER(CONTAINS(LCASE(?componentLabel), "membrane"))
}
```

### 5. Get Protein Variants and Alternative Products
```sparql
SELECT ?protein ?variant ?variantType WHERE {
  ?protein a core:Protein ;
           core:annotation ?variant .
  ?variant a core:Alternative_Products_Annotation ;
           a ?variantType .
}
```

## Important Considerations

### 1. Annotation Hierarchy
- All specific annotation types inherit from `core:Annotation`
- Use the most specific annotation class available
- Site annotations (Active_Site, Binding_Site) inherit from `Site_Annotation`

### 2. Sequence Positions
- Use `core:begin` and `core:end` for sequence ranges
- Positions are typically 1-based
- Some annotations may have uncertain positions

### 3. Evidence and Attribution
- Annotations often have `core:attribution` linking to evidence
- Citations provide bibliographic support via `core:citation`
- Check for evidence quality indicators

### 4. Protein Status
- Distinguish between `Reviewed_Protein` and regular proteins
- Be aware of `Obsolete_Protein` entries
- Use `Not_Obsolete_Protein` for current entries

### 5. Alternative Names
- Proteins may have multiple names via `core:alternativeName`
- Common names available through `core:commonName`
- Aliases stored in `core:alias`

## Quick Reference

### Essential Classes
```
core:Protein                    # Main protein entity
core:Annotation                 # Base annotation class
core:Active_Site_Annotation     # Enzyme active sites
core:Binding_Site_Annotation    # Binding sites
core:Catalytic_Activity         # Enzymatic activities
core:Cellular_Component         # Subcellular locations
```

### Essential Properties
```
core:annotation                 # Protein → Annotation
core:activity                   # Protein → Activity
core:cellularComponent         # Protein → Location
core:begin / core:end          # Sequence positions
core:citation                  # → Bibliography
core:alternativeName           # Alternative names
```

### Common Prefixes
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
PREFIX uniprot: <http://purl.uniprot.org/uniprot/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
```

### Quick Query Template
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
SELECT ?protein ?annotation ?type WHERE {
  ?protein a core:Protein ;
           core:annotation ?annotation .
  ?annotation a ?type .
  # Add specific filters here
}
```