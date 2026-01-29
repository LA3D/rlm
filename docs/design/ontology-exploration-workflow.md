# Ontology Exploration Workflow Design

**Date**: 2026-01-28
**Status**: Design Draft
**Purpose**: Define a two-phase workflow where LLM builds its own agent guide through ontology exploration

---

## Core Insight

Instead of pre-written static AGENT_GUIDE.md, the LLM should:
1. **Explore the ontology** loaded in memory
2. **Generate understanding** through chain-of-thought
3. **Materialize that understanding** as a reusable guide
4. **Query agents use the materialized guide** - they don't re-explore

This is a **workflow**, not dynamic per-query exploration.

---

## Two-Phase Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 1: ONTOLOGY EXPLORATION                    │
│                    (Run once per ontology)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Load ontology graph into namespace                              │
│     ns['ont'] = Graph().parse('schema.ttl')                         │
│                                                                     │
│  2. RLM explores graph using rdflib                                 │
│     - Discover classes, properties, hierarchies                     │
│     - Write exploration code in REPL                                │
│     - Use llm_query() to synthesize understanding                   │
│                                                                     │
│  3. Materialize chain-of-thought as guide                           │
│     ns['ontology_guide'] = {                                        │
│         'exploration_cot': "I found that...",                       │
│         'domain_model': {...},                                      │
│         'query_patterns': [...],                                    │
│         'key_concepts': {...}                                       │
│     }                                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ Shared namespace persists
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: QUERY CONSTRUCTION                      │
│                    (Run for each user query)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Query agent receives user question                              │
│                                                                     │
│  2. Agent reads materialized guide from namespace                   │
│     guide = ns['ontology_guide']                                    │
│                                                                     │
│  3. Agent reasons using pre-computed understanding                  │
│     - References exploration_cot for context                        │
│     - Uses query_patterns as templates                              │
│     - Applies key_concepts to map user terms                        │
│                                                                     │
│  4. Agent constructs and executes SPARQL                            │
│     - Grounded in ontology understanding                            │
│     - Chain-of-thought references the guide                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Ontology Exploration

### Purpose
Build understanding of ontology structure and semantics through LLM-driven exploration. The output is a materialized guide that query agents can use.

### Input
- Path to ontology file(s)
- Empty or pre-seeded namespace

### Process

**Step 1: Load Graph**
```python
from rdflib import Graph, RDF, RDFS, OWL

ns['ont'] = Graph()
ns['ont'].parse('ontology/uniprot/core.ttl')
print(f"Loaded {len(ns['ont'])} triples")
```

**Step 2: Structural Discovery (model writes this in REPL)**
```python
# Discover classes
classes = list(ns['ont'].subjects(RDF.type, OWL.Class))
print(f"Found {len(classes)} classes")

# Sample with labels
for c in classes[:20]:
    label = ns['ont'].value(c, RDFS.label)
    comment = ns['ont'].value(c, RDFS.comment)
    print(f"  {c}")
    print(f"    Label: {label}")
    if comment:
        print(f"    Comment: {comment[:100]}...")
```

**Step 3: Relationship Discovery**
```python
# Discover properties
props = list(ns['ont'].subjects(RDF.type, OWL.ObjectProperty))
props += list(ns['ont'].subjects(RDF.type, OWL.DatatypeProperty))

# Examine domains and ranges
for p in props[:15]:
    label = ns['ont'].value(p, RDFS.label)
    domain = ns['ont'].value(p, RDFS.domain)
    range_ = ns['ont'].value(p, RDFS.range)
    print(f"  {label}: {domain} -> {range_}")
```

**Step 4: Hierarchy Discovery**
```python
# Find class hierarchy
hierarchy = {}
for s, p, o in ns['ont'].triples((None, RDFS.subClassOf, None)):
    parent = str(o)
    child = str(s)
    if parent not in hierarchy:
        hierarchy[parent] = []
    hierarchy[parent].append(child)

# Find root classes (no parent)
all_children = set(c for children in hierarchy.values() for c in children)
roots = [c for c in hierarchy.keys() if c not in all_children]
print(f"Root classes: {roots[:10]}")
```

**Step 5: Semantic Synthesis (using llm_query)**
```python
# Ask sub-LLM to synthesize understanding
class_summary = llm_query(f"""
Based on these classes I discovered in the ontology:
{classes[:30]}

With labels:
{[(c, ns['ont'].value(c, RDFS.label)) for c in classes[:30]]}

What is this ontology about? What are the main conceptual areas?
What should I know to construct SPARQL queries against it?
""")
print(class_summary)
ns['_class_understanding'] = class_summary
```

```python
# Synthesize property understanding
prop_summary = llm_query(f"""
Based on these properties connecting classes:
{[(p, ns['ont'].value(p, RDFS.domain), ns['ont'].value(p, RDFS.range))
  for p in props[:20]]}

How do the main concepts in this ontology connect?
What relationship patterns should I use in SPARQL queries?
""")
ns['_prop_understanding'] = prop_summary
```

**Step 6: Materialize Guide**
```python
# Compile exploration into reusable guide
ns['ontology_guide'] = {
    'exploration_cot': f"""
## Ontology Exploration Chain-of-Thought

I explored the {len(ns['ont'])} triple ontology and discovered:

### Classes ({len(classes)} total)
{ns['_class_understanding']}

### Properties ({len(props)} total)
{ns['_prop_understanding']}

### Hierarchy
Root classes: {roots[:5]}
Branching structure: {len(hierarchy)} parent classes with children

### Key Findings
- Main entity types: ...
- Key relationships: ...
- Query patterns to use: ...
""",
    'key_classes': [...],  # URIs and labels
    'key_properties': [...],  # URIs, domains, ranges
    'hierarchy': hierarchy,
    'query_patterns': [...]  # Extracted from llm_query synthesis
}

print("Materialized ontology guide")
```

### Output
- `ns['ontology_guide']` - Structured guide with chain-of-thought
- `ns['ont']` - Graph remains available for reference
- Guide can be serialized for reuse across sessions

---

## Phase 2: Query Construction

### Purpose
Use the materialized guide to construct SPARQL queries grounded in ontology understanding.

### Input
- User query (natural language)
- `ns['ontology_guide']` from Phase 1
- `ns['ont']` graph (for reference lookups)

### Process

**Step 1: Load Context**
```python
# Query agent reads the guide
guide = ns['ontology_guide']
print("=== Ontology Understanding ===")
print(guide['exploration_cot'][:1000])
```

**Step 2: Map User Concepts**
```python
# User asked about "kinase activity"
# Check guide for relevant concepts
user_term = "kinase activity"

# Search in key_classes
matches = [c for c in guide['key_classes']
           if user_term.lower() in c['label'].lower()]
print(f"Matched classes: {matches}")

# If not found, use llm_query with guide context
if not matches:
    mapping = llm_query(f"""
    Based on this ontology understanding:
    {guide['exploration_cot'][:2000]}

    The user is asking about "{user_term}".
    What class or concept in this ontology corresponds to this?
    How should I query for it?
    """)
    print(mapping)
```

**Step 3: Construct Query Using Patterns**
```python
# Use query patterns from guide
patterns = guide['query_patterns']
print(f"Available patterns: {[p['name'] for p in patterns]}")

# Select appropriate pattern based on query type
# Adapt pattern with mapped concepts
# Execute SPARQL
```

### Chain-of-Thought Requirement

Query agent's thinking MUST reference the guide:

```
THINK: Based on the ontology exploration, I learned that:
- Proteins connect to GO terms via up:classifiedWith
- GO terms form a hierarchy with rdfs:subClassOf
- For "kinase activity", the guide shows GO:0016301

Therefore, my query should:
1. Filter proteins by organism (taxon:9606 for human)
2. Use classifiedWith to link to GO terms
3. Include subClassOf* for GO hierarchy traversal
```

---

## Workflow Implementation

### Option A: Sequential Script
```python
# explore_ontology.py - Run once
ns = {}
result = run_exploration_rlm(
    ontology_path="ontology/uniprot/core.ttl",
    ns=ns,
    max_iterations=15
)
# Serialize guide
save_guide(ns['ontology_guide'], 'uniprot_guide.json')
```

```python
# query.py - Run for each query
ns = {}
ns['ontology_guide'] = load_guide('uniprot_guide.json')
ns['ont'] = Graph().parse('ontology/uniprot/core.ttl')

result = run_query_rlm(
    query="Find human proteins with kinase activity",
    ns=ns,
    max_iterations=10
)
```

### Option B: DSPy Module Composition
```python
class OntologyWorkflow(dspy.Module):
    def __init__(self, ontology_path):
        self.explorer = dspy.RLM(ExplorationSig, ...)
        self.querier = dspy.RLM(QuerySig, ...)
        self.ontology_path = ontology_path
        self._guide = None

    def explore(self):
        """Phase 1: Build understanding (run once)"""
        ns = {'ont': Graph().parse(self.ontology_path)}
        result = self.explorer(ontology=ns['ont'])
        self._guide = result.guide
        return self._guide

    def query(self, question: str):
        """Phase 2: Answer query using guide"""
        if self._guide is None:
            self.explore()

        ns = {
            'ont': Graph().parse(self.ontology_path),
            'ontology_guide': self._guide
        }
        return self.querier(query=question, guide=self._guide)
```

### Option C: Persistent Namespace Server
```python
# Long-running process with shared namespace
class OntologyServer:
    def __init__(self):
        self.ns = {}  # Shared namespace

    def load_ontology(self, path: str, name: str):
        self.ns[f'{name}_ont'] = Graph().parse(path)
        # Run exploration RLM
        guide = self._explore(name)
        self.ns[f'{name}_guide'] = guide

    def query(self, ontology_name: str, question: str):
        # Query RLM uses pre-computed guide
        return self._query(
            question,
            self.ns[f'{ontology_name}_guide'],
            self.ns[f'{ontology_name}_ont']
        )
```

---

## Signatures

### Exploration Signature
```python
class OntologyExplorationSig(dspy.Signature):
    """Explore an ontology and build understanding through chain-of-thought.

    You have access to the ontology graph via ns['ont'] (rdflib Graph).
    Use rdflib to explore: triples(), subjects(), objects(), value().
    Use llm_query() to synthesize understanding of what you find.

    Your exploration_cot should document what you learned.
    Your guide should be structured for query agents to use.
    """

    ontology_path: str = dspy.InputField(desc="Path to loaded ontology")

    exploration_cot: str = dspy.OutputField(
        desc="Chain-of-thought documenting your exploration: "
             "what classes you found, how they connect, key patterns"
    )
    domain_summary: str = dspy.OutputField(
        desc="What is this ontology about? Main concepts and scope."
    )
    key_classes: list = dspy.OutputField(
        desc="Important classes with URIs, labels, and why they matter"
    )
    key_properties: list = dspy.OutputField(
        desc="Important properties with domain->range and usage patterns"
    )
    query_patterns: list = dspy.OutputField(
        desc="SPARQL patterns for common query types on this ontology"
    )
```

### Query Signature
```python
class OntologyQuerySig(dspy.Signature):
    """Construct SPARQL query using pre-computed ontology understanding.

    You have access to:
    - ns['ontology_guide'] - Exploration chain-of-thought and patterns
    - ns['ont'] - The ontology graph for reference lookups

    Your thinking MUST reference what you learned from the guide.
    """

    query: str = dspy.InputField(desc="User question")
    guide_summary: str = dspy.InputField(desc="Ontology guide exploration_cot")

    thinking: str = dspy.OutputField(
        desc="THINK: Reference the guide. What did exploration reveal about "
             "relevant classes/properties? How does that inform your query?"
    )
    concept_mapping: str = dspy.OutputField(
        desc="Map user terms to ontology concepts using guide knowledge"
    )
    sparql: str = dspy.OutputField(desc="SPARQL query grounded in ontology understanding")
    answer: str = dspy.OutputField(desc="Answer to user question")
```

---

## Key Design Principles

1. **LLM builds the guide** - Not pre-written, generated through exploration
2. **Chain-of-thought is materialized** - Exploration reasoning becomes reusable artifact
3. **Two distinct phases** - Explore once, query many times
4. **Simple tools** - Just rdflib access and llm_query, no specialized exploration tools
5. **Shared namespace** - Both phases use common namespace for state
6. **Guide references required** - Query CoT must cite exploration findings

---

## Benefits

1. **Ontology-grounded reasoning** - Understanding comes from actual exploration
2. **Reusable understanding** - Explore once, amortize across queries
3. **Transparent reasoning** - Chain-of-thought shows HOW understanding was built
4. **Adaptable** - Different ontologies get different guides based on their structure
5. **Simple implementation** - No complex tool proliferation

---

## Open Questions

1. **Guide format** - What structure best supports query agents?
2. **Exploration depth** - How thoroughly should Phase 1 explore?
3. **Guide updates** - When ontology changes, how to refresh?
4. **Multi-ontology** - How to handle queries spanning multiple ontologies?
5. **Validation** - How to verify guide accuracy?

---

## Next Steps

1. Implement exploration signature and prompt
2. Test on PROV ontology (small, well-understood)
3. Iterate on guide structure based on query agent needs
4. Scale to UniProt schema
5. Evaluate: Does guide-based querying outperform static AGENT_GUIDE.md?

---

**Last Updated**: 2026-01-28
