# Structured Output Comparison: Pydantic vs. OWL+SHACL

## Overview

The original KAG implementation used **Pydantic models with LLM structured outputs** to enforce schema conformance. This document explains why the RLM-based KAG experiment uses **OWL ontologies with SHACL validation** instead, and how this enables truly agentic behavior while maintaining structure guarantees.

## Problem: How to Enforce Structure in Document Graphs?

Both approaches solve the same problem:
> **"How do we ensure the LLM produces document graphs that conform to a specific schema/ontology, without making up its own structure?"**

This is critical because downstream systems (knowledge graph queries, graph databases, reasoning engines) expect consistent structure.

---

## Approach 1: Original KAG (Pydantic + Structured Outputs)

### Architecture

```
Markdown Text
    ↓
LLM Call (with Pydantic schema injected)
    ↓
Structured JSON Output (forced to match schema)
    ↓
DocumentGraph object (validated by Pydantic)
    ↓
JSON-LD serialization
```

### Code Example

```python
from pydantic import BaseModel, Field, constr
from typing import List, Optional, Dict

# Define schema as Pydantic models
class DocumentChunk(BaseModel):
    """Schema enforced by Pydantic validation."""
    id: str
    type: str
    mainText: str
    summary: Optional[str] = None
    supporting_chunks: List[str] = []
    belongTo: Optional[str] = None  # Must link to section
    relationships: List[Dict]

class DocumentGraph(BaseModel):
    """Top-level document graph."""
    id: str
    document_type: str
    chunks: List[DocumentChunk]
    metadata: Dict
    context: Dict = DOCUMENT_CONTEXT  # JSON-LD

# LLM call with structured output
llm_client = Anthropic()
response = llm_client.messages.create(
    model="claude-3-5-sonnet",
    messages=[{
        "role": "user",
        "content": f"Extract document structure from: {text}"
    }],
    # CRITICAL: Force output to match schema
    response_format=DocumentGraph.model_json_schema()
)

# Parse and validate
doc_graph = DocumentGraph.model_validate_json(response.content)
# → Guaranteed to conform or raises ValidationError
```

### Strengths

✅ **Guaranteed conformance** - LLM must output valid JSON or fails
✅ **Type safety** - Python type hints enforced
✅ **Fast validation** - Pydantic is efficient
✅ **Simple** - Direct Python → JSON workflow

### Weaknesses

❌ **Not agentic** - LLM forced into fixed schema, can't reason about structure
❌ **No learning** - Same schema every time, no strategy accumulation
❌ **Brittle** - Schema change = rewrite all prompts
❌ **Domain-specific** - `DocumentChunk` schema baked into code
❌ **No repair** - Invalid output = failure, no recovery
❌ **Limited flexibility** - Can't extend schema mid-execution
❌ **Payload injection** - Full text often passed to LLM

### Example Schema (from KAG notebooks)

```python
class SpatialRelationship(BaseModel):
    from_region: constr(pattern=r"^r[0-9]+$")
    to_region: constr(pattern=r"^r[0-9]+$")
    relationship: constr(pattern="^(above|below|left_of|right_of)$")

class Region(BaseModel):
    id: constr(pattern=r"^r[0-9]+$")
    name: str
    type: str
    order: int = Field(ge=1)
    position: str
    bbox: Optional[List[int]] = None

class Layout(BaseModel):
    regions: List[Region]
    reading_flow: List[constr(pattern=r"^r[0-9]+$")]
    spatial_relationships: List[SpatialRelationship]

class DocumentLayout(BaseModel):
    document_type: str
    layout: Layout
```

**The workflow:**
1. LLM receives page image + schema
2. LLM must output JSON matching `DocumentLayout`
3. Pydantic validates (pass/fail)
4. JSON-LD context added manually
5. Graph constructed from validated JSON

---

## Approach 2: RLM-Based KAG (OWL + SHACL)

### Architecture

```
Markdown Text (behind ContentRef handle)
    ↓
Agent reasons about structure
    ↓
Agent writes code to build RDF graph
    ↓
Code executes (propose)
    ↓
SHACL validates graph (verify)
    ↓
If violations: Agent repairs (iterate)
    ↓
Valid RDF graph (conforming to ontology)
```

### Code Example

#### 1. Define Ontology (OWL) - Replaces Pydantic Models

```turtle
# ontology/document_ontology.ttl
@prefix doc: <http://example.org/document#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Classes (like Pydantic classes)
doc:Document a owl:Class ;
    rdfs:label "Document" ;
    rdfs:comment "Top-level document container" .

doc:Section a owl:Class ;
    rdfs:label "Section" ;
    rdfs:comment "Document section (from sub_title tags)" .

doc:Paragraph a owl:Class ;
    rdfs:label "Paragraph" ;
    rdfs:comment "Text paragraph (from text tags)" .

doc:Figure a owl:Class ;
    rdfs:label "Figure" ;
    rdfs:comment "Figure or image (from image tags)" .

doc:Equation a owl:Class ;
    rdfs:label "Equation" ;
    rdfs:comment "Mathematical equation" .

# Properties (like Pydantic fields)
doc:hasSection a owl:ObjectProperty ;
    rdfs:domain doc:Document ;
    rdfs:range doc:Section .

doc:hasMainText a owl:DatatypeProperty ;
    rdfs:domain doc:DocumentChunk ;
    rdfs:range xsd:string .

doc:hasSummary a owl:DatatypeProperty ;
    rdfs:domain doc:DocumentChunk ;
    rdfs:range xsd:string .

doc:belongsTo a owl:ObjectProperty ;
    rdfs:domain doc:Paragraph ;
    rdfs:range doc:Section ;
    rdfs:label "belongs to" ;
    rdfs:comment "Links paragraphs to their containing section" .

doc:supportedBy a owl:ObjectProperty ;
    rdfs:domain doc:DocumentChunk ;
    rdfs:range doc:DocumentChunk ;
    rdfs:label "supported by" ;
    rdfs:comment "Supporting evidence relationship" .

doc:hasContentRef a owl:DatatypeProperty ;
    rdfs:domain doc:DocumentChunk ;
    rdfs:range xsd:string ;
    rdfs:comment "Handle to content in blob store (RLM-strict)" .
```

#### 2. Define Validation (SHACL) - Replaces Pydantic Validators

```turtle
# ontology/document_shapes.ttl
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix doc: <http://example.org/document#> .

# Validates all Paragraphs
doc:ParagraphShape a sh:NodeShape ;
    sh:targetClass doc:Paragraph ;

    # MUST have mainText (required=True in Pydantic)
    sh:property [
        sh:path doc:hasMainText ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
        sh:minLength 1 ;
        sh:message "Paragraphs must have non-empty mainText" ;
    ] ;

    # MUST belong to exactly one section
    sh:property [
        sh:path doc:belongsTo ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:class doc:Section ;
        sh:message "Paragraphs must belong to exactly one Section" ;
    ] ;

    # MAY have summary (Optional[str] in Pydantic)
    sh:property [
        sh:path doc:hasSummary ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
    ] ;

    # MUST have content handle (RLM-strict)
    sh:property [
        sh:path doc:hasContentRef ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^[a-z_]+:[a-f0-9]{16}$" ;  # Like "paragraph:abc123..."
        sh:message "Must have valid ContentRef handle" ;
    ] .

# Validates all Sections
doc:SectionShape a sh:NodeShape ;
    sh:targetClass doc:Section ;

    # Sections must have at least one paragraph
    sh:property [
        sh:path [ sh:inversePath doc:belongsTo ] ;
        sh:minCount 1 ;
        sh:class doc:Paragraph ;
        sh:message "Sections must contain at least one Paragraph" ;
    ] ;

    # Sections must have title
    sh:property [
        sh:path doc:hasMainText ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .

# Validates entire Document
doc:DocumentShape a sh:NodeShape ;
    sh:targetClass doc:Document ;

    # Document must have at least one section
    sh:property [
        sh:path doc:hasSection ;
        sh:minCount 1 ;
        sh:class doc:Section ;
        sh:message "Document must have at least one Section" ;
    ] ;

    # Document must have type
    sh:property [
        sh:path doc:documentType ;
        sh:minCount 1 ;
        sh:in ("research_paper" "technical_report" "medical_document") ;
        sh:message "Document must have valid type" ;
    ] .
```

#### 3. Agentic Construction (Propose → Verify → Repair)

```python
from pyshacl import validate
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS

DOC = Namespace("http://example.org/document#")

class DocumentStructureAgent:
    """Agent that builds document graphs with SHACL validation."""

    def __init__(self, ontology_path, shapes_path, blob_store):
        self.ontology = Graph().parse(ontology_path)
        self.shapes = Graph().parse(shapes_path)
        self.blob_store = blob_store

    def build_graph(self, ocr_sense, page_refs, schema):
        """
        Agentic graph construction with validation loop.

        Agent reasons about structure, proposes RDF graph,
        validates with SHACL, repairs if needed.
        """

        # 1. PROPOSE: Agent reasons and writes code
        reasoning = self._reason_about_structure(ocr_sense, page_refs)
        code = self._generate_construction_code(reasoning)

        # 2. EXECUTE: Run agent's code
        namespace = {
            'parse_detection_tags': self.parse_detection_tags,
            'create_node': self._create_node,
            'add_property': self._add_property,
            'link_nodes': self._link_nodes,
            'blob_store': self.blob_store,
            'DOC': DOC,
            'RDF': RDF,
            'g': Graph(),  # Working graph
        }

        exec(code, namespace)
        proposed_graph = namespace['g']

        # 3. VERIFY: SHACL validation
        conforms, results_graph, report_text = validate(
            data_graph=proposed_graph,
            shacl_graph=self.shapes,
            ont_graph=self.ontology,
            inference='rdfs',  # Enable RDFS reasoning
            abort_on_first=False
        )

        if conforms:
            # Success! Store and return handle
            graph_ref = self.blob_store.store(
                content=proposed_graph.serialize(format='turtle'),
                content_type='document_graph'
            )
            return {
                'success': True,
                'graph_ref': graph_ref,
                'violations': []
            }

        # 4. REPAIR: Extract violations and fix
        violations = self._parse_shacl_violations(results_graph)

        for attempt in range(3):  # Max 3 repair attempts
            repair_code = self._generate_repair_code(violations)
            exec(repair_code, namespace)

            # Re-validate
            conforms, results_graph, _ = validate(
                namespace['g'], self.shapes, self.ontology
            )

            if conforms:
                graph_ref = self.blob_store.store(
                    namespace['g'].serialize(format='turtle'),
                    'document_graph'
                )
                return {
                    'success': True,
                    'graph_ref': graph_ref,
                    'violations': [],
                    'repairs': attempt + 1
                }

            violations = self._parse_shacl_violations(results_graph)

        # Failed to repair
        report_ref = self.blob_store.store(report_text, 'shacl_report')
        return {
            'success': False,
            'violations': violations,
            'report_ref': report_ref
        }

    def _reason_about_structure(self, ocr_sense, page_refs):
        """Agent reasons about document structure (using DSPy)."""
        # Agent sees:
        # - OCR sense: page_count=8, has equations, inferred_type=research_paper
        # - Page refs: List of handles (NOT raw text!)
        # - Schema constraints from SHACL shapes

        return """
        1. OCR sense shows research paper with 8 pages
        2. Detection types include: title, sub_title, text, equation, image
        3. Page 1 has single 'title' tag → Document title
        4. Pages 2-7 have 'sub_title' tags → Section boundaries
        5. 'text' tags following sub_title → Paragraphs in that section
        6. 'equation' tags → Equation nodes linked to sections
        7. 'image' tags → Figure nodes
        8. Need to build: Document → Sections → Paragraphs/Equations/Figures
        9. SHACL requires: every Paragraph must belongsTo a Section
        10. SHACL requires: every Section must have at least one Paragraph
        """

    def _generate_construction_code(self, reasoning):
        """Agent generates code to build graph (DSPy output)."""
        return """
# Create document root
doc_uri = URIRef("http://example.org/doc/chemrxiv_001")
g.add((doc_uri, RDF.type, DOC.Document))
g.add((doc_uri, DOC.documentType, Literal("research_paper")))

current_section = None
para_count = 0
eq_count = 0

for i, page_ref in enumerate(page_refs):
    # Parse detection tags (bounded access!)
    tags = parse_detection_tags(page_ref, max_tags=100)

    for tag in tags:
        if tag.label == 'title' and i == 0:
            # Document title
            g.add((doc_uri, DOC.hasMainText, Literal(tag.text)))

        elif tag.label == 'sub_title':
            # New section
            section_uri = URIRef(f"http://example.org/doc/section_{i}")
            g.add((section_uri, RDF.type, DOC.Section))
            g.add((section_uri, DOC.hasMainText, Literal(tag.text)))
            g.add((doc_uri, DOC.hasSection, section_uri))

            # Store content behind handle
            content_ref = blob_store.store(tag.text, 'section')
            g.add((section_uri, DOC.hasContentRef, Literal(content_ref.ref_id)))

            current_section = section_uri

        elif tag.label == 'text' and current_section:
            # Paragraph
            para_count += 1
            para_uri = URIRef(f"http://example.org/doc/para_{para_count}")
            g.add((para_uri, RDF.type, DOC.Paragraph))
            g.add((para_uri, DOC.hasMainText, Literal(tag.text)))
            g.add((para_uri, DOC.belongsTo, current_section))  # Link!

            # Handle for content
            content_ref = blob_store.store(tag.text, 'paragraph')
            g.add((para_uri, DOC.hasContentRef, Literal(content_ref.ref_id)))

        elif tag.label == 'equation' and current_section:
            # Equation
            eq_count += 1
            eq_uri = URIRef(f"http://example.org/doc/eq_{eq_count}")
            g.add((eq_uri, RDF.type, DOC.Equation))
            g.add((eq_uri, DOC.hasMainText, Literal(tag.text)))
            g.add((eq_uri, DOC.belongsTo, current_section))

            content_ref = blob_store.store(tag.text, 'equation')
            g.add((eq_uri, DOC.hasContentRef, Literal(content_ref.ref_id)))

# Graph complete - will be validated by SHACL
"""

    def _parse_shacl_violations(self, results_graph):
        """Extract violations from SHACL validation report."""
        SH = Namespace("http://www.w3.org/ns/shacl#")
        violations = []

        for result in results_graph.subjects(RDF.type, SH.ValidationResult):
            severity = results_graph.value(result, SH.resultSeverity)
            if severity != SH.Violation:
                continue

            focus_node = results_graph.value(result, SH.focusNode)
            path = results_graph.value(result, SH.resultPath)
            message = results_graph.value(result, SH.resultMessage)

            violations.append({
                'focus_node': str(focus_node),
                'path': str(path) if path else None,
                'message': str(message)
            })

        return violations

    def _generate_repair_code(self, violations):
        """Agent generates code to fix SHACL violations."""
        # Agent sees symbolic violation data (not full report!)
        # Generates targeted fixes

        # Example: "Paragraph must belong to Section"
        # → Find orphan paragraphs, link to nearest section

        return """
# Repair orphan paragraphs
for para in g.subjects(RDF.type, DOC.Paragraph):
    if not g.value(para, DOC.belongsTo):
        # Find section on same page
        para_page = extract_page_number(para)
        section = find_section_on_page(para_page)
        if section:
            g.add((para, DOC.belongsTo, section))
"""
```

### Strengths

✅ **Truly agentic** - Agent reasons about structure, not forced
✅ **Self-repairing** - SHACL violations → agent fixes → iterate
✅ **Learnable** - Repair operators accumulate in L2 memory
✅ **Domain-agnostic** - Same agents work on different ontologies
✅ **Flexible** - Can extend ontology during execution
✅ **RLM-compliant** - Content behind handles, bounded access
✅ **Provenance** - Full chain from detection tag → graph node
✅ **Standards-based** - OWL, SHACL, RDF (interoperable)

### Weaknesses

⚠️ **More complex** - Requires OWL + SHACL knowledge
⚠️ **Slower** - Propose → verify → repair loop vs. single LLM call
⚠️ **Setup overhead** - Must define ontology + shapes upfront

---

## Side-by-Side Comparison

### Creating a Paragraph Node

**Pydantic Approach:**
```python
# LLM forced to output this exact JSON structure
{
    "id": "para_001",
    "type": "paragraph",
    "mainText": "The Diels-Alder reaction...",
    "summary": "DA reaction overview",
    "belongTo": "section_intro",
    "supporting_chunks": [],
    "relationships": []
}

# Validated by Pydantic
chunk = DocumentChunk.model_validate(json_data)
```

**OWL+SHACL Approach:**
```python
# Agent writes code (not hardcoded!)
para_uri = URIRef("http://example.org/doc/para_001")
g.add((para_uri, RDF.type, DOC.Paragraph))
g.add((para_uri, DOC.hasMainText, Literal("The Diels-Alder reaction...")))
g.add((para_uri, DOC.belongsTo, section_intro_uri))

# Store content behind handle (RLM-strict)
content_ref = blob_store.store("The Diels-Alder reaction...", "paragraph")
g.add((para_uri, DOC.hasContentRef, Literal(content_ref.ref_id)))

# Validated by SHACL
conforms, _, _ = validate(g, shapes, ontology)
# → If fails: Agent sees violation message, repairs
```

### Handling Invalid Structure

**Pydantic:**
```python
# Invalid: missing required field
{
    "id": "para_001",
    "type": "paragraph"
    # Missing: mainText (required)
}

# Result: ValidationError, no recovery
try:
    chunk = DocumentChunk.model_validate(data)
except ValidationError as e:
    # Failure! Have to retry whole LLM call
    print(e.errors())
```

**OWL+SHACL:**
```python
# Agent proposes incomplete graph
g.add((para_uri, RDF.type, DOC.Paragraph))
# Missing: hasMainText property

# SHACL validation
conforms, results, _ = validate(g, shapes, ontology)
# → conforms = False

# Agent sees violation
violations = parse_violations(results)
# → [{'focus_node': 'para_001',
#     'path': 'doc:hasMainText',
#     'message': 'Paragraphs must have non-empty mainText'}]

# Agent repairs
repair_code = """
# Extract text from ContentRef
text = blob_store.retrieve(para_content_ref)
g.add((para_uri, DOC.hasMainText, Literal(text)))
"""

# Re-validate → Success!
```

---

## Why OWL+SHACL for RLM-Based KAG?

### 1. Agentic Reasoning

**Pydantic forces structure, OWL+SHACL enables reasoning:**

```python
# Pydantic: LLM told "output this exact JSON"
# → No reasoning, just template filling

# OWL+SHACL: Agent decides structure
reasoning = """
I see sub_title tags on pages 2, 3, 5, 7.
These mark section boundaries.
Text tags between sub_titles belong to those sections.
I'll create Section nodes and link Paragraphs via belongsTo.
SHACL requires at least one paragraph per section, so I'll verify.
"""
```

### 2. Learning and Improvement

**Pydantic is static, OWL+SHACL accumulates strategies:**

```python
# L2 Memory: Repair Operators (learned from failures)
repair_operators = {
    "orphan_paragraph": {
        "signature": "doc:belongsTo minCount violation",
        "action": "Link to section on same page",
        "success_count": 12,
        "applicable_to": ["research_paper", "technical_report"]
    },
    "empty_section": {
        "signature": "inversePath doc:belongsTo minCount violation",
        "action": "Merge with previous section or split paragraphs",
        "success_count": 8
    }
}

# Next time agent sees similar violation → apply learned operator!
```

### 3. Domain Flexibility

**Pydantic hardcodes schema, OWL+SHACL is extensible:**

```python
# Chemistry paper needs:
doc:hasChemicalFormula a owl:DatatypeProperty .
doc:hasSMILES a owl:DatatypeProperty .

# Medical paper needs:
doc:hasDiagnosisCode a owl:DatatypeProperty .
doc:hasPatientCohort a owl:ObjectProperty .

# Same agents work on both! Just load different ontology.
```

### 4. RLM Compliance

**Pydantic operates on payloads, OWL+SHACL uses handles:**

```python
# Pydantic: Full text in JSON
{
    "mainText": "The Diels-Alder reaction is a [4+2] cycloaddition..."  # 500 chars
}

# OWL+SHACL: Content behind handle
g.add((para_uri, DOC.hasContentRef, Literal("paragraph:abc123...")))  # 23 chars
# Full text in blob store, retrieved on demand
```

### 5. Provenance and Verification

**Pydantic provides no trace, OWL+SHACL has full provenance:**

```turtle
# Every fact links to source
doc:para_001 a doc:Paragraph ;
    doc:hasMainText "The Diels-Alder reaction..." ;
    doc:belongsTo doc:section_intro ;
    doc:hasContentRef "paragraph:abc123..." ;
    prov:wasQuotedFrom doc:page_002 ;  # Provenance!
    prov:wasDerivedFrom [
        a prov:Entity ;
        prov:value "Detection tag: <|ref|>text<|/ref|><|det|>[[66,79,492,198]]<|/det|>" ;
    ] .

# Can trace: Which page? Which detection tag? Which agent action?
```

---

## Migration Path (If Needed)

If you have existing Pydantic schemas from KAG notebooks, you can **convert them to OWL+SHACL**:

### Pydantic → OWL

```python
# Pydantic
class DocumentChunk(BaseModel):
    id: str
    mainText: str
    summary: Optional[str] = None
```

```turtle
# OWL equivalent
doc:DocumentChunk a owl:Class .

doc:hasMainText a owl:DatatypeProperty ;
    rdfs:domain doc:DocumentChunk ;
    rdfs:range xsd:string .

doc:hasSummary a owl:DatatypeProperty ;
    rdfs:domain doc:DocumentChunk ;
    rdfs:range xsd:string .
```

### Pydantic Validators → SHACL

```python
# Pydantic
class DocumentChunk(BaseModel):
    id: constr(pattern=r"^chunk_[0-9]+$")
    mainText: str = Field(min_length=1)
    belongTo: str  # Required
```

```turtle
# SHACL equivalent
doc:DocumentChunkShape a sh:NodeShape ;
    sh:targetClass doc:DocumentChunk ;

    sh:property [
        sh:path doc:id ;
        sh:pattern "^chunk_[0-9]+$" ;
    ] ;

    sh:property [
        sh:path doc:hasMainText ;
        sh:minCount 1 ;
        sh:minLength 1 ;
    ] ;

    sh:property [
        sh:path doc:belongsTo ;
        sh:minCount 1 ;
    ] .
```

---

## Summary

| Aspect | Pydantic (Old KAG) | OWL+SHACL (RLM KAG) |
|--------|-------------------|-------------------|
| **Philosophy** | Force LLM into schema | Let agent reason, validate result |
| **Structure Definition** | Python classes | OWL ontology (TTL) |
| **Validation** | Pydantic validators | SHACL shapes |
| **Enforcement** | Structured output API | Propose→Verify→Repair loop |
| **Error Handling** | Fail and retry | Self-repair with learning |
| **Learning** | None | Accumulates repair operators |
| **Flexibility** | Fixed schema | Extensible ontology |
| **Domain Scope** | One schema per domain | Same agents, different ontologies |
| **RLM Compliance** | ❌ Payload-based | ✅ Handle-based |
| **Provenance** | ❌ None | ✅ Full PROV-O chains |
| **Standards** | Python-specific | W3C standards (OWL, SHACL, RDF) |
| **Complexity** | Simple | Moderate |
| **Speed** | Fast (single call) | Slower (iterate) |
| **Best For** | Fixed workflows | Agentic systems |

## Recommendation

**Use OWL+SHACL for RLM-based KAG because:**

1. ✅ Truly agentic (agent reasons, not forced)
2. ✅ Learnable (strategies accumulate)
3. ✅ Domain-agnostic (same agents, different ontologies)
4. ✅ Self-repairing (SHACL violations → agent fixes)
5. ✅ RLM-compliant (handles, bounded access)
6. ✅ Standards-based (interoperable with semantic web tools)
7. ✅ Provenance-aware (full chains to source)

The upfront complexity of defining OWL ontologies and SHACL shapes is offset by:
- **Reusability** across document types
- **Learning** that improves over time
- **Flexibility** to extend without rewriting prompts
- **Verifiability** of all claims via provenance

**Next step:** Define the document ontology and SHACL shapes for the KAG experiment!
