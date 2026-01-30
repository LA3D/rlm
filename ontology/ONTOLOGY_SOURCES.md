# Ontology Sources

This document tracks ontology sources for discovered SPARQL endpoints.

## Downloaded Ontologies

**Note**: Ontologies are stored **compressed (.gz)** in git to save space. Uncompress before use:
```bash
gunzip -k ontology/rheadb/rhea.rdf.gz  # -k keeps original
```

Or use rdflib which can read compressed files directly:
```python
from rdflib import Graph
g = Graph()
g.parse('ontology/rheadb/rhea.rdf.gz', format='xml')
```

### Rhea (Rhea-db)
- **Status**: Downloaded (compressed)
- **File**: `rheadb/rhea.rdf.gz` (8.3 MB compressed, 196 MB uncompressed)
- **Source**: https://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz
- **Format**: RDF/XML
- **Description**: Rhea is a comprehensive resource of expert-curated biochemical reactions
- **Examples in SHACL**: 123

### neXtProt
- **Status**: Downloaded (compressed)
- **Files**: `nextprot/schema.ttl.gz` (27 KB), `nextprot/terminology.ttl.gz` (5 MB)
- **Source**: https://rdfportal.org/download/nextprot/20240826/
- **Format**: Turtle (compressed)
- **Description**: neXtProt schema and terminology (data from August 2024, service discontinued)
- **Examples in SHACL**: 197
- **Note**: neXtProt reached end-of-life in 2024; schema files downloaded from RDFPortal archive

### OrthoDB
- **Status**: Downloaded
- **File**: `orthodb/orth.owl` (88 KB)
- **Source**: http://purl.org/net/orth (redirects to GitHub)
- **Format**: OWL
- **Description**: Orthology Ontology (ORTH) v2.0 for describing orthology information
- **Examples in SHACL**: 22

### OMA Browser
- **Status**: Downloaded
- **Files**: `oma/oo.owl` (22 KB), `oma/orthOntology_v3.ttl` (50 KB), `oma/lscr.ttl` (11 KB)
- **Source**: https://github.com/qfo/OrthologyOntology
- **Format**: OWL and Turtle
- **Description**: Quest for Orthologs (QfO) ontologies - OO (Orthology Ontology) and LSCR (Life-Sciences Cross-Reference)
- **Examples in SHACL**: 16

### Wikidata
- **Status**: Downloaded
- **File**: `wikidata/wikibase.owl` (17 KB)
- **Source**: https://github.com/wikimedia/mediawiki-extensions-Wikibase/blob/master/docs/ontology.owl
- **Format**: OWL
- **Description**: Wikibase system ontology (schema for Wikidata RDF exports)
- **Examples in SHACL**: 6
- **Note**: This is the Wikibase ontology, not the full Wikidata dataset

### GlyConnect
- **Status**: Downloaded
- **File**: `glyconnect/glycocoo.owl` (29 KB)
- **Source**: https://github.com/glycoinfo/GlycoCoO/blob/master/ontology/glycocoo.owl
- **Format**: OWL
- **Description**: Glycoconjugate Ontology (GlycoCoO) for glycoprotein/glycolipid data
- **Examples in SHACL**: 5

## Existing Ontologies

### UniProt
- **Status**: Present in repository
- **Files**: `uniprot/core.owl`, `uniprot/core.ttl`
- **Examples in SHACL**: 40

### WikiPathways
- **Status**: Present in repository
- **Examples in SHACL**: 4

### PubChem
- **Status**: Present in repository
- **Files**: `pubchem/pubchem_shacl.ttl`, `pubchem/pubchem_void.ttl`

## Endpoints Without Downloadable Ontologies

These endpoints provide SPARQL access but do not have standalone ontology files available:

### IDSM (Integrated Database of Small Molecules)
- **Status**: Uses existing ontologies (ChEBI, ChEMBL, Wikidata)
- **Endpoints**:
  - https://idsm.elixir-czech.cz/sparql/endpoint/chebi (5 examples)
  - https://idsm.elixir-czech.cz/sparql/endpoint/idsm (4 examples)
  - https://idsm.elixir-czech.cz/sparql/endpoint/cco (2 examples)
  - https://idsm.elixir-czech.cz/sparql/endpoint/wikidata (1 example)
- **Description**: IDSM ChemWebRDF integrates PubChem, ChEMBL, and ChEBI datasets
- **Note**: Uses ChEBI ontology (OWL) and ChEMBL Core Ontology (CCO); download from source databases

### Bgee
- **Status**: Downloaded (GENEX + UBERON ontologies)
- **Files**:
  - `bgee/genex.ttl` (89 KB, 702 triples) - Gene expression schema
  - `uberon/uberon.owl.gz` (5.7 MB compressed, 1.18M triples) - Multi-species anatomy
- **Sources**:
  - GENEX: https://biosoda.expasy.org/genex/ontology.ttl
  - UBERON: http://purl.obolibrary.org/obo/uberon.owl
- **Format**: Turtle (GENEX), OWL compressed (UBERON)
- **Description**: Bgee uses GENEX for gene expression representation and UBERON for anatomical entities and developmental stages
- **Endpoint**: https://www.bgee.org/sparql/
- **Examples in SHACL**: 33
- **Note**: Also uses Gene Ontology (GO) for cell types and LSCR for cross-references (available in oma/)

### DisGeNET
- **Status**: Requires registration
- **Endpoint**: https://rdf.disgenet.org/sparql
- **Examples in SHACL**: 4
- **Note**: DisGeNET requires registration for downloads

### Other Endpoints
- **String-db** (1 example): https://sparql.string-db.org/sparql
- **CORDIS** (1 example): https://cordis.europa.eu/datalab/sparql
- **Bioregistry** (1 example): https://bioregistry.io/sparql
- **Identifiers.org** (1 example): https://sparql.api.identifiers.org/sparql
- **Allie** (2 examples): https://data.allie.dbcls.jp/sparql
- **Nibb** (1 example): http://sparql.nibb.ac.jp/sparql
- **Qlever/Wikidata** (14 examples): https://qlever.dev/api/wikidata (covered by wikidata/wikibase.owl)

## Download Sources (Reference)

For ontologies that can be downloaded:

| Endpoint | Source URL | Size | Format |
|----------|-----------|------|--------|
| Rhea | https://ftp.expasy.org/databases/rhea/rdf/rhea.rdf.gz | 8.3 MB (196 MB uncompressed) | RDF/XML |
| neXtProt schema | https://rdfportal.org/download/nextprot/20240826/schema.ttl.gz | 27 KB | Turtle |
| neXtProt terminology | https://rdfportal.org/download/nextprot/20240826/terminology.ttl.gz | 5 MB | Turtle |
| OrthoDB (ORTH) | http://purl.org/net/orth | 88 KB | OWL |
| OMA (OO) | https://raw.githubusercontent.com/qfo/OrthologyOntology/master/oo.owl | 22 KB | OWL |
| OMA (LSCR) | https://raw.githubusercontent.com/qfo/OrthologyOntology/master/lscr.ttl | 11 KB | Turtle |
| OMA (Orth v3) | https://raw.githubusercontent.com/qfo/OrthologyOntology/master/orthOntology_v3_a.ttl | 50 KB | Turtle |
| Wikibase | https://raw.githubusercontent.com/wikimedia/mediawiki-extensions-Wikibase/master/docs/ontology.owl | 17 KB | OWL |
| GlycoCoO | https://raw.githubusercontent.com/glycoinfo/GlycoCoO/master/ontology/glycocoo.owl | 29 KB | OWL |
| Bgee (GENEX) | https://biosoda.expasy.org/genex/ontology.ttl | 89 KB | Turtle |
| UBERON | http://purl.obolibrary.org/obo/uberon.owl | 5.7 MB (93 MB uncompressed) | OWL |

## Usage

Use the `download_ontologies.py` script to download additional ontologies:

```bash
# Dry run to see what would be downloaded
python experiments/reasoningbank/tools/download_ontologies.py --dry-run --top 10

# Download ontologies for top 5 endpoints
python experiments/reasoningbank/tools/download_ontologies.py --top 5
```

## Service Description Discovery

For endpoints without downloadable ontologies, use the service description tools:

```python
from experiments.reasoningbank.tools.endpoint_tools import EndpointTools

tools = EndpointTools()

# Fetch service description
sd_ref = tools.service_desc('https://sparql.nextprot.org/sparql')

# Explore schema
stats = tools.service_desc_stats(sd_ref.key)
graphs = tools.service_desc_graphs(sd_ref.key)
features = tools.service_desc_features(sd_ref.key)
```

This allows agentic discovery without requiring full ontology downloads.
