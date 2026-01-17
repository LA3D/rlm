# UniProt SPARQL Endpoint - Agent Navigation Guide

## Overview
This guide provides information and affordances for AI agents to effectively query the UniProt SPARQL endpoint at `https://sparql.uniprot.org/sparql/`.

## Core Resources

### Ontology & Schema
- **Core Ontology**: `ontology/uniprot/core.ttl` - Defines all UniProt classes and properties
- **Prefixes**: `ontology/uniprot/examples/prefixes.ttl` - Standard namespace declarations
- **Format**: OWL ontology in Turtle format

### Example Queries
Located in `ontology/uniprot/examples/`, organized by database/resource:
- **UniProt/** - 126 example queries for UniProtKB
- **Rhea/** - Chemical reactions and enzyme data
- **neXtProt/** - Human protein data
- **OMA/** - Orthology data
- **Bgee/** - Gene expression data
- **Cellosaurus/** - Cell line data
- **OrthoDB/** - Orthology relationships
- **HAMAP/** - Protein family signatures
- **MetaNetX/** - Metabolic networks
- **SwissLipids/** - Lipid data
- **GlyConnect/** - Glycan structures

## Key Namespaces

### Essential Prefixes
```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX uniprotkb: <http://purl.uniprot.org/uniprot/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX keywords: <http://purl.uniprot.org/keywords/>
PREFIX ec: <http://purl.uniprot.org/enzyme/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
```

### Cross-Reference Namespaces
```sparql
PREFIX GO: <http://purl.obolibrary.org/obo/GO_>
PREFIX CHEBI: <http://purl.obolibrary.org/obo/CHEBI_>
PREFIX ensembl: <http://rdf.ebi.ac.uk/resource/ensembl/>
PREFIX pubmed: <http://rdf.ncbi.nlm.nih.gov/pubmed/>
PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
```

## Core Classes

### Main Entity Types
- **up:Protein** - Protein entries (both reviewed and unreviewed)
- **up:Taxon** - Taxonomic classifications
- **up:Gene** - Gene information
- **up:Sequence** - Amino acid sequences
- **up:Enzyme** - Enzyme classification
- **up:Disease** - Disease associations
- **up:Annotation** - Various annotation types
- **up:Citation** - Literature references
- **up:Cluster** - UniRef clusters
- **up:Proteome** - Complete proteome sets

### Annotation Types (subclasses of up:Annotation)
- **up:Function_Annotation** - Protein function
- **up:Catalytic_Activity_Annotation** - Enzyme activity
- **up:Disease_Annotation** - Disease involvement
- **up:Subcellular_Location_Annotation** - Cellular location
- **up:Tissue_Specificity_Annotation** - Expression patterns
- **up:Domain_Annotation** - Protein domains
- **up:Pathway_Annotation** - Metabolic pathways
- **up:Interaction** - Protein-protein interactions
- **up:PTM_Annotation** - Post-translational modifications
- **up:Natural_Variation_Annotation** - Sequence variants
- **up:Mutagenesis_Annotation** - Experimental mutations

### Sequence Annotations
- **up:Active_Site_Annotation** - Catalytic residues
- **up:Binding_Site_Annotation** - Ligand binding
- **up:Transmembrane_Annotation** - Membrane regions
- **up:Signal_Peptide_Annotation** - Signal sequences
- **up:Domain_Extent_Annotation** - Domain boundaries
- **up:Glycosylation_Annotation** - Glycosylation sites
- **up:Disulfide_Bond_Annotation** - Disulfide bridges

## Key Properties

### Protein Properties
- **up:organism** - Links to taxon
- **up:sequence** - Links to sequence
- **up:mnemonic** - Entry name (e.g., "INS_HUMAN")
- **up:reviewed** - Boolean for Swiss-Prot (true) vs TrEMBL (false)
- **up:annotation** - Links to annotations
- **up:encodedBy** - Links to gene
- **up:classifiedWith** - Links to GO terms, keywords, etc.
- **up:enzyme** - Links to EC numbers
- **up:isolatedFrom** - Source organism/tissue

### Sequence Properties
- **rdf:value** - Actual sequence string
- **up:modified** - Date of last modification
- **up:translatedFrom** - Links to nucleotide sequence

### Annotation Properties
- **rdfs:comment** - Textual description
- **up:range** - Sequence range (for positional annotations)
- **up:evidence** - Evidence codes

### Taxonomic Properties
- **rdfs:subClassOf** - Taxonomic hierarchy (materialized)
- **up:rank** - Taxonomic rank
- **up:scientificName** - Scientific name
- **up:mnemonic** - Taxon code

## Query Patterns

### Basic Protein Query
```sparql
SELECT ?protein ?mnemonic ?organism
WHERE {
    ?protein a up:Protein ;
             up:mnemonic ?mnemonic ;
             up:organism ?organism .
}
LIMIT 10
```

### Reviewed Proteins Only (Swiss-Prot)
```sparql
SELECT ?protein
WHERE {
    ?protein a up:Protein ;
             up:reviewed true .
}
```

### Proteins by Organism
```sparql
SELECT ?protein
WHERE {
    ?protein a up:Protein ;
             up:organism taxon:9606 .  # Human
}
```

### Proteins with GO Term (including subclasses)
```sparql
SELECT ?protein
WHERE {
    ?protein a up:Protein ;
             up:classifiedWith|(up:classifiedWith/rdfs:subClassOf) GO:0016301 .
}
```

### Protein Sequences
```sparql
SELECT ?protein ?sequence
WHERE {
    ?protein a up:Protein ;
             up:sequence ?seq .
    ?seq rdf:value ?sequence .
}
```

### Annotations with Position
```sparql
SELECT ?protein ?annotation ?begin ?end ?comment
WHERE {
    ?protein a up:Protein ;
             up:annotation ?annotation .
    ?annotation a up:Active_Site_Annotation ;
                rdfs:comment ?comment ;
                up:range ?range .
    ?range faldo:begin/faldo:position ?begin ;
           faldo:end/faldo:position ?end .
}
```

## Important Query Considerations

### Taxonomic Hierarchy
- Taxonomy subclasses are **materialized** - use `rdfs:subClassOf` directly, NOT `rdfs:subClassOf+`
- Example: To get all E. coli strains, use:
  ```sparql
  ?organism rdfs:subClassOf taxon:83333 .
  ```

### Named Graphs
Some data is in specific named graphs:
- **Taxonomy**: `FROM <http://sparql.uniprot.org/taxonomy>`
- **UniRef**: Cluster data
- **Proteomes**: Complete proteome sets

### Performance Tips
1. Always filter by `up:reviewed true` when possible for curated data
2. Use specific annotation types rather than generic `up:annotation`
3. Limit organism scope when possible
4. Use LIMIT during development

## Discovery Strategies

### 1. Explore Available Properties
```sparql
SELECT DISTINCT ?property
WHERE {
    ?protein a up:Protein .
    ?protein ?property ?value .
}
LIMIT 100
```

### 2. Explore Annotation Types
```sparql
SELECT DISTINCT ?annotationType (COUNT(?annotation) AS ?count)
WHERE {
    ?protein a up:Protein ;
             up:annotation ?annotation .
    ?annotation a ?annotationType .
}
GROUP BY ?annotationType
ORDER BY DESC(?count)
```

### 3. Sample Data Exploration
```sparql
DESCRIBE uniprotkb:P05067  # Amyloid beta precursor protein
```

### 4. Check Available Classes
```sparql
SELECT DISTINCT ?class (COUNT(?instance) AS ?count)
WHERE {
    ?instance a ?class .
    FILTER(STRSTARTS(STR(?class), "http://purl.uniprot.org/core/"))
}
GROUP BY ?class
ORDER BY DESC(?count)
```

## Common Query Tasks

### Find proteins by gene name
```sparql
SELECT ?protein ?gene
WHERE {
    ?protein up:encodedBy ?gene .
    ?gene skos:prefLabel "INS" .
}
```

### Find proteins with disease associations
```sparql
SELECT ?protein ?disease
WHERE {
    ?protein up:annotation ?annotation .
    ?annotation a up:Disease_Annotation ;
                up:disease ?disease .
}
```

### Find enzyme activities
```sparql
SELECT ?protein ?ecNumber
WHERE {
    ?protein up:enzyme ?ecNumber .
}
```

### Find protein interactions
```sparql
SELECT ?protein1 ?protein2
WHERE {
    ?protein1 up:interaction ?interaction .
    ?interaction up:participant ?protein2 .
}
```

### Cross-reference to other databases
```sparql
SELECT ?protein ?pdbId
WHERE {
    ?protein rdfs:seeAlso ?pdbResource .
    ?pdbResource up:database <http://purl.uniprot.org/database/PDB> ;
                 rdfs:label ?pdbId .
}
```

## Federated Queries

UniProt can be combined with other SPARQL endpoints:
- **Wikidata**: For additional contextual information
- **Rhea**: For reaction details
- **ChEBI**: For chemical structures
- **Ensembl**: For genomic coordinates

Example federated query:
```sparql
SELECT ?protein ?geneLabel
WHERE {
    ?protein up:organism taxon:9606 ;
             up:encodedBy ?gene .
    ?gene rdfs:seeAlso ?wikidataGene .
    
    SERVICE <https://query.wikidata.org/sparql> {
        ?wikidataGene rdfs:label ?geneLabel .
        FILTER(LANG(?geneLabel) = "en")
    }
}
```

## Example Files Structure

Each example file follows this pattern:
```turtle
@prefix ex: <https://sparql.uniprot.org/.well-known/sparql-examples/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

ex:N a sh:SPARQLExecutable,
       sh:SPARQLSelectExecutable ;
    rdfs:comment "Description of what the query does"@en ;
    sh:prefixes _:sparql_examples_prefixes ;
    sh:select """[SPARQL QUERY]""" ;
    schema:keywords "keyword1", "keyword2" ;
    schema:target <https://sparql.uniprot.org/sparql/> .
```

## Resources for Further Learning

1. **UniProt Manual**: http://www.uniprot.org/manual/
2. **UniProt SPARQL Documentation**: https://sparql.uniprot.org/
3. **Example Queries Repository**: https://github.com/sib-swiss/sparql-examples/
4. **UniProt Help**: https://www.uniprot.org/help/

## Quick Reference: Common Filters

```sparql
# Reviewed entries only
?protein up:reviewed true .

# Human proteins
?protein up:organism taxon:9606 .

# Proteins with 3D structure
?protein rdfs:seeAlso ?structure .
?structure up:database <http://purl.uniprot.org/database/PDB> .

# Membrane proteins
?protein up:annotation ?annotation .
?annotation a up:Transmembrane_Annotation .

# Proteins with disease associations
?protein up:annotation ?annotation .
?annotation a up:Disease_Annotation .

# Enzymes
?protein up:enzyme ?ec .

# Proteins with GO annotation
?protein up:classifiedWith ?goTerm .
?goTerm a <http://purl.obolibrary.org/obo/GO_0003674> .  # molecular_function
```

## Troubleshooting

### Query Returns No Results
1. Check that prefixes are correctly defined
2. Verify entity URIs are in the correct namespace
3. Try removing filters one at a time
4. Use DESCRIBE or ASK to verify entities exist

### Query Times Out
1. Add LIMIT clause during development
2. Filter by organism early in the query
3. Filter by up:reviewed true for smaller dataset
4. Avoid unbounded property paths

### Understanding Data Structure
1. Use DESCRIBE on a known entity
2. Look at example queries in the relevant subdirectory
3. Check the core.ttl ontology for property definitions
4. Examine prefixes.ttl for correct namespace usage
