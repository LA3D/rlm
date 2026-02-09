# Document Ontology Design Using DoCO (SPAR Ontologies)

## Key Decision: Use DoCO Instead of Creating Custom Ontology

Instead of creating our own document ontology from scratch, we'll **use and extend DoCO** (Document Components Ontology) from SPAR Ontologies.

**Why DoCO?**
- ✅ W3C-standard ontology for document structure
- ✅ 60+ classes covering structural and rhetorical components
- ✅ Well-established (used in academic publishing, semantic web)
- ✅ Integrates with other SPAR ontologies (FaBiO, C4O, etc.)
- ✅ Already defines: Section, Paragraph, Figure, Table, etc.
- ✅ Hierarchical structure via `po:contains` relationships

**Source:** https://sparontologies.github.io/doco/current/doco.html

---

## DoCO Classes and DeepSeek OCR Mapping

### DeepSeek OCR Detection → DoCO Classes

| DeepSeek Label | DoCO Class | Notes |
|----------------|------------|-------|
| `title` | `doco:Title` | Document title |
| `sub_title` | `doco:Section` + `doco:SectionTitle` | Section with title |
| `text` | `doco:Paragraph` | Body paragraph |
| `equation` | `doco:Formula` | Mathematical formula |
| `image` | `doco:Figure` | Figure/diagram |
| `table` | `doco:Table` | Tabular data |
| `figure_title` | `doco:Caption` + `doco:FigureLabel` | Figure caption |
| `table_title` | `doco:Caption` + `doco:TableLabel` | Table caption |

### DoCO Hierarchy

```
doco:Document (or fabio:ResearchPaper)
├── doco:FrontMatter
│   ├── doco:Title
│   └── doco:Abstract
├── doco:BodyMatter
│   ├── doco:Section (Introduction)
│   │   ├── doco:SectionTitle
│   │   ├── doco:Paragraph
│   │   ├── doco:Paragraph
│   │   └── doco:Figure
│   │       └── doco:Caption
│   ├── doco:Section (Results)
│   │   ├── doco:SectionTitle
│   │   ├── doco:Paragraph
│   │   ├── doco:Table
│   │   └── doco:Formula
│   └── doco:Section (Methods)
└── doco:BackMatter
    └── doco:Bibliography
```

---

## Required Files

### 1. `ontology/document_ontology.ttl` - Extension of DoCO

We **import DoCO** and add RLM-specific extensions.

```turtle
@prefix doco: <http://purl.org/spar/doco/> .
@prefix po: <http://www.essepuntato.it/2008/12/pattern#> .
@prefix c4o: <http://purl.org/spar/c4o/> .
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix kag: <http://example.org/kag#> .

# Import DoCO
<http://example.org/kag/ontology> a owl:Ontology ;
    owl:imports <http://purl.org/spar/doco> ;
    rdfs:label "KAG Document Ontology" ;
    rdfs:comment "Extension of DoCO for RLM-based document understanding" .

# ============================================================================
# RLM-Specific Extensions (Not in DoCO)
# ============================================================================

# Property: ContentRef Handle (RLM-strict)
kag:hasContentRef a owl:DatatypeProperty ;
    rdfs:label "has content reference" ;
    rdfs:comment "Handle to content in blob store (RLM-compliant). Never store large payloads in graph." ;
    rdfs:domain doco:DocumentComponent ;
    rdfs:range xsd:string .

# Property: Detection Label (from DeepSeek OCR)
kag:detectionLabel a owl:DatatypeProperty ;
    rdfs:label "detection label" ;
    rdfs:comment "Original OCR detection type (title, text, image, etc.)" ;
    rdfs:domain doco:DocumentComponent ;
    rdfs:range xsd:string .

# Property: Bounding Box (normalized coordinates)
kag:hasBBox a owl:DatatypeProperty ;
    rdfs:label "has bounding box" ;
    rdfs:comment "Normalized bbox from OCR: [x1,y1,x2,y2] in 0-1000 space" ;
    rdfs:domain doco:DocumentComponent ;
    rdfs:range xsd:string .

# Property: Page Number
kag:pageNumber a owl:DatatypeProperty ;
    rdfs:label "page number" ;
    rdfs:comment "Page number where this component appears" ;
    rdfs:domain doco:DocumentComponent ;
    rdfs:range xsd:integer .

# Property: Reading Order
kag:order a owl:DatatypeProperty ;
    rdfs:label "reading order" ;
    rdfs:comment "Sequential order in document reading flow" ;
    rdfs:domain doco:DocumentComponent ;
    rdfs:range xsd:integer .

# Property: Summary (for hierarchical summarization)
kag:hasSummary a owl:DatatypeProperty ;
    rdfs:label "has summary" ;
    rdfs:comment "Multi-level summary (coarse-to-fine)" ;
    rdfs:domain doco:DocumentComponent ;
    rdfs:range xsd:string .

# ============================================================================
# Use DoCO Properties for Relationships
# ============================================================================

# Containment: Use po:contains (from Pattern Ontology, inherited by DoCO)
# - doco:Section po:contains doco:Paragraph
# - doco:Document po:contains doco:Section
# - doco:Figure po:contains doco:Caption

# Content: Use c4o:hasContent (from C4O, used by DoCO)
# - For short text snippets
# - For RLM: prefer kag:hasContentRef for large content

# Provenance: Use PROV-O
# - prov:wasQuotedFrom (links to source page)
# - prov:wasDerivedFrom (links to OCR detection)
```

### 2. `ontology/document_shapes.ttl` - SHACL Validation

Validate DoCO-based graphs with RLM constraints.

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix doco: <http://purl.org/spar/doco/> .
@prefix po: <http://www.essepuntato.it/2008/12/pattern#> .
@prefix c4o: <http://purl.org/spar/c4o/> .
@prefix kag: <http://example.org/kag#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .

# ============================================================================
# Document-Level Validation
# ============================================================================

kag:DocumentShape a sh:NodeShape ;
    sh:targetClass doco:Document ;
    sh:or (
        [ sh:class fabio:ResearchPaper ]
        [ sh:class fabio:TechnicalReport ]
        [ sh:class doco:Document ]
    ) ;

    # Must contain at least one section
    sh:property [
        sh:path po:contains ;
        sh:minCount 1 ;
        sh:class doco:Section ;
        sh:message "Document must contain at least one Section" ;
    ] ;

    # Should have title
    sh:property [
        sh:path po:contains ;
        sh:qualifiedValueShape [ sh:class doco:Title ] ;
        sh:qualifiedMinCount 1 ;
        sh:severity sh:Warning ;
        sh:message "Document should have a Title" ;
    ] .

# ============================================================================
# Section Validation
# ============================================================================

kag:SectionShape a sh:NodeShape ;
    sh:targetClass doco:Section ;

    # Must have section title
    sh:property [
        sh:path po:containsAsHeader ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:class doco:SectionTitle ;
        sh:message "Section must have exactly one SectionTitle" ;
    ] ;

    # Must contain at least one component (paragraph, figure, formula, etc.)
    sh:property [
        sh:path po:contains ;
        sh:minCount 1 ;
        sh:message "Section must contain at least one component (Paragraph, Figure, Formula, Table)" ;
    ] ;

    # RLM: Must have content handle
    sh:property [
        sh:path kag:hasContentRef ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^[a-z_]+:[a-f0-9]{16}$" ;
        sh:message "Section must have valid ContentRef handle" ;
    ] ;

    # Must have page number
    sh:property [
        sh:path kag:pageNumber ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
        sh:minInclusive 1 ;
    ] .

# ============================================================================
# Paragraph Validation
# ============================================================================

kag:ParagraphShape a sh:NodeShape ;
    sh:targetClass doco:Paragraph ;

    # Must have content (either c4o:hasContent or kag:hasContentRef)
    sh:or (
        [ sh:property [ sh:path c4o:hasContent ; sh:minCount 1 ] ]
        [ sh:property [ sh:path kag:hasContentRef ; sh:minCount 1 ] ]
    ) ;

    # RLM: Prefer ContentRef for large content
    sh:property [
        sh:path kag:hasContentRef ;
        sh:datatype xsd:string ;
        sh:pattern "^paragraph:[a-f0-9]{16}$" ;
    ] ;

    # Must be contained by a Section
    sh:property [
        sh:path [ sh:inversePath po:contains ] ;
        sh:minCount 1 ;
        sh:class doco:Section ;
        sh:message "Paragraph must be contained by a Section" ;
    ] ;

    # Must have page number
    sh:property [
        sh:path kag:pageNumber ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
    ] ;

    # Should have detection label
    sh:property [
        sh:path kag:detectionLabel ;
        sh:hasValue "text" ;
        sh:severity sh:Warning ;
    ] .

# ============================================================================
# Figure Validation
# ============================================================================

kag:FigureShape a sh:NodeShape ;
    sh:targetClass doco:Figure ;

    # Must have content reference (handle to image)
    sh:property [
        sh:path kag:hasContentRef ;
        sh:minCount 1 ;
        sh:pattern "^figure:[a-f0-9]{16}$" ;
        sh:message "Figure must have ContentRef handle to image" ;
    ] ;

    # Must be contained by a Section
    sh:property [
        sh:path [ sh:inversePath po:contains ] ;
        sh:minCount 1 ;
        sh:class doco:Section ;
    ] ;

    # Must have bounding box
    sh:property [
        sh:path kag:hasBBox ;
        sh:minCount 1 ;
        sh:pattern "^\\[[0-9]+,[0-9]+,[0-9]+,[0-9]+\\]$" ;
        sh:message "Figure must have bounding box in format [x1,y1,x2,y2]" ;
    ] ;

    # Should have caption
    sh:property [
        sh:path po:contains ;
        sh:qualifiedValueShape [ sh:class doco:Caption ] ;
        sh:qualifiedMinCount 1 ;
        sh:severity sh:Warning ;
        sh:message "Figure should have a Caption" ;
    ] ;

    # Must have detection label
    sh:property [
        sh:path kag:detectionLabel ;
        sh:hasValue "image" ;
    ] .

# ============================================================================
# Formula/Equation Validation
# ============================================================================

kag:FormulaShape a sh:NodeShape ;
    sh:targetClass doco:Formula ;

    # Must have content
    sh:or (
        [ sh:property [ sh:path c4o:hasContent ; sh:minCount 1 ] ]
        [ sh:property [ sh:path kag:hasContentRef ; sh:minCount 1 ] ]
    ) ;

    # Must be contained by a Section
    sh:property [
        sh:path [ sh:inversePath po:contains ] ;
        sh:minCount 1 ;
        sh:class doco:Section ;
    ] ;

    # Should have detection label
    sh:property [
        sh:path kag:detectionLabel ;
        sh:hasValue "equation" ;
        sh:severity sh:Warning ;
    ] .

# ============================================================================
# Table Validation
# ============================================================================

kag:TableShape a sh:NodeShape ;
    sh:targetClass doco:Table ;

    # Must have content reference
    sh:property [
        sh:path kag:hasContentRef ;
        sh:minCount 1 ;
        sh:pattern "^table:[a-f0-9]{16}$" ;
    ] ;

    # Must be contained by a Section
    sh:property [
        sh:path [ sh:inversePath po:contains ] ;
        sh:minCount 1 ;
        sh:class doco:Section ;
    ] ;

    # Should have caption
    sh:property [
        sh:path po:contains ;
        sh:qualifiedValueShape [ sh:class doco:Caption ] ;
        sh:qualifiedMinCount 1 ;
        sh:severity sh:Warning ;
    ] .

# ============================================================================
# RLM Compliance Validation
# ============================================================================

kag:ContentRefConstraint a sh:NodeShape ;
    sh:targetSubjectsOf kag:hasContentRef ;

    # All ContentRefs must match pattern
    sh:property [
        sh:path kag:hasContentRef ;
        sh:pattern "^[a-z_]+:[a-f0-9]{16}$" ;
        sh:message "ContentRef must match format: type:hash (e.g., 'paragraph:abc123...')" ;
    ] .

# Provenance Constraint
kag:ProvenanceConstraint a sh:NodeShape ;
    sh:targetClass doco:DocumentComponent ;

    # All components should have provenance
    sh:property [
        sh:path prov:wasQuotedFrom ;
        sh:minCount 1 ;
        sh:severity sh:Warning ;
        sh:message "Components should have provenance (prov:wasQuotedFrom)" ;
    ] .
```

---

## Example Graph Using DoCO

```turtle
@prefix ex: <http://example.org/doc/chemrxiv#> .
@prefix doco: <http://purl.org/spar/doco/> .
@prefix po: <http://www.essepuntato.it/2008/12/pattern#> .
@prefix c4o: <http://purl.org/spar/c4o/> .
@prefix kag: <http://example.org/kag#> .
@prefix fabio: <http://purl.org/spar/fabio/> .
@prefix prov: <http://www.w3.org/ns/prov#> .

# Document
ex:doc_001 a fabio:ResearchPaper ;
    doco:hasTitle "Low-temperature retro Diels-Alder reactions" ;
    po:contains ex:intro, ex:results, ex:methods .

# Introduction Section
ex:intro a doco:Section ;
    po:containsAsHeader ex:intro_title ;
    po:contains ex:para_001, ex:para_002, ex:fig_001 ;
    kag:hasContentRef "section:3d8f7a2c1b9e5f4d" ;
    kag:pageNumber 2 ;
    kag:order 1 .

# Section Title
ex:intro_title a doco:SectionTitle ;
    c4o:hasContent "Introduction" ;
    kag:detectionLabel "sub_title" .

# Paragraph
ex:para_001 a doco:Paragraph ;
    c4o:hasContent "Diels-Alder (DA) reactions are ubiquitous..." ;
    kag:hasContentRef "paragraph:7a3f9c2e8b1d4f5a" ;  # Full text in blob store
    kag:pageNumber 2 ;
    kag:hasBBox "[66,411,492,751]" ;
    kag:detectionLabel "text" ;
    prov:wasQuotedFrom ex:page_002 .

# Figure
ex:fig_001 a doco:Figure ;
    po:contains ex:caption_001 ;
    kag:hasContentRef "figure:1a2b3c4d5e6f7a8b" ;  # Handle to PNG
    kag:hasBBox "[515,626,920,816]" ;
    kag:detectionLabel "image" ;
    prov:wasQuotedFrom ex:page_002 .

# Caption
ex:caption_001 a doco:Caption ;
    c4o:hasContent "Figure 1. Crystal structures of DA adducts..." ;
    kag:detectionLabel "figure_title" .

# Equation
ex:eq_001 a doco:Formula ;
    c4o:hasContent "[4+2] cycloaddition" ;
    kag:hasContentRef "equation:4b9c8d7e6f5a3b2c" ;
    kag:detectionLabel "equation" ;
    prov:wasQuotedFrom ex:page_002 .
```

---

## Key Advantages of Using DoCO

### 1. Standards-Based
- Part of SPAR (Semantic Publishing and Referencing) Ontologies
- Used in academic publishing, semantic web
- Integrates with FaBiO, C4O, PROV-O

### 2. Rich Vocabulary
- 60+ classes covering all document components
- Structural (Section, Paragraph) + Rhetorical (Abstract, Introduction)
- Already defines Figure, Table, Formula, Bibliography, etc.

### 3. Proven Relationships
- `po:contains` - hierarchical containment
- `po:containsAsHeader` - section → title linking
- `c4o:hasContent` - text content
- Works with Collections Ontology for ordering

### 4. Extensible
- We only add RLM-specific properties:
  - `kag:hasContentRef` (handle to blob store)
  - `kag:detectionLabel` (OCR metadata)
  - `kag:hasBBox` (spatial info)
  - `kag:pageNumber`, `kag:order`

### 5. Interoperable
- Can export to standard formats
- Compatible with other semantic web tools
- Easier integration with existing document KGs

---

## Implementation Notes

### Import Strategy

```python
# Load DoCO from official source
from rdflib import Graph

# Option 1: Import from web (requires internet)
g = Graph()
g.parse("http://purl.org/spar/doco", format="xml")

# Option 2: Cache locally (better for experiments)
# Download DoCO once, store in ontology/doco.ttl
g.parse("ontology/doco.ttl", format="turtle")

# Then add our extensions
g.parse("ontology/document_ontology.ttl", format="turtle")
```

### Agent Mapping

Agents map DeepSeek detections to DoCO:

```python
# Agent reasoning
if tag.label == 'sub_title':
    # Create Section with SectionTitle
    section = URIRef(f"ex:section_{count}")
    g.add((section, RDF.type, DOCO.Section))

    title = URIRef(f"ex:title_{count}")
    g.add((title, RDF.type, DOCO.SectionTitle))
    g.add((title, C4O.hasContent, Literal(tag.text)))
    g.add((section, PO.containsAsHeader, title))

elif tag.label == 'text':
    # Create Paragraph
    para = URIRef(f"ex:para_{count}")
    g.add((para, RDF.type, DOCO.Paragraph))

    # Content behind handle (RLM-strict)
    content_ref = blob_store.store(tag.text, 'paragraph')
    g.add((para, KAG.hasContentRef, Literal(content_ref.ref_id)))

    # Link to containing section
    g.add((current_section, PO.contains, para))
```

---

## Next Steps

1. ✅ Use DoCO instead of custom ontology
2. Create `ontology/document_ontology.ttl` with RLM extensions
3. Create `ontology/document_shapes.ttl` with SHACL validation
4. Download/cache DoCO locally for offline use
5. Test validation on chemrxiv example
6. Implement Agent 1 (StructureParser) with DoCO mappings

## References

- **DoCO Specification:** https://sparontologies.github.io/doco/current/doco.html
- **SPAR Ontologies:** https://www.sparontologies.net/
- **Pattern Ontology (PO):** http://www.essepuntato.it/2008/12/pattern
- **C4O (Content):** http://purl.org/spar/c4o
- **FaBiO (Document Types):** http://purl.org/spar/fabio
