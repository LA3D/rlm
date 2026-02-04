"""L1 Schema Constraints - Domain/range, disjointness, property characteristics.

Deterministic schema facts that improve correctness without relying on
emergent behavior. Can be auto-derived or curated.
"""

from rdflib import Graph, RDF, RDFS, OWL

def extract(g:Graph) -> dict:
    "Extract domain/range constraints from ontology."
    dr = []
    for p in g.subjects(RDFS.domain, None):
        doms = list(g.objects(p, RDFS.domain))
        rngs = list(g.objects(p, RDFS.range))
        if doms and rngs:
            dr.append((str(p).split('/')[-1], str(doms[0]).split('/')[-1], str(rngs[0]).split('/')[-1]))

    disj = [(str(a).split('/')[-1], str(b).split('/')[-1])
            for a,_,b in g.triples((None, OWL.disjointWith, None))]

    func = [str(p).split('/')[-1] for p in g.subjects(RDF.type, OWL.FunctionalProperty)]

    return {'domain_range': dr, 'disjoint': disj, 'functional': func}

def pack(g:Graph, budget:int=1000) -> str:
    "Pack constraints as bullet list."
    c = extract(g)
    lines = ['**Schema Constraints**:']
    for p,d,r in c['domain_range'][:15]:
        lines.append(f"- `{p}`: {d} → {r}")
    if c['disjoint']:
        lines.append(f"**Disjoint**: {', '.join(f'{a}⊥{b}' for a,b in c['disjoint'][:5])}")
    if c['functional']:
        lines.append(f"**Functional**: {', '.join(c['functional'][:5])}")
    return '\n'.join(lines)[:budget]
