# SPAR Ontologies for KAG Document Understanding

This directory contains W3C-standard ontologies from SPAR (Semantic Publishing and Referencing Ontologies) used in the KAG experiment.

## Required Ontologies

### Core Document Understanding

#### 1. DoCO (Document Components Ontology) ⭐ ESSENTIAL
- **URL:** https://sparontologies.github.io/doco/current/doco.ttl
- **Prefix:** `doco:`
- **Namespace:** `http://purl.org/spar/doco/`
- **Purpose:** Defines document structural components
- **Classes:** Section, Paragraph, Figure, Table, Formula, Caption, SectionTitle, etc.
- **Imports:** DEO, PO
- **Used for:** Core document structure (mapping DeepSeek OCR to DoCO classes)

#### 2. DEO (Discourse Elements Ontology) ⭐ ESSENTIAL
- **URL:** https://sparontologies.github.io/deo/current/deo.ttl
- **Prefix:** `deo:`
- **Namespace:** `http://purl.org/spar/deo/`
- **Purpose:** Defines major rhetorical elements (Introduction, Results, Discussion, etc.)
- **Classes:** Introduction, Methods, Results, Discussion, Conclusion, Abstract, etc.
- **Imports:** PO
- **Used for:** Rhetorical structure (IMRaD format in research papers)
- **Note:** Imported by DoCO

#### 3. PO (Pattern Ontology) ⭐ ESSENTIAL
- **URL:** http://www.essepuntato.it/2008/12/pattern (need to find actual .ttl file)
- **Prefix:** `po:`
- **Namespace:** `http://www.essepuntato.it/2008/12/pattern#`
- **Purpose:** Defines structural patterns (containment, sequences, etc.)
- **Properties:** `po:contains`, `po:isContainedBy`, `po:containsAsHeader`
- **Used for:** Hierarchical relationships (Section contains Paragraphs)
- **Note:** Imported by DoCO and DEO

#### 4. FaBiO (FRBR-aligned Bibliographic Ontology) ⭐ RECOMMENDED
- **URL:** https://sparontologies.github.io/fabio/current/fabio.ttl
- **Prefix:** `fabio:`
- **Namespace:** `http://purl.org/spar/fabio/`
- **Purpose:** Defines document types and bibliographic entities
- **Classes:** ResearchPaper, JournalArticle, TechnicalReport, Thesis, ConferencePaper, etc.
- **Used for:** Document type classification (fabio:ResearchPaper instead of generic doco:Document)

### Optional (Useful)

#### 5. Literal (Literal Reification Ontology) 🔸 OPTIONAL
- **URL:** https://sparontologies.github.io/literal/current/literal.ttl
- **Prefix:** `litre:`
- **Namespace:** `http://www.essepuntato.it/2010/06/literalreification/`
- **Purpose:** Reifies literal values as first-class objects
- **Classes:** Literal
- **Properties:** `hasLiteral`, `hasLiteralValue`
- **Used for:** Attaching metadata to text (OCR confidence, corrections, versions)
- **Note:** Use if we need assertions about text itself

#### 6. C4O (Citation Context Characterization Ontology) 🔸 OPTIONAL
- **URL:** https://sparontologies.github.io/c4o/current/c4o.ttl
- **Prefix:** `c4o:`
- **Namespace:** `http://purl.org/spar/c4o/`
- **Purpose:** Citation counting and context
- **Used for:** If we need to track citations in papers
- **Note:** Not needed for basic document structure

### External (Non-SPAR)

#### 7. PROV-O (Provenance Ontology) ⭐ ESSENTIAL
- **URL:** https://www.w3.org/ns/prov.ttl
- **Prefix:** `prov:`
- **Namespace:** `http://www.w3.org/ns/prov#`
- **Purpose:** W3C standard for provenance
- **Properties:** `wasQuotedFrom`, `wasDerivedFrom`, `wasGeneratedBy`
- **Used for:** Tracking which page/detection tag each node came from
- **Note:** W3C standard, not SPAR

## Download Instructions

```bash
cd ../rlm/ontology

# Essential SPAR ontologies
curl -o doco.ttl https://sparontologies.github.io/doco/current/doco.ttl
curl -o deo.ttl https://sparontologies.github.io/deo/current/deo.ttl
curl -o fabio.ttl https://sparontologies.github.io/fabio/current/fabio.ttl

# Pattern Ontology (check URL)
# curl -o po.ttl http://www.essepuntato.it/2008/12/pattern

# Optional
curl -o literal.ttl https://sparontologies.github.io/literal/current/literal.ttl

# External (W3C)
curl -o prov-o.ttl https://www.w3.org/ns/prov.ttl
```

## Usage in KAG Experiment

### Ontology Stack

```
KAG Document Graph
├── PROV-O (provenance: wasQuotedFrom, wasDerivedFrom)
├── FaBiO (document types: ResearchPaper, TechnicalReport)
├── DoCO (structure: Section, Paragraph, Figure, Table)
│   ├── DEO (rhetoric: Introduction, Results, Methods)
│   └── PO (patterns: contains, isContainedBy)
└── Literal (optional: text reification)
```

### Agent Usage

Agents will:
1. **Load ontologies** from this directory
2. **Map DeepSeek OCR** detections to DoCO/DEO classes
3. **Build RDF graph** using these classes and properties
4. **Validate with SHACL** against these ontologies
5. **Export** as valid semantic web data

### Example Mapping

| DeepSeek Detection | SPAR Ontology Classes |
|-------------------|-----------------------|
| `title` | `doco:Title` |
| `sub_title` | `doco:Section` + `doco:SectionTitle` |
| `text` | `doco:Paragraph` |
| `equation` | `doco:Formula` |
| `image` | `doco:Figure` |
| `table` | `doco:Table` |
| `figure_title` | `doco:Caption` |

### Document Type Classification

```turtle
# Use FaBiO for document types
ex:chemrxiv_001 a fabio:ResearchPaper ;
    doco:hasBodyMatter ex:body .

ex:body a doco:BodyMatter ;
    po:contains ex:intro, ex:results, ex:methods .

# Use DEO for rhetorical structure
ex:intro a deo:Introduction ;
    po:contains ex:para_001 .

ex:results a deo:Results ;
    po:contains ex:para_010, ex:fig_001 .
```

## Dependencies

### Import Chain

```
DoCO
├── imports DEO
│   └── imports PO
└── imports PO

FaBiO
└── imports FRBR

KAG Extensions
├── imports DoCO
├── imports FaBiO
├── imports PROV-O
└── imports Literal (optional)
```

### Required for Agents

Agents need access to:
1. **Class definitions** - What is a Section? What is a Paragraph?
2. **Property definitions** - What does po:contains mean?
3. **Hierarchies** - Which classes are subclasses of DocumentComponent?
4. **Constraints** - From SHACL shapes (in experiments/KAG/ontology/)

## File Organization

```
../rlm/ontology/
├── README.md           # This file
├── doco.ttl            # Document Components
├── deo.ttl             # Discourse Elements
├── po.ttl              # Pattern Ontology
├── fabio.ttl           # Bibliographic types
├── literal.ttl         # Text reification (optional)
└── prov-o.ttl          # Provenance (W3C)
```

## References

- **SPAR Ontologies:** https://www.sparontologies.net/
- **DoCO Spec:** https://sparontologies.github.io/doco/current/doco.html
- **DEO Spec:** https://sparontologies.github.io/deo/current/deo.html
- **FaBiO Spec:** https://sparontologies.github.io/fabio/current/fabio.html
- **PROV-O Spec:** https://www.w3.org/TR/prov-o/
- **SPAR GitHub:** https://github.com/orgs/SPAROntologies/repositories

## Next Steps

1. Download ontologies to this directory
2. Use in KAG experiment: `experiments/KAG/ontology/document_ontology.ttl` imports these
3. Agents load ontologies to understand classes/properties
4. SHACL validation uses these for reasoning
