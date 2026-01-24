# UNIPROT Ontology Agent Guide

## Overview
The UniProt ontology is designed to systematically organize and classify protein-related data, serving as the foundational knowledge structure for the UniProt protein database. Its main purpose is to provide standardized categories and hierarchical relationships for proteins, genes, enzymes, and their various annotations (such as active sites, binding sites, and other functional features), enabling consistent data organization and retrieval. This ontology supports both current protein records and obsolete entries, while also capturing different levels of protein existence evidence to ensure comprehensive and reliable protein information management.

## Core Classes
Based on the UniProt ontology data, here are the 4-5 most important core classes and when agents should use each:

## Core Classes for UniProt Data

### 1. **Protein** 
**When to use:** This is the primary entry point for most protein-related queries.
- Retrieving basic protein information (sequence, structure, function)
- Looking up protein properties and characteristics
- Finding general protein metadata
- Starting point for most protein research workflows

### 2. **Gene**
**When to use:** When you need genetic context or gene-level information.
- Linking proteins to their encoding genes
- Studying gene expression and regulation
- Investigating genetic variants and mutations
- Connecting protein function to genomic location

### 3. **Enzyme**
**When to use:** For proteins with catalytic activity.
- Researching enzymatic reactions and pathways
- Finding enzyme classification (EC numbers)
- Studying metabolic processes
- Investigating enzyme kinetics and mechanisms
- Drug target analysis for enzymatic proteins

### 4. **Annotation**
**When to use:** For detailed functional and structural information.
- Accessing specific protein features and domains
- Finding experimental evidence and literature references
- Retrieving functional annotations and GO terms
- Getting detailed protein characterization data

### 5. **Annotation Subtypes** (Active Site, Activity Regulation, etc.)
**When to use:** For highly specific functional details.
- **Active Site**: Identifying catalytic residues and binding sites
- **Activity Regulation**: Understanding protein regulation mechanisms
- **Alternative Splicing**: Studying protein isoforms and variants
- **Allergen**: Researching allergenic proteins and immune responses

**Workflow recommendation:** Start with **Protein** for general queries, then drill down to **Gene**, **Enzyme**, or specific **Annotation** subtypes based on the research focus.

## Key Properties
Based on the UniProt core properties provided, here are the most important properties and their usage patterns:

## Most Critical Properties

### 1. **annotation** 
- **Pattern**: `Protein → Annotation`
- **Importance**: This is the foundational property that connects proteins to all types of annotations (functional, structural, localization, etc.)
- **Usage**: Acts as the primary hub for associating descriptive information with protein entries

### 2. **catalytic activity** (appears twice with different patterns)
- **Pattern 1**: `Enzyme → Catalytic_Activity` 
- **Pattern 2**: `Catalytic_Activity_Annotation → Catalytic_Activity`
- **Importance**: Central for functional annotation of enzymes
- **Usage**: Creates a hierarchical relationship where enzymes have catalytic activities, and these activities can be further annotated with specific details

### 3. **based on**
- **Pattern**: `Modified_Sequence → Simple_Sequence`
- **Importance**: Critical for sequence relationships and variant tracking
- **Usage**: Links modified protein sequences back to their original/canonical forms, essential for understanding protein modifications and isoforms

## Key Relationship Patterns

### Functional Annotation Chain
```
Protein → annotation → Catalytic_Activity_Annotation → catalytic activity → Catalytic_Activity
                                                    → catalyzed reaction
                                                    → catalyzed physiological reaction
```

### Sequence Relationship
```
Modified_Sequence → based on → Simple_Sequence
```

### Naming and Classification
- **alternativeName**: Provides structured naming variants
- **cellular component**: Links to subcellular localization
- **category**: Classifies database entries

## Usage Significance

1. **Hierarchical Organization**: Properties create multi-level relationships (Protein → Annotation → Specific Activity)

2. **Functional Characterization**: The catalytic activity properties form a comprehensive system for describing enzyme function at multiple granularity levels

3. **Sequence Integrity**: The "based on" relationship maintains traceability between sequence variants and canonical forms

4. **Cross-referencing**: Properties like "attribution" and "category" enable proper data provenance and classification

These properties collectively enable UniProt to maintain rich, interconnected protein knowledge graphs that support both human interpretation and computational analysis.

## Query Patterns
Here are 5 practical SPARQL query examples for the UniProt ontology that agents would commonly need:

## 1. Finding Proteins with Specific Annotations

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinName ?annotation ?annotationType
WHERE {
  ?protein a up:Protein ;
           up:annotation ?annotation ;
           up:recommendedName ?recName .
  ?recName up:fullName ?proteinName .
  ?annotation a ?annotationType ;
              rdfs:comment ?comment .
  
  # Filter for specific annotation types (e.g., function annotations)
  FILTER(?annotationType = up:Function_Annotation)
  
  # Optional: filter by specific keywords in comments
  FILTER(CONTAINS(LCASE(?comment), "kinase"))
}
LIMIT 50
```

## 2. Getting Enzyme Information

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinName ?ecNumber ?enzymeClass ?catalyticActivity
WHERE {
  ?protein a up:Protein ;
           up:enzyme ?enzyme ;
           up:recommendedName ?recName .
  ?recName up:fullName ?proteinName .
  
  ?enzyme up:ecName ?ecNumber .
  
  # Get catalytic activity annotation
  OPTIONAL {
    ?protein up:annotation ?catAnnotation .
    ?catAnnotation a up:Catalytic_Activity_Annotation ;
                   rdfs:comment ?catalyticActivity .
  }
  
  # Extract enzyme class from EC number (first digit)
  BIND(SUBSTR(?ecNumber, 1, 1) AS ?enzymeClass)
  
  # Filter for specific enzyme classes if needed
  # FILTER(?enzymeClass = "2")  # Transferases
}
ORDER BY ?ecNumber
LIMIT 100
```

## 3. Retrieving Protein Sequences

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinName ?sequence ?sequenceLength ?mass
WHERE {
  ?protein a up:Protein ;
           up:recommendedName ?recName ;
           up:sequence ?seqObj .
  
  ?recName up:fullName ?proteinName .
  
  ?seqObj up:value ?sequence ;
          up:length ?sequenceLength .
  
  # Get molecular weight if available
  OPTIONAL {
    ?protein up:annotation ?massAnnotation .
    ?massAnnotation a up:Mass_Spectrometry_Annotation ;
                    up:mass ?mass .
  }
  
  # Filter by organism if needed
  OPTIONAL {
    ?protein up:organism ?organism .
    ?organism up:scientificName ?organismName .
    FILTER(?organismName = "Homo sapiens")
  }
  
  # Filter by sequence length range
  FILTER(?sequenceLength >= 100 && ?sequenceLength <= 500)
}
ORDER BY DESC(?sequenceLength)
LIMIT 25
```

## 4. Finding Gene-Protein Relationships

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinName ?gene ?geneName ?organism ?chromosomeLocation
WHERE {
  ?protein a up:Protein ;
           up:recommendedName ?recName ;
           up:encodedBy ?gene ;
           up:organism ?organism .
  
  ?recName up:fullName ?proteinName .
  ?organism up:scientificName ?organismName .
  
  ?gene a up:Gene ;
        up:locusName ?geneName .
  
  # Get chromosomal location if available
  OPTIONAL {
    ?gene up:annotation ?locationAnnotation .
    ?locationAnnotation a up:Subcellular_Location_Annotation ;
                        rdfs:comment ?chromosomeLocation .
  }
  
  # Alternative gene names
  OPTIONAL {
    ?gene up:orfName ?orfName .
  }
  
  # Filter by specific organism
  FILTER(?organismName = "Homo sapiens")
  
  # Filter by gene name pattern if needed
  # FILTER(REGEX(?geneName, "^TP53", "i"))
}
ORDER BY ?geneName
LIMIT 100
```

## 5. Getting Detailed Annotation Information

```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?protein ?proteinName ?annotationType ?evidence ?confidence ?source ?description
WHERE {
  ?protein a up:Protein ;
           up:recommendedName ?recName ;
           up:annotation ?annotation .
  
  ?recName up:fullName ?proteinName .
  
  ?annotation a ?annotationType ;
              rdfs:comment ?description .
  
  # Get evidence information
  OPTIONAL {
    ?annotation up:evidence ?evidenceObj .
    ?evidenceObj a ?evidence ;
                 up:confidence ?confidence ;
                 up:source ?source .
  }
  
  # Get database cross-references for the annotation
  OPTIONAL {
    ?annotation up:database ?database .
    ?database rdfs:label ?dbName .
  }
  
  # Filter for specific annotation types
  FILTER(?annotationType IN (
    up:Function_Annotation,
    up:Subcellular_Location_Annotation,
    up:Domain_Annotation,
    up:Pathway_Annotation
  ))
  
  # Filter by evidence quality if needed
  # FILTER(?confidence = up:High_Confidence)
}
ORDER BY ?protein ?annotationType
LIMIT 200
```

## Key Features of These Queries:

1. **Namespace Usage**: All queries properly use the UniProt core namespace
2. **Flexible Filtering**: Include commented FILTER clauses that can be uncommented as needed
3. **Optional Clauses**: Use OPTIONAL to handle missing data gracefully
4. **Practical Limits**: Include LIMIT clauses to prevent overwhelming results
5. **Real-world Scenarios**: Address common research questions about proteins, genes, and their relationships

These queries can be easily modified by agents to:
- Change organism filters
- Adjust annotation types
- Modify sequence length ranges
- Add or remove optional information
- Change result limits based on needs

## Important Considerations
Based on the UniProt ontology structure, here are 4 critical considerations for agents working with this data:

## 1. **Protein Record Quality and Status**
- **Reviewed vs Unreviewed**: Prioritize `Reviewed_Protein` (Swiss-Prot) records over unreviewed (TrEMBL) ones for higher confidence data. Reviewed proteins have manual curation and experimental validation.
- **Obsolete Records**: Always filter out `Obsolete_Protein` entries unless specifically studying historical data. These may have outdated or incorrect information that could mislead analyses.
- **Redundancy**: Multiple unreviewed entries may exist for the same protein, while reviewed entries are typically non-redundant.

## 2. **Annotation Hierarchy and Specificity**
- **GO Term Hierarchy**: Gene Ontology annotations follow parent-child relationships. A protein annotated with a specific term (e.g., "protein kinase activity") implicitly has all parent annotations (e.g., "kinase activity", "catalytic activity").
- **Annotation Propagation**: When querying, consider whether you need the most specific terms only or should include broader parent terms.
- **Cross-references**: Annotations often link to external databases - ensure you're using the most appropriate source for your specific use case.

## 3. **Evidence Quality and Reliability**
- **Evidence Codes**: Pay attention to evidence codes (IEA = computational, IDA = direct assay, etc.). Experimental evidence (IDA, IMP, IGI) is generally more reliable than computational predictions (IEA, ISS).
- **Annotation Confidence**: Some annotations may be predicted or inferred rather than experimentally validated. Check the evidence supporting each annotation.
- **Source Tracking**: Different annotations may come from different databases with varying quality standards.

## 4. **Temporal and Versioning Considerations**
- **Dynamic Nature**: UniProt is continuously updated. Protein sequences, annotations, and classifications can change between releases.
- **Accession Stability**: Primary accessions are stable, but secondary accessions may be merged or deprecated.
- **Annotation Dating**: Consider when annotations were added - newer annotations may reflect more current understanding, but older experimental data may still be valuable.

These considerations are crucial for ensuring data quality, avoiding deprecated information, and properly interpreting the hierarchical relationships within the ontology.

## Quick Reference
# UniProt Ontology Quick Reference

## Key Namespaces
- **uniprot:** `http://purl.uniprot.org/uniprot/`
- **uniprotkb:** `http://purl.uniprot.org/uniprotkb/`
- **core:** `http://purl.uniprot.org/core/`
- **taxonomy:** `http://purl.uniprot.org/taxonomy/`
- **go:** `http://purl.obolibrary.org/obo/GO_`

## Most Important Classes
- **core:Protein** - Main protein entity
- **core:Gene** - Gene information
- **core:Enzyme** - Enzymatic proteins
- **core:Annotation** - General annotation container
- **core:Sequence** - Protein sequence data
- **core:Organism** - Taxonomic information
- **core:Reference** - Literature citations

## Essential Properties

### Identity & Basic Info
- **core:mnemonic** - Protein name/identifier
- **core:fullName** - Complete protein name
- **core:alternativeName** - Alternative names
- **core:sequence** - Links to sequence data
- **core:organism** - Taxonomic classification

### Functional Properties
- **core:enzyme** - EC number classification
- **core:catalyticActivity** - Enzymatic function
- **core:cofactor** - Required cofactors
- **core:pathway** - Metabolic pathways

### Structural & Location
- **core:domain** - Protein domains
- **core:subcellularLocation** - Cellular localization
- **core:transmembraneRegion** - Membrane-spanning regions
- **core:signalPeptide** - Signal sequences

### Annotations & Evidence
- **core:annotation** - General annotations
- **core:evidence** - Supporting evidence
- **core:citation** - Literature references
- **core:reviewed** - Manual curation status

## Common Prefixes
```
@prefix up: <http://purl.uniprot.org/core/> .
@prefix uniprot: <http://purl.uniprot.org/uniprot/> .
@prefix taxon: <http://purl.uniprot.org/taxonomy/> .
@prefix ec: <http://purl.uniprot.org/enzyme/> .
@prefix go: <http://purl.obolibrary.org/obo/GO_> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
```
