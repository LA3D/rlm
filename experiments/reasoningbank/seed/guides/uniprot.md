# UniProt SPARQL Endpoint Guide

UniProt (232B triples) runs QLever with PSO/POS index only. Queries with bound predicates are fast (<1s). Queries with unbound predicates timeout.

## Discovery Workflow

1. Find annotation types: `SELECT ?type WHERE { ?type rdfs:subClassOf up:Annotation }`
2. Find properties of a class: `SELECT ?prop WHERE { ?prop rdfs:domain <Class> }`
3. Describe a sample instance: `SELECT ?p ?o WHERE { <URI> ?p ?o } LIMIT 30`
4. Construct query using known predicates from steps 1-3.

## Key Predicates (always bound, always fast)

- `up:organism` — links protein to taxon (e.g., `taxon:9606` = human)
- `up:annotation` — links protein to typed annotation
- `up:encodedBy` — links protein to gene
- `up:classifiedWith` — links protein to keyword
- `up:disease` — links disease annotation to disease entity
- `up:locatedIn` — links subcellular location annotation to compartment
- `rdfs:subClassOf` — class hierarchy traversal
- `skos:prefLabel` — preferred label for entities

## Annotation Pattern

UniProt models diseases, functions, and locations as typed annotations:

```sparql
?protein up:annotation ?annot .
?annot a up:Disease_Annotation .
?annot rdfs:comment ?text .
```

Annotation types (via `?type rdfs:subClassOf up:Annotation`):
Disease_Annotation, Function_Annotation, Subcellular_Location_Annotation,
Catalytic_Activity_Annotation, Pathway_Annotation, and ~20 more.

## Safe Query Templates

**Bacterial taxa:**
```sparql
SELECT ?taxon ?name WHERE {
    ?taxon a up:Taxon .
    ?taxon up:scientificName ?name .
    ?taxon rdfs:subClassOf taxon:2 .
} LIMIT 20
```

**Human proteins with disease annotations:**
```sparql
SELECT ?name ?text WHERE {
    ?protein a up:Protein .
    ?protein up:organism taxon:9606 .
    ?protein up:encodedBy ?gene .
    ?gene skos:prefLabel ?name .
    ?protein up:annotation ?annotation .
    ?annotation a up:Disease_Annotation .
    ?annotation rdfs:comment ?text .
} LIMIT 20
```

**Disease-protein with cellular location:**
```sparql
SELECT ?protein ?disease ?location ?cellcmpt WHERE {
    ?protein up:annotation ?diseaseAnnotation , ?subcellAnnotation .
    ?diseaseAnnotation up:disease/skos:prefLabel ?disease .
    ?subcellAnnotation up:locatedIn/up:cellularComponent ?cellcmpt .
    ?cellcmpt skos:prefLabel ?location .
} LIMIT 20
```

## Timeout Patterns (NEVER use)

- `?s ?p ?o` with unbound `?p` — scans 232B triples
- `FILTER(CONTAINS(STR(?x), "..."))` on data — no text index
- `SELECT DISTINCT ?p WHERE { ?s a up:Protein . ?s ?p ?o }` — scans all proteins
- `GRAPH ?g { ?s ?p ?o }` — full cross-graph scan
