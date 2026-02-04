"""RDFLib wrappers exposed as RLM tools.

All tools return bounded results or serializable handles (dicts), never full graphs.
Module globals (_store, _graphs) are set by the runner before execution.

Handle dict format: {'key': str, 'dtype': str, 'size': int, 'preview': str}
Use ctx_peek(result['key']) to inspect handle contents.
"""

from rdflib import Graph, RDF, RDFS, OWL, URIRef
from .blob import Ref, Store

_store: Store = None  # Set by runner
_graphs: dict[str, Graph] = {}   # key -> Graph

def _ref_to_handle(ref: Ref) -> dict:
    "Convert Ref to serializable handle dict."
    return {'key': ref.key, 'dtype': ref.dtype, 'size': ref.sz, 'preview': ref.prev}

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

def g_query(ref:Ref, q:str, limit:int=100) -> dict:
    "Execute SPARQL `q`, return handle dict. Use ctx_peek(result['key']) to inspect."
    g = _graphs[ref.key]
    res = list(g.query(q))[:limit]
    txt = '\n'.join(str(row) for row in res)
    return _ref_to_handle(_store.put(txt, 'results'))

def g_sample(ref:Ref, n:int=10) -> dict:
    "Return `n` sample triples as handle dict. Use ctx_peek(result['key']) to inspect."
    g = _graphs[ref.key]
    triples = list(g)[:n]
    content = '\n'.join(f"{s} {p} {o}" for s,p,o in triples)
    return _ref_to_handle(_store.put(content, 'sample'))

def g_classes(ref:Ref, limit:int=50) -> dict:
    "Return class URIs as handle dict. Use ctx_peek(result['key']) to inspect."
    g = _graphs[ref.key]
    classes = [str(c) for c in list(g.subjects(RDF.type, OWL.Class))[:limit]]
    content = '\n'.join(classes)
    return _ref_to_handle(_store.put(content, 'classes'))

def g_classes_list(ref:Ref, limit:int=50) -> list[str]:
    "Return class URIs as a list (can be sliced, iterated directly)."
    g = _graphs[ref.key]
    return [str(c) for c in list(g.subjects(RDF.type, OWL.Class))[:limit]]

def g_props(ref:Ref, limit:int=50) -> dict:
    "Return property URIs as handle dict. Use ctx_peek(result['key']) to inspect."
    g = _graphs[ref.key]
    props = list(g.subjects(RDF.type, OWL.ObjectProperty))
    props += list(g.subjects(RDF.type, OWL.DatatypeProperty))
    content = '\n'.join([str(p) for p in props[:limit]])
    return _ref_to_handle(_store.put(content, 'properties'))

def g_props_list(ref:Ref, limit:int=50) -> list[str]:
    "Return property URIs as a list (can be sliced, iterated directly)."
    g = _graphs[ref.key]
    props = list(g.subjects(RDF.type, OWL.ObjectProperty))
    props += list(g.subjects(RDF.type, OWL.DatatypeProperty))
    return [str(p) for p in props[:limit]]

def g_describe(ref:Ref, uri:str, limit:int=20) -> dict:
    "Return triples about `uri` as handle dict. Use ctx_peek(result['key']) to inspect."
    g = _graphs[ref.key]
    subj = URIRef(uri)
    triples = list(g.triples((subj, None, None)))[:limit]
    content = '\n'.join(f"{p} {o}" for _,p,o in triples)
    return _ref_to_handle(_store.put(content, 'describe'))
