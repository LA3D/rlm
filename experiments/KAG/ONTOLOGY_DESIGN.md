# Document Ontology Design for Agentic KAG

## Purpose

This document specifies the OWL ontology and SHACL shapes needed for the RLM-based KAG document understanding experiment. This replaces Pydantic schemas with W3C standards-based validation.

## Source: DeepSeek OCR Detection Structure

DeepSeek-OCR-2 provides these semantic detection types:

```markdown
<|ref|>LABEL<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
Content...
```

**Detection Labels:**
- `title` - Document title
- `sub_title` - Section/subsection headings
- `text` - Body paragraphs
- `equation` - Mathematical equations
- `image` - Figures/diagrams
- `table` - Tabular data
- `figure_title` - Figure captions
- `table_title` - Table captions

**Bounding Boxes:** Normalized 0-1000 coordinate space

## Required Files

### 1. `ontology/document_ontology.ttl`

OWL ontology defining document structure classes and properties.

**Namespaces:**
```turtle
@prefix doc: <http://example.org/document#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
```

**Classes to Define:**

1. **Document Structure:**
   - `doc:Document` - Root container
   - `doc:Section` - Major sections (from `sub_title`)
   - `doc:Subsection` - Nested sections
   - `doc:Paragraph` - Text paragraphs (from `text`)
   - `doc:Figure` - Images/diagrams (from `image`)
   - `doc:Table` - Tabular data (from `table`)
   - `doc:Equation` - Math formulas (from `equation`)
   - `doc:Caption` - Figure/table captions (from `figure_title`/`table_title`)

2. **Abstract Class:**
   - `doc:DocumentChunk` - Parent class for all content nodes
   - Provides common properties shared by all chunks

**Properties to Define:**

1. **Content Properties:**
   - `doc:hasMainText` (DatatypeProperty, range: xsd:string)
   - `doc:hasSummary` (DatatypeProperty, range: xsd:string, optional)
   - `doc:hasContentRef` (DatatypeProperty, range: xsd:string) - Handle to blob store

2. **Structural Properties:**
   - `doc:hasSection` (ObjectProperty, domain: Document, range: Section)
   - `doc:hasSubsection` (ObjectProperty, domain: Section, range: Subsection)
   - `doc:belongsTo` (ObjectProperty, domain: Paragraph/Equation/Figure, range: Section)
   - `doc:supportedBy` (ObjectProperty, domain: DocumentChunk, range: DocumentChunk)

3. **Spatial Properties:**
   - `doc:hasBBox` (DatatypeProperty, range: xsd:string) - "[x1,y1,x2,y2]"
   - `doc:pageNumber` (DatatypeProperty, range: xsd:integer)
   - `doc:order` (DatatypeProperty, range: xsd:integer) - Reading order

4. **Metadata Properties:**
   - `doc:documentType` (DatatypeProperty, range: xsd:string)
   - `doc:detectionLabel` (DatatypeProperty, range: xsd:string) - Original OCR label

5. **Provenance Properties (using PROV-O):**
   - `prov:wasQuotedFrom` - Links to source page/detection
   - `prov:wasDerivedFrom` - Links to OCR output

**Relationships:**
- Paragraph → belongsTo → Section
- Figure → belongsTo → Section
- Equation → belongsTo → Section
- Caption → describes → Figure/Table
- Section → partOf → Document

### 2. `ontology/document_shapes.ttl`

SHACL validation shapes ensuring graph correctness.

**Namespaces:**
```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix doc: <http://example.org/document#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

**Shapes to Define:**

#### DocumentShape
Validates `doc:Document` instances.

**Constraints:**
- MUST have `doc:documentType` (exactly 1)
- MUST have at least one `doc:hasSection`
- documentType MUST be one of: "research_paper", "technical_report", "medical_document", "documentation"
- SHOULD have `doc:hasMainText` (document title)

#### SectionShape
Validates `doc:Section` instances.

**Constraints:**
- MUST have `doc:hasMainText` (section title, min length 1)
- MUST have `doc:hasContentRef` (handle to blob store)
- MUST have `doc:pageNumber` (integer >= 1)
- MUST contain at least one child (Paragraph, Equation, Figure, or Subsection)
  - Use `sh:inversePath doc:belongsTo` to check
- SHOULD have `doc:order` (reading order)

#### ParagraphShape
Validates `doc:Paragraph` instances.

**Constraints:**
- MUST have `doc:hasMainText` (min length 1)
- MUST have `doc:hasContentRef` (pattern: "^[a-z_]+:[a-f0-9]{16}$")
- MUST have `doc:belongsTo` (exactly 1, class: Section)
- MUST have `doc:pageNumber`
- MAY have `doc:hasSummary`
- MAY have `doc:supportedBy` (other chunks)
- MAY have `doc:hasBBox`

#### EquationShape
Validates `doc:Equation` instances.

**Constraints:**
- MUST have `doc:hasMainText` (equation content)
- MUST have `doc:hasContentRef`
- MUST have `doc:belongsTo` (exactly 1, class: Section)
- MUST have `doc:detectionLabel` with value "equation"
- SHOULD have `doc:hasBBox`

#### FigureShape
Validates `doc:Figure` instances.

**Constraints:**
- MUST have `doc:hasContentRef` (handle to image)
- MUST have `doc:belongsTo` (exactly 1, class: Section)
- MUST have `doc:hasBBox` (normalized coordinates)
- SHOULD have caption (via inverse relationship or property)
- MUST have `doc:detectionLabel` with value "image"

#### TableShape
Validates `doc:Table` instances.

**Constraints:**
- MUST have `doc:hasMainText` or `doc:hasContentRef`
- MUST have `doc:belongsTo` (exactly 1, class: Section)
- SHOULD have caption
- MUST have `doc:detectionLabel` with value "table"

#### CaptionShape
Validates `doc:Caption` instances.

**Constraints:**
- MUST have `doc:hasMainText` (caption text)
- MUST describe exactly one Figure or Table
- SHOULD have `doc:detectionLabel` matching "figure_title" or "table_title"

#### ContentRefShape
Validates all `doc:hasContentRef` properties.

**Constraints:**
- Pattern: "^[a-z_]+:[a-f0-9]{16}$"
- Examples: "paragraph:abc123...", "section:def456..."
- Ensures RLM-compliant handle format

## Design Principles

### 1. RLM Compliance

**All content behind handles:**
```turtle
doc:para_001 a doc:Paragraph ;
    doc:hasMainText "The Diels-Alder reaction..." ;  # Short summary OK
    doc:hasContentRef "paragraph:7a3f9c2e8b1d4f5a" . # Full text in blob store
```

**Never store large payloads in graph:**
- Use `doc:hasMainText` for short text (titles, brief summaries < 200 chars)
- Use `doc:hasContentRef` for full content (paragraphs, sections, equations)

### 2. Provenance Tracking

**Every node links to source:**
```turtle
doc:para_001 a doc:Paragraph ;
    prov:wasQuotedFrom doc:page_002 ;
    prov:wasDerivedFrom [
        a prov:Entity ;
        prov:value "<|ref|>text<|/ref|><|det|>[[66,79,492,198]]<|/det|>" ;
    ] .
```

### 3. Hierarchical Structure

**Enforced by SHACL:**
- Documents MUST contain Sections
- Sections MUST contain at least one Paragraph/Equation/Figure
- Paragraphs MUST belong to a Section
- No orphan nodes allowed

### 4. Extensibility

**Domain-specific extensions:**
```turtle
# Chemistry papers add:
chem:hasChemicalFormula a owl:DatatypeProperty ;
    rdfs:subPropertyOf doc:hasMainText .

chem:hasSMILES a owl:DatatypeProperty ;
    rdfs:domain doc:Figure .

# Medical papers add:
med:hasDiagnosisCode a owl:DatatypeProperty .
med:hasModalityType a owl:DatatypeProperty ;
    rdfs:domain doc:Figure .
```

## Example Graph Instance

```turtle
@prefix doc: <http://example.org/document#> .
@prefix ex: <http://example.org/doc/chemrxiv#> .

# Document
ex:doc_001 a doc:Document ;
    doc:documentType "research_paper" ;
    doc:hasMainText "Low-temperature retro Diels-Alder reactions" ;
    doc:hasSection ex:intro, ex:results, ex:methods .

# Section (from sub_title tag)
ex:intro a doc:Section ;
    doc:hasMainText "Introduction" ;
    doc:hasContentRef "section:3d8f7a2c1b9e5f4d" ;
    doc:pageNumber 2 ;
    doc:order 1 .

# Paragraph (from text tag)
ex:para_001 a doc:Paragraph ;
    doc:hasMainText "Diels-Alder (DA) reactions are ubiquitous..." ;
    doc:hasContentRef "paragraph:7a3f9c2e8b1d4f5a" ;
    doc:belongsTo ex:intro ;
    doc:pageNumber 2 ;
    doc:hasBBox "[66,411,492,751]" ;
    prov:wasQuotedFrom ex:page_002 .

# Equation (from equation tag)
ex:eq_001 a doc:Equation ;
    doc:hasMainText "[4+2] cycloaddition" ;
    doc:hasContentRef "equation:4b9c8d7e6f5a3b2c" ;
    doc:belongsTo ex:intro ;
    doc:detectionLabel "equation" ;
    prov:wasQuotedFrom ex:page_002 .

# Figure (from image tag)
ex:fig_001 a doc:Figure ;
    doc:hasContentRef "figure:1a2b3c4d5e6f7a8b" ;  # Handle to PNG
    doc:belongsTo ex:intro ;
    doc:hasBBox "[515,626,920,816]" ;
    doc:detectionLabel "image" ;
    prov:wasQuotedFrom ex:page_002 .

# Caption (from figure_title tag)
ex:caption_001 a doc:Caption ;
    doc:hasMainText "Figure 1. Crystal structures of DA adducts..." ;
    doc:describes ex:fig_001 ;
    doc:detectionLabel "figure_title" .
```

## Validation Example

```python
from pyshacl import validate
from rdflib import Graph

# Load graphs
data_graph = Graph().parse("chemrxiv_document.ttl")
ontology = Graph().parse("ontology/document_ontology.ttl")
shapes = Graph().parse("ontology/document_shapes.ttl")

# Validate
conforms, results_graph, report_text = validate(
    data_graph=data_graph,
    shacl_graph=shapes,
    ont_graph=ontology,
    inference='rdfs'
)

if conforms:
    print("✅ Document graph is valid!")
else:
    print("❌ Validation failed:")
    print(report_text)
```

## Next Steps

1. Create `ontology/` directory
2. Implement `document_ontology.ttl` with all classes and properties
3. Implement `document_shapes.ttl` with all validation constraints
4. Test on chemrxiv example
5. Use in agentic construction (Agent 1: StructureParser)

## References

- OWL 2 Primer: https://www.w3.org/TR/owl2-primer/
- SHACL Specification: https://www.w3.org/TR/shacl/
- PROV-O: https://www.w3.org/TR/prov-o/
- RDFLib: https://rdflib.readthedocs.io/
- pyshacl: https://github.com/RDFLib/pySHACL
