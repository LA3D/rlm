"""Enhanced L0 Sense Card - Comprehensive metadata extraction.

Handles multiple annotation styles:
- Widoco (DC, DCTerms, VANN, FOAF)
- OGC/GeoSPARQL (Schema.org, SKOS, Profiles)
- OBO Foundry/SIO (CITO, Void subsets, ORCID)
"""

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
from rdflib.namespace import DC, DCTERMS, SKOS, FOAF

# Extended vocabularies
VANN = Namespace("http://purl.org/vocab/vann/")
PAV = Namespace("http://purl.org/pav/")
SCHEMA = Namespace("http://schema.org/")
VOID = Namespace("http://rdfs.org/ns/void#")
CITO = Namespace("http://purl.org/spar/cito/")
PROF = Namespace("http://www.w3.org/ns/dx/prof/")

def extract_metadata(g: Graph) -> dict:
    """Extract comprehensive ontology metadata."""

    # Find ontology URI(s)
    ontologies = list(g.subjects(RDF.type, OWL.Ontology))
    onto = ontologies[0] if ontologies else None

    meta = {
        'uri': None,
        'title': None,
        'description': None,
        'prefix': None,
        'version': None,
        'imports': [],
        'subsets': [],
        'namespaces': {},
        'label_property': None,
        'desc_property': None,
        'formalism': None,
    }

    if not onto:
        return meta

    meta['uri'] = str(onto)

    # Title - try multiple properties
    title = (g.value(onto, DC.title) or
             g.value(onto, DCTERMS.title) or
             g.value(onto, RDFS.label))
    if title:
        meta['title'] = str(title)

    # Description - try multiple properties
    desc = (g.value(onto, DC.description) or
            g.value(onto, DCTERMS.description) or
            g.value(onto, RDFS.comment) or
            g.value(onto, SKOS.scopeNote) or
            g.value(onto, SCHEMA.comment))
    if desc:
        meta['description'] = str(desc)

    # Prefix - VANN preferred
    prefix = g.value(onto, VANN.preferredNamespacePrefix)
    if prefix:
        meta['prefix'] = str(prefix)

    # Version
    version = g.value(onto, OWL.versionInfo)
    if version:
        meta['version'] = str(version)

    # Imports
    imports = list(g.objects(onto, OWL.imports))
    meta['imports'] = [str(i) for i in imports]

    # Subsets/modules (OBO/SIO pattern)
    subsets = list(g.objects(onto, VOID.subset))
    meta['subsets'] = [str(s).split('/')[-1].replace('.owl', '').replace('sio-subset-', '')
                       for s in subsets]

    # Namespaces (filter out standard ones)
    standard_prefixes = {'rdf', 'rdfs', 'owl', 'xsd', 'xml'}
    meta['namespaces'] = {
        prefix: str(ns)
        for prefix, ns in g.namespaces()
        if prefix and prefix not in standard_prefixes
    }

    # Detect label property convention
    if list(g.triples((None, SKOS.prefLabel, None))):
        meta['label_property'] = 'skos:prefLabel'
    else:
        meta['label_property'] = 'rdfs:label'

    # Detect description property convention
    if list(g.triples((None, SKOS.definition, None))):
        meta['desc_property'] = 'skos:definition'
    elif list(g.triples((None, DCTERMS.description, None))):
        meta['desc_property'] = 'dcterms:description'
    else:
        meta['desc_property'] = 'rdfs:comment'

    # Detect formalism level
    n_restrict = len(list(g.subjects(RDF.type, OWL.Restriction)))
    n_disjoint = len(list(g.triples((None, OWL.disjointWith, None))))
    if n_restrict > 0 or n_disjoint > 0:
        meta['formalism'] = 'OWL-DL'
    elif list(g.subjects(RDF.type, OWL.Class)):
        meta['formalism'] = 'OWL-Lite'
    elif list(g.triples((None, RDFS.subClassOf, None))):
        meta['formalism'] = 'RDFS'
    else:
        meta['formalism'] = 'RDF'

    return meta


def pack(g: Graph, budget: int = 600) -> str:
    """Pack metadata into compact sense card.

    Priority order:
    1. Title (if available)
    2. Description excerpt (if available)
    3. Size stats (always)
    4. Namespaces (key ones)
    5. Imports/subsets (if present)
    6. Label/description conventions (always)
    7. Formalism (if space permits)
    """
    meta = extract_metadata(g)
    lines = []

    # Title (optional, if present)
    if meta['title']:
        lines.append(f"**{meta['title']}**")

    # Description excerpt (optional, first 150 chars)
    if meta['description']:
        desc = meta['description']
        if len(desc) > 150:
            desc = desc[:150] + "..."
        lines.append(desc)

    # Size stats (always)
    n_triples = len(g)
    n_classes = len(list(g.subjects(RDF.type, OWL.Class)))
    n_props = len(list(g.subjects(RDF.type, OWL.ObjectProperty)))
    n_props += len(list(g.subjects(RDF.type, OWL.DatatypeProperty)))

    stats = [f"{n_triples} triples", f"{n_classes} classes", f"{n_props} properties"]
    if meta['version']:
        stats.append(f"v{meta['version']}")
    lines.append(f"**Size**: {', '.join(stats)}")

    # Key namespaces (prioritize domain-specific)
    if meta['namespaces']:
        # Show up to 5 most relevant (non-standard) prefixes
        ns_names = [p for p in meta['namespaces'].keys()
                    if p not in ['dc', 'dcterms', 'foaf', 'skos', 'prov']][:5]
        if ns_names:
            lines.append(f"**Namespaces**: {', '.join(f'`{p}`' for p in ns_names)}")

    # Imports (if present)
    if meta['imports']:
        import_names = [i.split('/')[-1].split('#')[0] for i in meta['imports']]
        # Shorten if too many
        if len(import_names) > 6:
            shown = ', '.join(import_names[:5])
            lines.append(f"**Imports**: {shown}, +{len(import_names)-5} more")
        else:
            lines.append(f"**Imports**: {', '.join(import_names)}")

    # Subsets (if present, OBO/SIO pattern)
    if meta['subsets']:
        if len(meta['subsets']) > 8:
            shown = ', '.join(meta['subsets'][:7])
            lines.append(f"**Modules**: {shown}, +{len(meta['subsets'])-7} more")
        else:
            lines.append(f"**Modules**: {', '.join(meta['subsets'])}")

    # Label/description conventions (always)
    lines.append(f"**Labels**: use `{meta['label_property']}`")
    if meta['desc_property']:
        lines.append(f"**Descriptions**: use `{meta['desc_property']}`")

    # Formalism (if space permits)
    current = '\\n'.join(lines)
    if len(current) + 30 < budget and meta['formalism']:
        lines.append(f"**Formalism**: {meta['formalism']}")

    return '\\n'.join(lines)[:budget]
