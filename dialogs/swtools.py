import json
from SPARQLWrapper import SPARQLWrapper, JSON, XML
from rdflib import Graph

def sparql_query(query:str, # SPARQL Query String
    endpoint:str="https://dbpedia.org/sparql", # Endpoint, dbpedia default for testing 
    max_results:int=100, # Limit the number of results by default
    name:str='res', # Symbol name to store results in namespace
    ns:dict=None): # Target namespace (defaults to globals())
    """Execute SPARQL query, store results in REPL, return summary
    
    Remember to think through the needed prefixes. For example 
    Wikidata queries, include these prefixes for label service:
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wikibase: <http://wikiba.se/ontology#>
    PREFIX bd: <http://www.bigdata.com/rdf#>
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }

    Each service endpoint will require a different set of prefixes. 

    **Understanding Graph Structure:**
        - Run simple queries first to discover what properties exist
        - Properties themselves are entities with labels/descriptions
        - Use `FILTER(STRSTARTS(STR(?property), "namespace"))` to focus on relevant properties

        **Label Resolution:**
        - Labels may be federated (external SERVICE) or local (rdfs:label)
        - If SERVICE fails, fall back to direct label queries
        - Property URIs often map to entity URIs with labels

        **Query Strategy:**
        - Start broad, then filter
        - Use LIMIT for exploration
        - CONSTRUCT gives more control than DESCRIBE
        - Check if endpoint includes metadata (schema.org) that needs filtering

        **Discovering Affordances:**
        - Query an entity's properties to see what questions you can ask
        - Follow property relationships to explore the graph
        - Look for temporal properties (dates, time periods) for historical queries
        - Identify relationship properties (part of, located in, capital of) for traversal

        **Endpoint Differences:**
        - Test label resolution approach per endpoint
        - Check if federated queries work
        - Some endpoints pre-include labels, others require explicit queries
    """
    if ns is None: ns = globals()
    max_results = int(max_results)
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    
    query_upper = query.upper()
    if 'CONSTRUCT' in query_upper or 'DESCRIBE' in query_upper:
        sparql.setReturnFormat(XML)
        response = sparql.query()
        g = Graph()
        g.parse(data=response.response.read(), format='xml')
        triples = [(str(s), str(p), str(o)) for s,p,o in g]
        if len(triples) > max_results: triples = triples[:max_results]
        ns[name] = triples
        return f"Stored {len(triples)} triples into '{name}'"
    else:
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        bindings = results.get('results', {}).get('bindings', [])
        if len(bindings) > max_results: bindings = bindings[:max_results]
        cols = results.get('head', {}).get('vars', [])
        ns[name] = bindings
        return f"Stored {len(bindings)} results into '{name}': columns {cols}"