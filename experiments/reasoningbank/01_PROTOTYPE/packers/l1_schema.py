"""Enhanced L1 Schema Constraints - Comprehensive correctness guidance.

Extracts:
- Domain/range constraints by property type (Object, Datatype, Annotation)
- Disjoint classes + derived anti-patterns
- Property characteristics (Functional, Symmetric, Transitive, etc.)
- Cardinality constraints (from OWL Restrictions)
- SPARQL pattern hints (property paths for transitive properties)
"""

from rdflib import Graph, RDF, RDFS, OWL, URIRef, Literal, Namespace
from rdflib.namespace import XSD

# Schema.org namespace for domainIncludes/rangeIncludes pattern
SCHEMA = Namespace('https://schema.org/')
SCHEMA_HTTP = Namespace('http://schema.org/')

def _local_name(uri) -> str:
    """Extract local name from URI."""
    s = str(uri)
    return s.split('/')[-1].split('#')[-1]

def extract(g: Graph) -> dict:
    """Extract comprehensive schema constraints."""

    # Collect property types for classification
    object_props = set(g.subjects(RDF.type, OWL.ObjectProperty))
    datatype_props = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    annotation_props = set(g.subjects(RDF.type, OWL.AnnotationProperty))
    rdf_props = set(g.subjects(RDF.type, RDF.Property))  # Generic rdf:Property

    # Domain/range constraints - categorized by property type
    dr_object = []      # ObjectProperty: links entities
    dr_datatype = []    # DatatypeProperty: links to literals
    dr_other = []       # Properties without explicit OWL type

    # Track seen properties to avoid duplicates
    seen_props = set()

    # Method 1: Standard rdfs:domain + rdfs:range
    for p in g.subjects(RDFS.domain, None):
        doms = list(g.objects(p, RDFS.domain))
        rngs = list(g.objects(p, RDFS.range))
        if doms and rngs:
            p_name = _local_name(p)
            d_name = _local_name(doms[0])
            r_name = _local_name(rngs[0])
            entry = (p_name, d_name, r_name)
            seen_props.add(p)

            if p in object_props:
                dr_object.append(entry)
            elif p in datatype_props:
                dr_datatype.append(entry)
            else:
                dr_other.append(entry)

    # Method 2: Schema.org pattern (domainIncludes + rangeIncludes)
    # Used by Schema.org, Wikidata, and other large vocabularies
    for domain_pred in [SCHEMA.domainIncludes, SCHEMA_HTTP.domainIncludes]:
        for p in g.subjects(domain_pred, None):
            if p in seen_props:
                continue
            doms = list(g.objects(p, domain_pred))
            # Try both https and http variants for range
            rngs = list(g.objects(p, SCHEMA.rangeIncludes)) or list(g.objects(p, SCHEMA_HTTP.rangeIncludes))
            if doms and rngs:
                p_name = _local_name(p)
                d_name = _local_name(doms[0])
                r_name = _local_name(rngs[0])
                entry = (p_name, d_name, r_name)
                seen_props.add(p)

                # Schema.org uses rdf:Property, classify by range type
                if any('Text' in _local_name(r) or 'Date' in _local_name(r) or
                       'Number' in _local_name(r) or 'Boolean' in _local_name(r)
                       for r in rngs):
                    dr_datatype.append(entry)
                else:
                    dr_object.append(entry)

    # Disjoint classes
    disj = []
    for a, _, b in g.triples((None, OWL.disjointWith, None)):
        disj.append((_local_name(a), _local_name(b)))

    # Property characteristics
    functional = [_local_name(p) for p in g.subjects(RDF.type, OWL.FunctionalProperty)]
    inverse_functional = [_local_name(p) for p in g.subjects(RDF.type, OWL.InverseFunctionalProperty)]
    symmetric = [_local_name(p) for p in g.subjects(RDF.type, OWL.SymmetricProperty)]
    transitive = [_local_name(p) for p in g.subjects(RDF.type, OWL.TransitiveProperty)]

    # Cardinality constraints (from OWL Restrictions)
    cardinality = []
    for restriction in g.subjects(RDF.type, OWL.Restriction):
        on_prop = g.value(restriction, OWL.onProperty)
        if not on_prop:
            continue

        prop_name = _local_name(on_prop)

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

    # NamedIndividuals - enum-like values grouped by class type
    # These are important for queries that filter by specific values
    named_individuals = {}  # class_name -> [individual_names]
    for indiv in g.subjects(RDF.type, OWL.NamedIndividual):
        indiv_name = _local_name(indiv)
        # Get the class type(s) excluding NamedIndividual itself
        for cls in g.objects(indiv, RDF.type):
            if cls != OWL.NamedIndividual:
                cls_name = _local_name(cls)
                # Skip generic types
                if cls_name in ['Thing', 'Resource']:
                    continue
                if cls_name not in named_individuals:
                    named_individuals[cls_name] = []
                named_individuals[cls_name].append(indiv_name)

    return {
        'object_properties': dr_object,
        'datatype_properties': dr_datatype,
        'other_properties': dr_other,
        'annotation_properties': [_local_name(p) for p in annotation_props],
        'disjoint': disj,
        'functional': functional,
        'inverse_functional': inverse_functional,
        'symmetric': symmetric,
        'transitive': transitive,
        'cardinality': cardinality,
        'named_individuals': named_individuals,
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


def generate_sparql_hints(constraints: dict, include_defaults: bool = True) -> list[str]:
    """Generate SPARQL pattern hints from constraints.

    Args:
        constraints: Extracted schema constraints
        include_defaults: Include common RDFS/OWL patterns (default True)
    """
    hints = []

    # Default RDFS/OWL patterns (always useful for class/property hierarchies)
    if include_defaults:
        hints.append("Class hierarchy: `rdfs:subClassOf+` (transitive), `rdfs:subClassOf*` (includes self)")

    # Transitive property path hints from declared properties
    if constraints['transitive']:
        trans_props = constraints['transitive'][:3]
        for prop in trans_props:
            # Skip if already covered by defaults
            if 'subClassOf' in prop or 'subPropertyOf' in prop:
                continue
            hints.append(f"Use `{prop}+` for transitive closure, `{prop}*` includes start node")

    # Symmetric property hints
    if constraints['symmetric']:
        sym_props = ', '.join(constraints['symmetric'][:2])
        hints.append(f"Symmetric props ({sym_props}): ?a prop ?b implies ?b prop ?a")

    # Inverse functional hints
    if constraints['inverse_functional']:
        inv_props = ', '.join(constraints['inverse_functional'][:2])
        hints.append(f"InverseFunctional ({inv_props}): each value identifies at most one subject")

    return hints


def pack(g: Graph, budget: int = 1000) -> str:
    """Pack schema constraints into bounded markdown.

    Priority:
    1. Anti-patterns (most actionable)
    2. SPARQL hints (property paths, etc.)
    3. Disjoint classes (prevent invalid queries)
    4. Property characteristics (enable optimizations)
    5. Object properties (entity relationships)
    6. Datatype properties (literal values)
    7. Cardinality (if space)
    """
    c = extract(g)
    lines = ['**Schema Constraints**:']

    # 1. Anti-patterns (high value, concise)
    anti_patterns = generate_anti_patterns(c)
    if anti_patterns:
        lines.append('\n**Anti-patterns**:')
        for ap in anti_patterns[:3]:  # Top 3
            lines.append(f'- {ap}')

    # 2. SPARQL hints (property paths, symmetry, etc.)
    sparql_hints = generate_sparql_hints(c)
    if sparql_hints:
        lines.append('\n**SPARQL Patterns**:')
        for hint in sparql_hints[:4]:  # Top 4 hints
            lines.append(f'- {hint}')

    # 3. Disjoint classes (critical for correctness)
    if c['disjoint']:
        disj_str = ', '.join(f'{a}⊥{b}' for a, b in c['disjoint'][:4])
        lines.append(f'\n**Disjoint**: {disj_str}')

    # 4. Property characteristics (enables optimizations)
    chars = []
    if c['functional']:
        chars.append(f"Functional: {', '.join(c['functional'][:3])}")
    if c['transitive']:
        chars.append(f"Transitive: {', '.join(c['transitive'][:3])}")

    if chars:
        lines.append('\n**Property Characteristics**:')
        for char in chars:
            lines.append(f'- {char}')

    # 5. Object properties (entity-to-entity relationships)
    if c['object_properties']:
        lines.append('\n**Object Properties** (entity→entity):')
        for p, d, r in c['object_properties'][:8]:
            lines.append(f'- `{p}`: {d} → {r}')

    # 6. Datatype properties (entity-to-literal relationships)
    if c['datatype_properties']:
        lines.append('\n**Datatype Properties** (entity→literal):')
        for p, d, r in c['datatype_properties'][:5]:
            lines.append(f'- `{p}`: {d} → {r}')

    # 7. Other properties (without explicit OWL type)
    if c['other_properties'] and len('\n'.join(lines)) + 200 < budget:
        lines.append('\n**Other Properties**:')
        for p, d, r in c['other_properties'][:5]:
            lines.append(f'- `{p}`: {d} → {r}')

    # 8. Cardinality (if space remains)
    if c['cardinality']:
        current = '\n'.join(lines)
        if len(current) + 100 < budget:  # Only if space
            lines.append('\n**Cardinality**:')
            for prop, op, val in c['cardinality'][:3]:
                lines.append(f'- `{prop}`: {op} {val}')

    # 9. Named individuals (enum-like values for filtering)
    if c['named_individuals']:
        current = '\n'.join(lines)
        if len(current) + 150 < budget:  # Only if space
            lines.append('\n**Valid Values** (NamedIndividuals):')
            # Sort by class name, show classes with most members first
            sorted_classes = sorted(c['named_individuals'].items(),
                                    key=lambda x: -len(x[1]))
            for cls, members in sorted_classes[:4]:  # Top 4 classes
                member_str = ', '.join(members[:5])  # First 5 members
                if len(members) > 5:
                    member_str += f'... (+{len(members)-5})'
                lines.append(f'- {cls}: {member_str}')

    return '\n'.join(lines)[:budget]
