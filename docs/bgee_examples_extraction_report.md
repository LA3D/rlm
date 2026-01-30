# Bgee SPARQL Examples Extraction Report

## Summary

**Source**: https://www.bgee.org/support/tutorial-query-bgee-knowledge-graph-sparql

**Total queries found in tutorial**: 19 queries
**Queries already present in existing files**: 14 queries
**New queries created**: 5 queries

## Tutorial Query Mapping

### Existing Queries (Already in ontology/uniprot/examples/Bgee/)

| Tutorial Query | Existing File | Description |
|---------------|---------------|-------------|
| Q01 | 001.ttl | What are the species present in Bgee? |
| Q02 | 002.ttl | What are the species in Bgee and their scientific and common names? |
| Q03 | 003.ttl | What anatomical entities express the "APOC1" gene? |
| Q04 | 004.ttl | Where is the "APOC1" Homo sapiens gene expressed? |
| Q05 | 005.ttl | Where is "APOC1" expressed independent of developmental stage, sex, strain, and cell type? |
| Q06 | 006.ttl | Where is human "APOC1" expressed during the post-juvenile stage? |
| Q08 | 008.ttl | Where is human "APOC1" expressed in post-juvenile stage with expression scores? |
| Q09 | 009.ttl | Where is human "APOC1" expressed in post-juvenile stage, including cell types? |
| Q10 | 010.ttl | Human "APOC1" in post-juvenile with anatomical entities and cell types (Q09 optimized) |
| Q11 | 011.ttl | What developmental stages are present in Bgee? |
| Q12 | 012.ttl | Where is the eel "apoc1" gene expressed with scores? |
| Q13 | 013.ttl | Where is UniProtKB protein P02654 (APOC1) expressed? |
| Q14 | 014.ttl | What metadata exists for gene ENSG00000130208 (APOC1)? |
| Q15 | 015.ttl | Where is human "APOC1" gene absent/not expressed? |

### New Queries Created (in ontology/bgee/examples/)

| Tutorial Query | New File | Description |
|---------------|----------|-------------|
| Q07 | 030.ttl | Where is human "APOC1" expressed in the post-juvenile stage? (Q06 optimized - removes strain/sex filters for better performance) |
| Q11-a | 031.ttl | What is the post-juvenile stage IRI and description? (filtered version of Q11 using CONTAINS filter) |
| Q08-a | 032.ttl | Where is human "APOC1" expressed in post-juvenile using IRIs? (controlled vocabulary version using ENSG00000130208, UBERON_0000113, up-taxon:9606) |
| Q08-b | 033.ttl | Human "APOC1" expression with IRIs, simplified (removes organism filter from Q08-a) |
| Q12-a | 034.ttl | Eel "apoc1" gene expression using gene identifiers (uses dcterms:identifier instead of lscr:xrefNCBIGene URL) |

## Key Differences in New Queries

### 030.ttl (Q07 - Optimized Query)
- **Purpose**: Performance optimization of Q06
- **Key difference**: Removes `genex:hasSex` and `genex:hasStrain` filters that were redundant for performance
- **Use case**: When you need faster results and don't need explicit strain/sex filtering

### 031.ttl (Q11-a - Filtered Developmental Stage)
- **Purpose**: Find specific developmental stage information
- **Key difference**: Adds `FILTER (CONTAINS(?stageName,"post-juvenile"))` to narrow results
- **Use case**: When you need to look up metadata for a specific developmental stage

### 032.ttl (Q08-a - Controlled Vocabulary with IRIs)
- **Purpose**: Demonstrate use of ontology IRIs instead of labels
- **Key differences**:
  - Uses `lscr:xrefEnsemblGene ensembl:ENSG00000130208` instead of `rdfs:label "APOC1"`
  - Uses `obo:UBERON_0000113` (post-juvenile IRI) instead of label matching
  - Uses `up-taxon:9606` instead of `up:commonName "human"`
- **Use case**: More precise, machine-readable queries using standard identifiers

### 033.ttl (Q08-b - Simplified IRI Query)
- **Purpose**: Show minimal IRI-based query
- **Key difference**: Removes organism filter since Ensembl gene ID already implies human
- **Use case**: Cleaner queries when gene identifier already specifies species

### 034.ttl (Q12-a - Gene Identifier Instead of NCBI URL)
- **Purpose**: Alternative way to reference genes by identifier
- **Key difference**: Uses `dcterms:identifier "118230125"` instead of full NCBI Gene URL
- **Use case**: When you have gene IDs but not full URIs

## SHACL Format Used

All examples follow the Bgee SPARQL examples format:

```turtle
@prefix ex: <https://www.bgee.org/sparql/.well-known/sparql-examples/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

ex:NNN a sh:SPARQLExecutable,
        sh:SPARQLSelectExecutable ;
    rdfs:comment "Question in English"@en ;
    sh:prefixes _:sparql_examples_prefixes ;
    sh:select """SPARQL QUERY HERE""" ;
    schema:target <https://www.bgee.org/sparql/> .
```

## Files Created

1. `/Users/cvardema/dev/git/LA3D/rlm/ontology/bgee/examples/prefixes.ttl` - Prefix definitions
2. `/Users/cvardema/dev/git/LA3D/rlm/ontology/bgee/examples/030.ttl` - Q07 optimized query
3. `/Users/cvardema/dev/git/LA3D/rlm/ontology/bgee/examples/031.ttl` - Q11-a filtered stage query
4. `/Users/cvardema/dev/git/LA3D/rlm/ontology/bgee/examples/032.ttl` - Q08-a IRI-based query
5. `/Users/cvardema/dev/git/LA3D/rlm/ontology/bgee/examples/033.ttl` - Q08-b simplified IRI query
6. `/Users/cvardema/dev/git/LA3D/rlm/ontology/bgee/examples/034.ttl` - Q12-a identifier-based query

## Query Categories

The tutorial queries cover these main categories:

### 1. Species Discovery (Q01, Q02)
- List all species in Bgee
- Get species metadata (scientific/common names)

### 2. Basic Gene Expression (Q03, Q04, Q05)
- Find where genes are expressed
- Filter by species
- Control for biological conditions

### 3. Temporal Expression (Q06, Q07)
- Expression at specific developmental stages
- Performance optimization strategies

### 4. Quantitative Expression (Q08, Q09, Q10)
- Expression levels/scores
- Cell type specificity
- Query optimization techniques

### 5. Metadata Queries (Q11, Q11-a, Q14)
- Developmental stage information
- Gene metadata and cross-references

### 6. Alternative Identifiers (Q08-a, Q08-b, Q12, Q12-a, Q13)
- Using Ensembl gene IDs
- Using NCBI Gene IDs
- Using UniProtKB accessions
- Using ontology IRIs vs labels

### 7. Negative Results (Q15)
- Finding where genes are NOT expressed

## Notes

- All queries preserve the exact SPARQL syntax from the tutorial
- Comments accurately describe query purpose and key features
- All queries target `<https://www.bgee.org/sparql/>`
- The new examples complement existing ones by showing:
  - Performance optimization techniques (Q07)
  - Controlled vocabulary usage (Q08-a, Q08-b)
  - Alternative identifier patterns (Q11-a, Q12-a)
