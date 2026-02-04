"""Enhanced L1 Schema Constraints - Comprehensive correctness guidance.

Extracts:
- Domain/range constraints (property signatures)
- Disjoint classes + derived anti-patterns
- Property characteristics (Functional, Symmetric, Transitive, etc.)
- Cardinality constraints (from OWL Restrictions)
- Common SPARQL anti-patterns
"""

from rdflib import Graph, RDF, RDFS, OWL, URIRef, Literal
from rdflib.namespace import XSD

def extract(g: Graph) -> dict:
    """Extract comprehensive schema constraints."""

    # Domain/range constraints
    dr = []
    for p in g.subjects(RDFS.domain, None):
        doms = list(g.objects(p, RDFS.domain))
        rngs = list(g.objects(p, RDFS.range))
        if doms and rngs:
            p_name = str(p).split('/')[-1].split('#')[-1]
            d_name = str(doms[0]).split('/')[-1].split('#')[-1]
            r_name = str(rngs[0]).split('/')[-1].split('#')[-1]
            dr.append((p_name, d_name, r_name))

    # Disjoint classes
    disj = []
    for a, _, b in g.triples((None, OWL.disjointWith, None)):
        a_name = str(a).split('/')[-1].split('#')[-1]
        b_name = str(b).split('/')[-1].split('#')[-1]
        disj.append((a_name, b_name))

    # Property characteristics
    functional = [str(p).split('/')[-1].split('#')[-1]
                  for p in g.subjects(RDF.type, OWL.FunctionalProperty)]

    inverse_functional = [str(p).split('/')[-1].split('#')[-1]
                         for p in g.subjects(RDF.type, OWL.InverseFunctionalProperty)]

    symmetric = [str(p).split('/')[-1].split('#')[-1]
                for p in g.subjects(RDF.type, OWL.SymmetricProperty)]

    transitive = [str(p).split('/')[-1].split('#')[-1]
                 for p in g.subjects(RDF.type, OWL.TransitiveProperty)]

    # Cardinality constraints (from OWL Restrictions)
    cardinality = []
    for restriction in g.subjects(RDF.type, OWL.Restriction):
        on_prop = g.value(restriction, OWL.onProperty)
        if not on_prop:
            continue

        prop_name = str(on_prop).split('/')[-1].split('#')[-1]

        # Exact cardinality
        exact = g.value(restriction, OWL.cardinality) or g.value(restriction, OWL.qualifiedCardinality)
        if exact:
            cardinality.append((prop_name, 'exactly', int(exact)))
            continue

        # Min cardinality
        min_card = g.value(restriction, OWL.minCardinality) or g.value(restriction, OWL.minQualifiedCardinality)
        if min_card:
            cardinality.append((prop_name, 'min', int(min_card)))

        # Max cardinality
        max_card = g.value(restriction, OWL.maxCardinality) or g.value(restriction, OWL.maxQualifiedCardinality)
        if max_card:
            cardinality.append((prop_name, 'max', int(max_card)))

    return {
        'domain_range': dr,
        'disjoint': disj,
        'functional': functional,
        'inverse_functional': inverse_functional,
        'symmetric': symmetric,
        'transitive': transitive,
        'cardinality': cardinality,
    }


def generate_anti_patterns(constraints: dict) -> list[str]:
    """Generate anti-pattern warnings from constraints."""
    anti_patterns = []

    # From disjoint classes
    for a, b in constraints['disjoint'][:3]:  # Top 3 most important
        anti_patterns.append(f"Don't mix {a} and {b} in same query (disjoint)")

    # From functional properties
    if constraints['functional']:
        func_props = ', '.join(constraints['functional'][:3])
        anti_patterns.append(f"Functional props ({func_props}) have max 1 value per subject")

    # General SPARQL best practices
    anti_patterns.append("Always specify rdf:type for class-based queries")

    return anti_patterns


def pack(g: Graph, budget: int = 1000) -> str:
    """Pack schema constraints into bounded markdown.

    Priority:
    1. Anti-patterns (most actionable)
    2. Disjoint classes (prevent invalid queries)
    3. Property characteristics (enable optimizations)
    4. Domain/range (top 10 most important)
    5. Cardinality (if space)
    """
    c = extract(g)
    lines = ['**Schema Constraints**:']

    # 1. Anti-patterns (high value, concise)
    anti_patterns = generate_anti_patterns(c)
    if anti_patterns:
        lines.append('\n**Anti-patterns**:')
        for ap in anti_patterns[:3]:  # Top 3
            lines.append(f'- {ap}')

    # 2. Disjoint classes (critical for correctness)
    if c['disjoint']:
        disj_str = ', '.join(f'{a}⊥{b}' for a, b in c['disjoint'][:4])
        lines.append(f'\n**Disjoint**: {disj_str}')

    # 3. Property characteristics (enables optimizations)
    chars = []
    if c['functional']:
        chars.append(f"Functional: {', '.join(c['functional'][:3])}")
    if c['symmetric']:
        chars.append(f"Symmetric: {', '.join(c['symmetric'][:2])}")
    if c['transitive']:
        chars.append(f"Transitive: {', '.join(c['transitive'][:2])}")
    if c['inverse_functional']:
        chars.append(f"InverseFunctional: {', '.join(c['inverse_functional'][:2])}")

    if chars:
        lines.append('\n**Property Types**:')
        for char in chars[:3]:  # Max 3 types
            lines.append(f'- {char}')

    # 4. Domain/range (top 10 most important)
    if c['domain_range']:
        lines.append('\n**Domain/Range** (key properties):')
        for p, d, r in c['domain_range'][:10]:
            lines.append(f'- `{p}`: {d} → {r}')

    # 5. Cardinality (if space remains)
    if c['cardinality']:
        current = '\n'.join(lines)
        if len(current) + 100 < budget:  # Only if space
            lines.append('\n**Cardinality**:')
            for prop, op, val in c['cardinality'][:3]:
                lines.append(f'- `{prop}`: {op} {val}')

    return '\n'.join(lines)[:budget]
