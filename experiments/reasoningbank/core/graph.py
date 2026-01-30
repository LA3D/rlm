"""RDFLib wrappers exposed as RLM tools.

All tools return bounded results or handles (Ref), never full graphs.
Module globals (_store, _graphs) are set by the runner before execution.
"""

from rdflib import Graph, RDF, RDFS, OWL, URIRef
from .blob import Ref, Store

_store: Store = None  # Set by runner
_graphs: dict[str, Graph] = {}   # key -> Graph

def g_load(path:str) -> Ref:
    "Load graph from `path`, return handle."
    g = Graph().parse(path)
    ref = _store.put(path, 'graph')
    _graphs[ref.key] = g
    return ref

def g_stats(ref:Ref) -> dict:
    "Return `{triples, classes, props, ns}`."
    g = _graphs[ref.key]
    return {
        'triples': len(g),
        'classes': len(list(g.subjects(RDF.type, OWL.Class))),
        'props': len(list(g.subjects(RDF.type, OWL.ObjectProperty))),
        'ns': [str(n) for _,n in g.namespaces()][:10],
    }

def g_query(ref:Ref, q:str, limit:int=100) -> Ref:
    "Execute SPARQL `q`, return results as handle."
    g = _graphs[ref.key]
    res = list(g.query(q))[:limit]
    txt = '\n'.join(str(row) for row in res)
    return _store.put(txt, 'results')

def g_sample(ref:Ref, n:int=10) -> Ref:
    "Return `n` sample triples as handle. Use ctx_peek to inspect."
    g = _graphs[ref.key]
    triples = list(g)[:n]
    content = '\n'.join(f"{s} {p} {o}" for s,p,o in triples)
    return _store.put(content, 'sample')

def g_classes(ref:Ref, limit:int=50) -> Ref:
    "Return class URIs as handle. Use ctx_peek to inspect."
    g = _graphs[ref.key]
    classes = [str(c) for c in list(g.subjects(RDF.type, OWL.Class))[:limit]]
    content = '\n'.join(classes)
    return _store.put(content, 'classes')

def g_props(ref:Ref, limit:int=50) -> Ref:
    "Return property URIs as handle. Use ctx_peek to inspect."
    g = _graphs[ref.key]
    props = list(g.subjects(RDF.type, OWL.ObjectProperty))
    props += list(g.subjects(RDF.type, OWL.DatatypeProperty))
    content = '\n'.join([str(p) for p in props[:limit]])
    return _store.put(content, 'properties')

def g_describe(ref:Ref, uri:str, limit:int=20) -> Ref:
    "Return triples about `uri` as handle. Use ctx_peek to inspect."
    g = _graphs[ref.key]
    subj = URIRef(uri)
    triples = list(g.triples((subj, None, None)))[:limit]
    content = '\n'.join(f"{p} {o}" for _,p,o in triples)
    return _store.put(content, 'describe')
