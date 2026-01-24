# AGENT_GUIDE.md: UniProt Ontology

## Overview

The UniProt RDF schema ontology provides properties and classes for describing protein annotation data in the UniProt knowledge graph. It defines concepts central to protein biology including proteins, sequences, annotations, organisms, and their relationships when consensus concepts are not available in the broader bioinformatics community.

## Core Classes

- **`http://purl.uniprot.org/core/Protein`** - A protein entity with annotations, sequences, and biological properties. Use this to query for protein-specific data, functions, and relationships.

- **`http://purl.uniprot.org/core/Sequence`** - An amino acid sequence associated with proteins. Use this when you need sequence-level information like length, checksum, or modifications.

- **`http://purl.uniprot.org/core/Taxon`** - An organism or taxonomic group. Use this to filter proteins by organism or explore taxonomic relationships.

- **`http://purl.uniprot.org/core/Annotation`** - A piece of annotation data attached to proteins. Use this as a base class for specific annotation types like function, location, or disease.

- **`http://purl.uniprot.org/core/Gene`** - A gene that encodes a protein. Use this to connect proteins to their genetic context.

- **`http://purl.uniprot.org/core/Citation`** - A publication or reference. Use this to trace evidence sources for protein annotations.

- **`http://purl.uniprot.org/core/Enzyme`** - An enzyme with catalytic activities. Use this for proteins with enzymatic functions and EC classifications.

## Key Properties

- **`http://purl.uniprot.org/core/organism`**
  - Domain: Protein, Sequence | Range: Taxon
  - Usage: `?protein core:organism ?taxon`

- **`http://purl.uniprot.org/core/sequence`**
  - Domain: Protein, Annotation, Resource | Range: Sequence
  - Usage: `?protein core:sequence ?seq`

- **`http://purl.uniprot.org/core/annotation`**
  - Domain: Protein | Range: Annotation
  - Usage: `?protein core:annotation ?annotation`

- **`http://purl.uniprot.org/core/encodedBy`**
  - Domain: Protein | Range: Gene
  - Usage: `?protein core:encodedBy ?gene`

- **`http://purl.uniprot.org/core/mnemonic`**
  - Domain: Protein, Sequence, Cluster | Range: xsd:string
  - Usage: `?protein core:mnemonic ?name`

- **`http://purl.uniprot.org/core/recommendedName`**
  - Domain: Protein, Part | Range: Structured_Name
  - Usage: `?protein core:recommendedName ?name`

## Query Patterns

### Finding proteins by organism
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
SELECT ?protein ?name WHERE {
  ?protein a core:Protein ;
           core:organism ?taxon ;
           core:mnemonic ?name .
  ?taxon core:commonName "Human" .
}
```

### Getting protein sequences and their properties
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
SELECT ?protein ?seq ?length ?mass WHERE {
  ?protein a core:Protein ;
           core:sequence ?sequence .
  ?sequence core:length ?length ;
            core:mass ?mass .
}
```

### Finding enzymatic proteins with their activities
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
SELECT ?protein ?enzyme ?activity WHERE {
  ?protein a core:Protein ;
           core:enzyme ?enzyme .
  ?enzyme core:activity ?activity .
}
```

### Retrieving protein annotations with citations
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
SELECT ?protein ?annotation ?citation WHERE {
  ?protein a core:Protein ;
           core:annotation ?annotation ;
           core:citation ?citation .
}
```

### Finding proteins and their gene relationships
```sparql
PREFIX core: <http://purl.uniprot.org/core/>
SELECT ?protein ?gene ?geneName WHERE {
  ?protein a core:Protein ;
           core:encodedBy ?gene .
  ?gene core:locusName ?geneName .
}
```

## Important Considerations

- **Naming patterns**: Proteins have multiple name types (`core:recommendedName`, `core:alternativeName`, `core:submittedName`) - use `recommendedName` for canonical names
- **Sequence relationships**: The `core:sequence` property connects proteins to their amino acid sequences, which have computed properties like length and mass
- **Taxonomic navigation**: Use `core:organism` to link proteins to taxonomy; `core:commonName` provides human-readable organism names
- **Annotation types**: `core:Annotation` is a base class - specific annotation types provide more detailed information
- **Evidence tracking**: `core:citation` links to publication evidence for assertions
- **Identifiers**: `core:mnemonic` provides memorable but unstable identifiers; stable URIs should be used programmatically

## Quick Reference

**Core Classes:**
- `core:Protein` - Main protein entity
- `core:Sequence` - Amino acid sequence  
- `core:Taxon` - Organism/taxonomy
- `core:Annotation` - Protein annotation
- `core:Gene` - Encoding gene
- `core:Citation` - Literature reference

**Key Properties:**
- `core:organism` - Links to taxonomy
- `core:sequence` - Links to sequence
- `core:annotation` - Links to annotations
- `core:encodedBy` - Links to gene
- `core:mnemonic` - Human-readable name
- `core:recommendedName` - Official protein name

**Namespace:** `PREFIX core: <http://purl.uniprot.org/core/>`