"""Extract Widoco-style metadata from PROV ontology."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
from rdflib.namespace import DC, DCTERMS, SKOS, FOAF

# Widoco metadata vocabularies
VANN = Namespace("http://purl.org/vocab/vann/")
PAV = Namespace("http://purl.org/pav/")
SCHEMA = Namespace("http://schema.org/")

def extract_widoco_metadata(g: Graph) -> dict:
    """Extract Widoco-style ontology metadata."""

    # Find ontology URI(s)
    ontologies = list(g.subjects(RDF.type, OWL.Ontology))
    onto = ontologies[0] if ontologies else None

    meta = {}

    if onto:
        # Identification
        meta['uri'] = str(onto)
        meta['title'] = str(g.value(onto, DC.title) or g.value(onto, DCTERMS.title) or "")
        meta['description'] = str(g.value(onto, DC.description) or g.value(onto, DCTERMS.description) or "")
        meta['prefix'] = str(g.value(onto, VANN.preferredNamespacePrefix) or "")

        # Versioning
        meta['version'] = str(g.value(onto, OWL.versionInfo) or "")
        meta['version_iri'] = str(g.value(onto, OWL.versionIRI) or "")

        # Provenance
        creators = list(g.objects(onto, DC.creator)) + list(g.objects(onto, DCTERMS.creator))
        meta['creators'] = [str(c) for c in creators]

        contributors = list(g.objects(onto, DC.contributor)) + list(g.objects(onto, DCTERMS.contributor))
        meta['contributors'] = [str(c) for c in contributors]

        # Rights
        meta['license'] = str(g.value(onto, DC.rights) or g.value(onto, DCTERMS.license) or "")

        # Technical
        imports = list(g.objects(onto, OWL.imports))
        meta['imports'] = [str(i) for i in imports]

        # Modified dates
        meta['created'] = str(g.value(onto, DCTERMS.created) or g.value(onto, PAV.createdOn) or "")
        meta['modified'] = str(g.value(onto, DCTERMS.modified) or g.value(onto, PAV.lastUpdateOn) or "")

    # Namespaces
    meta['namespaces'] = {prefix: str(ns) for prefix, ns in g.namespaces()}

    return meta

# Load PROV
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

meta = extract_widoco_metadata(g)

print("=" * 70)
print("WIDOCO-STYLE METADATA EXTRACTION")
print("=" * 70)
print()
print("IDENTIFICATION:")
print(f"  URI: {meta['uri']}")
print(f"  Title: {meta['title']}")
print(f"  Prefix: {meta['prefix']}")
print()
print("DESCRIPTION:")
print(f"  {meta['description'][:200]}..." if len(meta['description']) > 200 else f"  {meta['description']}")
print()
print("VERSIONING:")
print(f"  Version: {meta['version']}")
print(f"  Version IRI: {meta['version_iri']}")
print()
print("PROVENANCE:")
print(f"  Creators: {', '.join(meta['creators'][:3]) if meta['creators'] else 'None'}")
print(f"  Contributors: {', '.join(meta['contributors'][:3]) if meta['contributors'] else 'None'}")
print()
print("RIGHTS:")
print(f"  License: {meta['license']}")
print()
print("TECHNICAL:")
print(f"  Imports: {', '.join(meta['imports']) if meta['imports'] else 'None'}")
print()
print("NAMESPACES:")
for prefix, ns in list(meta['namespaces'].items())[:8]:
    print(f"  {prefix}: {ns}")
if len(meta['namespaces']) > 8:
    print(f"  ... and {len(meta['namespaces']) - 8} more")
print()
print("=" * 70)

# Now format as a compact sense card
def format_sense_card_with_metadata(meta: dict, g: Graph, budget: int = 600) -> str:
    """Format Widoco metadata as compact sense card."""
    from rdflib import RDF, OWL

    lines = []

    # Core identity
    if meta['title']:
        lines.append(f"**{meta['title']}**")
    if meta['description']:
        lines.append(meta['description'][:150] + "..." if len(meta['description']) > 150 else meta['description'])

    # Technical specs
    stats = []
    stats.append(f"{len(g)} triples")
    stats.append(f"{len(list(g.subjects(RDF.type, OWL.Class)))} classes")
    stats.append(f"{len(list(g.subjects(RDF.type, OWL.ObjectProperty)))} properties")
    if meta['version']:
        stats.append(f"v{meta['version']}")
    lines.append(f"**Size**: {', '.join(stats)}")

    # Key namespaces (excluding standard ones)
    key_ns = {p: n for p, n in meta['namespaces'].items()
              if p not in ['rdf', 'rdfs', 'owl', 'xsd', 'xml']}
    if key_ns:
        ns_list = ', '.join([f"`{p}`" for p in list(key_ns.keys())[:5]])
        lines.append(f"**Namespaces**: {ns_list}")

    # Imports
    if meta['imports']:
        import_names = [i.split('/')[-1].split('#')[0] for i in meta['imports']]
        lines.append(f"**Imports**: {', '.join(import_names)}")

    # Query conventions
    lines.append(f"**Labels**: use `rdfs:label`")

    return '\n'.join(lines)[:budget]

sense_card = format_sense_card_with_metadata(meta, g, budget=600)
print()
print("=" * 70)
print("ENHANCED L0 SENSE CARD")
print("=" * 70)
print(sense_card)
print()
print(f"Length: {len(sense_card)} chars")
print("=" * 70)
