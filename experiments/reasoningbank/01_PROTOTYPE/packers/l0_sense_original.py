"""L0 Sense Card - Ontology metadata extraction.

Deterministic, compact, 100% URI grounded. Tells HOW to read the ontology,
not WHAT is in it (specific classes/properties discovered via tools).
"""

from rdflib import Graph, RDF, RDFS, OWL, Namespace

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

def extract(g:Graph) -> dict:
    "Extract ontology metadata via rdflib."
    # Detect label property
    label_prop = 'rdfs:label'
    if list(g.triples((None, SKOS.prefLabel, None))): label_prop = 'skos:prefLabel'

    # Detect desc property
    desc_prop = 'rdfs:comment'
    if list(g.triples((None, SKOS.definition, None))): desc_prop = 'skos:definition'

    # Detect formalism
    n_restrict = len(list(g.subjects(RDF.type, OWL.Restriction)))
    n_disjoint = len(list(g.triples((None, OWL.disjointWith, None))))
    if n_restrict > 0 or n_disjoint > 0: formalism = 'OWL-DL'
    elif list(g.subjects(RDF.type, OWL.Class)):      formalism = 'OWL-Lite'
    elif list(g.triples((None, RDFS.subClassOf, None))): formalism = 'RDFS'
    else: formalism = 'RDF'

    return {
        'triples': len(g),
        'classes': len(list(g.subjects(RDF.type, OWL.Class))),
        'props': len(list(g.subjects(RDF.type, OWL.ObjectProperty))),
        'label': label_prop,
        'desc': desc_prop,
        'formalism': formalism,
    }

def pack(g:Graph, budget:int=600) -> str:
    "Pack sense card into bounded markdown."
    s = extract(g)
    lines = [
        f"**Size**: {s['triples']} triples, {s['classes']} classes, {s['props']} properties",
        f"**Formalism**: {s['formalism']}",
        f"**Labels**: use `{s['label']}`",
        f"**Descriptions**: use `{s['desc']}`",
    ]
    return '\n'.join(lines)[:budget]
