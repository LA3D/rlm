# Ontology Design Patterns for Progressive Disclosure

This document explores how ontology design patterns (ODPs) can guide progressive disclosure strategies in RLM-based systems, enabling more intelligent navigation of large ontologies.

## The Connection: Patterns as Navigation Signals

In progressive disclosure, the LLM needs **signals** to decide what to explore next. Ontology design patterns provide these signals:

- **Structural patterns** indicate how to traverse the hierarchy
- **Content patterns** reveal where domain knowledge is encoded
- **Relation patterns** show how entities connect

If the LLM can **recognize patterns**, it can navigate more efficiently than blind exploration.

## Key Ontology Design Pattern Sources

### DOLCE+DnS Ultralite (DUL)

**Source**: http://www.ontologydesignpatterns.org/ont/dul/DUL.owl

A lightweight foundational ontology with pattern-based architecture. DUL provides:
- Core upper-level concepts
- Modular content patterns (importable independently)
- Extensions: Plans, Information Objects, Collections, Legal, Lexical

### Semantic Science Integrated Ontology (SIO)

**Source**: http://semanticscience.org/ontology/sio.owl

Designed for biomedical knowledge discovery with explicit design patterns for:
- Objects, processes, and attributes
- Qualities, capabilities, and roles
- Measurements with units
- Mereotopological relations (part-of, contains, connected-to)

### OntologyDesignPatterns.org Catalog

**Source**: https://odpa.github.io/

Community catalog of reusable Content ODPs including:
- PartOf, Participation, AgentRole
- Classification, Collection, Sequence
- Time intervals, Events, Situations

## Pattern Categories for Progressive Disclosure

### 1. Structural Patterns

These patterns define **how to traverse** the ontology.

#### Upper-Level / Foundational Patterns

DUL and SIO both provide upper-level categorization:

| DUL Categories | SIO Categories |
|----------------|----------------|
| Object | Material Object |
| Event | Process |
| Quality | Quality |
| Abstract | Information Content Entity |
| Agent | Agent |
| | Role, Capability, Disposition |

**Progressive Disclosure Strategy**:
```python
```repl
# First: Identify which upper-level category is relevant
upper_classes = graph_search(ontology, "Object|Process|Quality", search_in="labels")

# Navigate DOWN from the relevant upper category
if query_mentions_action:
    start_from = "Process"
elif query_mentions_measurement:
    start_from = "Quality"
else:
    start_from = "Object"

subclasses = onto_class_hierarchy(ontology, start_from, depth=2)
```
```

#### Part-Whole Patterns

Both DUL and SIO model parthood relations:

```
DUL:
  dul:hasPart / dul:isPartOf (transitive)
  dul:hasComponent / dul:isComponentOf

SIO:
  sio:has-part / sio:is-part-of (transitive, reflexive)
  sio:has-proper-part (irreflexive)
  sio:contains / sio:is-contained-in (spatial, not parthood)
```

**Progressive Disclosure Strategy**:
```python
```repl
# Find entity of interest
entity = graphsearch('onto', 'protein complex')

# Explore its parts progressively
parts = graph_neighbors(onto, entity_uri, predicate="sio:has-part")
print(f"Direct parts: {parts}")

# Go deeper only if relevant
for part in parts:
    if is_relevant(part, query):
        sub_parts = graph_neighbors(onto, part, predicate="sio:has-part")
```
```

### 2. Content Patterns

These patterns encode **domain knowledge** in recognizable structures.

#### Participation Pattern

How entities participate in processes:

```turtle
# SIO Participation Pattern
:protein a sio:material-entity ;
    sio:is-participant-in :binding_process .

:binding_process a sio:process ;
    sio:has-participant :protein ;
    sio:has-agent :enzyme ;        # active participant
    sio:has-substrate :substrate ; # consumed
    sio:has-product :product .     # produced
```

**Progressive Disclosure Strategy**:
```python
```repl
# User asks: "What processes does ACE2 participate in?"

# Step 1: Find ACE2
ace2 = graphsearch('onto', 'ACE2')[0]['uri']

# Step 2: Find participation relations (don't load all processes)
participations = graph_slice(onto, subject=ace2,
                             predicate='sio:is-participant-in')

# Step 3: For each process, get role details via sub-LLM
for proc in participations:
    proc_slice = graphdesc('onto', proc)
    role = llm_query(f"What role does ACE2 play in this process?\n{proc_slice}")
    print(role)
```
```

#### Measurement / Quality Pattern

SIO's pattern for quantities with units:

```turtle
# SIO Measurement Pattern
:sample sio:has-attribute :mass_measurement .

:mass_measurement a sio:mass ;
    sio:has-value "5.2"^^xsd:float ;
    sio:has-unit unit:Kilogram .
```

**Progressive Disclosure Strategy**:
```python
```repl
# User asks: "What measurements are available for this sample?"

# Step 1: Find attributes (qualities)
attributes = graph_neighbors(onto, sample_uri, predicate='sio:has-attribute')

# Step 2: Filter to measurements (have sio:has-value)
measurements = []
for attr in attributes:
    if graph_has_predicate(onto, attr, 'sio:has-value'):
        measurements.append(attr)

# Step 3: Get details only for relevant measurements
for m in measurements[:5]:
    details = graphdesc('onto', m)
    print(details)
```
```

#### Role Pattern

DUL and SIO model roles as context-dependent classifications:

```turtle
# SIO Role Pattern
:person sio:has-role :researcher_role .

:researcher_role a sio:researcher-role ;
    sio:is-realized-in :experiment .
```

**Progressive Disclosure Strategy**:
```python
```repl
# User asks: "What roles can a Person have?"

# Step 1: Find role classes
role_classes = onto_class_hierarchy(onto, 'sio:role', depth=3)

# Step 2: For the query context, find relevant roles
context_roles = llm_query(f"""
Which of these roles are relevant to biomedical research?
{role_classes}
Return only the relevant URIs.
""")

# Step 3: Get details for relevant roles only
for role in context_roles:
    role_info = graphdesc('onto', role)
```
```

### 3. Relation Patterns

These patterns define **how to follow connections**.

#### Mereotopological Relations (SIO)

```
Hierarchy of spatial relations:
sio:is-located-in
  └── sio:is-contained-in (spatial overlap, not parthood)
        └── sio:is-part-of (parthood)
              └── sio:is-proper-part-of (irreflexive)

sio:is-connected-to (boundary sharing, symmetric, transitive)
```

**Progressive Disclosure Strategy**:
```python
```repl
# User asks: "Where is this protein located?"

# Try most specific first, broaden if needed
location = graph_neighbors(onto, protein_uri, predicate='sio:is-part-of')
if not location:
    location = graph_neighbors(onto, protein_uri, predicate='sio:is-contained-in')
if not location:
    location = graph_neighbors(onto, protein_uri, predicate='sio:is-located-in')
```
```

#### Referential Relations (SIO)

```
sio:refers-to (basic mention)
  └── sio:is-about (topic)
  └── sio:describes
  └── sio:denotes (sign → meaning)

sio:has-evidence
  └── sio:is-supported-by
  └── sio:is-disputed-by
  └── sio:is-refuted-by
```

**Progressive Disclosure Strategy**:
```python
```repl
# User asks: "What evidence supports this claim?"

claim_uri = "..."

# Get evidence relations
evidence = graph_neighbors(onto, claim_uri, predicate='sio:has-evidence')

# Categorize by type
supported = [e for e in evidence if has_type(e, 'sio:is-supported-by')]
disputed = [e for e in evidence if has_type(e, 'sio:is-disputed-by')]

# Only fetch details for supporting evidence if that's what user wants
for e in supported[:3]:
    details = graphdesc('onto', e)
    summary = llm_query(f"Summarize this evidence:\n{details}")
```
```

## Pattern-Aware Exploration Algorithm

```python
def pattern_aware_explore(ontology, query, max_depth=3):
    """
    Progressive disclosure guided by ontology design patterns.
    """

    # Phase 1: Detect ontology patterns
    patterns = detect_patterns(ontology)
    # Returns: {"upper_level": "DUL"|"SIO"|"custom",
    #           "has_parthood": True/False,
    #           "has_participation": True/False,
    #           "has_measurements": True/False, ...}

    # Phase 2: Identify relevant upper-level category
    category = llm_query(f"""
    Given query: {query}
    And these upper-level categories: {patterns['upper_categories']}
    Which category is most relevant? Return the URI.
    """)

    # Phase 3: Navigate using pattern-specific relations
    if "process" in query.lower() and patterns['has_participation']:
        # Use participation pattern
        explore_via_participation(ontology, category, query)

    elif "part" in query.lower() and patterns['has_parthood']:
        # Use parthood pattern
        explore_via_parthood(ontology, category, query)

    elif "measure" in query.lower() and patterns['has_measurements']:
        # Use measurement pattern
        explore_via_measurement(ontology, category, query)

    else:
        # Default: hierarchical exploration
        explore_hierarchy(ontology, category, query, max_depth)


def detect_patterns(ontology):
    """Detect which ODPs are used in this ontology."""
    patterns = {}

    # Check for common upper-level imports
    imports = graph_get_imports(ontology)
    if 'dul' in str(imports).lower():
        patterns['upper_level'] = 'DUL'
    elif 'sio' in str(imports).lower():
        patterns['upper_level'] = 'SIO'

    # Check for specific relation patterns
    predicates = set(ontology.predicates())
    patterns['has_parthood'] = any('part' in str(p).lower() for p in predicates)
    patterns['has_participation'] = any('participant' in str(p).lower() for p in predicates)
    patterns['has_measurements'] = any('has-value' in str(p).lower() or
                                       'has-unit' in str(p).lower() for p in predicates)

    return patterns
```

## Pattern-Specific SPARQL Templates

Once patterns are detected, use pattern-specific query templates:

### Participation Pattern Query

```sparql
# Find all processes an entity participates in
SELECT ?process ?role ?roleType WHERE {
    ?entity sio:is-participant-in ?process .
    OPTIONAL {
        ?entity sio:has-role ?role .
        ?role sio:is-realized-in ?process .
        ?role a ?roleType .
    }
}
```

### Measurement Pattern Query

```sparql
# Get all measurements for an entity
SELECT ?quality ?value ?unit WHERE {
    ?entity sio:has-attribute ?quality .
    ?quality sio:has-value ?value .
    OPTIONAL { ?quality sio:has-unit ?unit }
}
```

### Part-Whole Pattern Query

```sparql
# Get all parts recursively (using property paths)
SELECT ?part ?partType WHERE {
    ?whole sio:has-part+ ?part .
    ?part a ?partType .
}
```

## Implementation: Pattern-Aware Graph Tools

```python
#| export
def detect_odp(graph: Graph) -> dict:
    """Detect which Ontology Design Patterns are used in a graph.

    Returns a dict of detected patterns that can guide exploration.
    """
    patterns = {
        "foundational": None,
        "content_patterns": [],
        "relation_patterns": []
    }

    # Check imports for foundational ontology
    for _, _, o in graph.triples((None, OWL.imports, None)):
        import_str = str(o).lower()
        if 'dul' in import_str or 'dolce' in import_str:
            patterns["foundational"] = "DUL"
        elif 'sio' in import_str or 'semanticscience' in import_str:
            patterns["foundational"] = "SIO"
        elif 'bfo' in import_str:
            patterns["foundational"] = "BFO"

    # Detect content patterns by checking for characteristic properties
    predicates = set(str(p) for p in graph.predicates())

    # Participation pattern
    if any('participant' in p for p in predicates):
        patterns["content_patterns"].append("Participation")

    # Part-whole pattern
    if any('has-part' in p or 'hasPart' in p for p in predicates):
        patterns["content_patterns"].append("PartWhole")

    # Measurement pattern
    if any('has-value' in p or 'hasValue' in p for p in predicates):
        patterns["content_patterns"].append("Measurement")

    # Role pattern
    if any('has-role' in p or 'hasRole' in p for p in predicates):
        patterns["content_patterns"].append("Role")

    # Information object pattern
    if any('refers-to' in p or 'refersTo' in p or 'denotes' in p for p in predicates):
        patterns["content_patterns"].append("InformationObject")

    # Detect relation patterns
    for p in predicates:
        if 'transitive' in p.lower():
            patterns["relation_patterns"].append("Transitive")
        if 'symmetric' in p.lower():
            patterns["relation_patterns"].append("Symmetric")

    return patterns


def get_pattern_relations(pattern: str) -> list[str]:
    """Get the characteristic relations for a detected pattern."""
    pattern_relations = {
        "Participation": [
            "sio:is-participant-in", "sio:has-participant",
            "sio:has-agent", "sio:has-substrate", "sio:has-product",
            "dul:hasParticipant", "dul:isParticipantIn"
        ],
        "PartWhole": [
            "sio:has-part", "sio:is-part-of",
            "sio:has-proper-part", "sio:is-proper-part-of",
            "dul:hasPart", "dul:isPartOf",
            "dul:hasComponent", "dul:isComponentOf"
        ],
        "Measurement": [
            "sio:has-attribute", "sio:has-value", "sio:has-unit",
            "dul:hasQuality", "dul:hasDataValue"
        ],
        "Role": [
            "sio:has-role", "sio:is-role-of", "sio:is-realized-in",
            "dul:hasRole", "dul:isRoleOf"
        ],
        "InformationObject": [
            "sio:refers-to", "sio:is-about", "sio:denotes",
            "sio:has-evidence", "sio:is-supported-by",
            "dul:isAbout", "dul:expresses"
        ]
    }
    return pattern_relations.get(pattern, [])


def explore_by_pattern(
    graph: Graph,
    start_uri: str,
    pattern: str,
    depth: int = 1
) -> Graph:
    """Extract a subgraph following pattern-specific relations."""
    relations = get_pattern_relations(pattern)
    subgraph = Graph()

    for prefix, ns in graph.namespaces():
        subgraph.bind(prefix, ns)

    def collect(uri, current_depth):
        if current_depth > depth:
            return
        node = URIRef(uri)
        for rel in relations:
            # Try to resolve the relation URI
            for prefix, ns in graph.namespaces():
                rel_uri = URIRef(rel.replace(f"{prefix}:", str(ns)))
                for s, p, o in graph.triples((node, rel_uri, None)):
                    subgraph.add((s, p, o))
                    if isinstance(o, URIRef):
                        collect(str(o), current_depth + 1)
                for s, p, o in graph.triples((None, rel_uri, node)):
                    subgraph.add((s, p, o))

    collect(start_uri, 0)
    return subgraph
```

## Example: Pattern-Guided Query Construction

```python
# Full workflow using pattern-aware progressive disclosure

# 1. Load ontology and detect patterns
ontology = load_ontology("biomedical.owl")
patterns = detect_odp(ontology)
print(f"Detected patterns: {patterns}")
# {"foundational": "SIO", "content_patterns": ["Participation", "Measurement", "PartWhole"]}

# 2. User query
query = "What processes does ACE2 participate in and what are their products?"

# 3. Pattern detection suggests using Participation pattern
if "Participation" in patterns["content_patterns"]:
    # Use participation-specific exploration
    ace2 = graphsearch('ontology', 'ACE2')[0]['uri']

    # Extract participation subgraph
    participation_graph = explore_by_pattern(ontology, ace2, "Participation", depth=2)

    # Serialize for sub-LLM
    turtle = graph_serialize(participation_graph, "turtle")

    # Sub-LLM analyzes with pattern context
    analysis = llm_query(f"""
    This ontology uses the SIO Participation pattern where:
    - sio:is-participant-in links entities to processes
    - sio:has-agent indicates active participants
    - sio:has-product indicates what is produced

    Analyze this subgraph about ACE2:
    {turtle}

    What processes does ACE2 participate in and what do they produce?
    """)

# 4. Construct SPARQL using pattern knowledge
sparql = llm_query(f"""
Given the SIO participation pattern, construct a SPARQL query to find:
- All processes ACE2 participates in
- The products of those processes

Use these relations:
{get_pattern_relations("Participation")}
""")
```

## Summary: Patterns Enable Smarter Progressive Disclosure

| Without Patterns | With Pattern Awareness |
|------------------|------------------------|
| Blind graph traversal | Targeted relation following |
| Explore all predicates | Focus on pattern-specific relations |
| Generic slicing | Pattern-aware subgraph extraction |
| Trial-and-error queries | Template-based SPARQL |
| Sub-LLM lacks context | Sub-LLM knows expected structure |

**Key Insight**: Ontology design patterns are **documentation of intention**. When an LLM recognizes that an ontology uses the SIO Participation pattern, it knows:
- What relations to follow
- What structure to expect
- How to construct valid queries
- What the domain modeler intended

This transforms progressive disclosure from random exploration into **guided navigation**.

## References

- [SIO Paper (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4015691/)
- [SIO GitHub](https://github.com/MaastrichtU-IDS/semanticscience)
- [DOLCE+DnS Ultralite](http://ontologydesignpatterns.org/wiki/Ontology:DOLCE+DnS_Ultralite)
- [DUL OWL](http://www.ontologydesignpatterns.org/ont/dul/DUL.owl)
- [ODP Portal](https://odpa.github.io/)
- [Applications of ODPs in Biomedical Ontologies](https://pmc.ncbi.nlm.nih.gov/articles/PMC3540458/)
- [Pattern-Based Ontology Design (Springer)](https://link.springer.com/chapter/10.1007/978-3-642-24794-1_3)
