# ReasoningBank Bootstrap Strategy

This document describes the strategy for bootstrapping procedural memory in the RLM system to improve convergence efficiency and reduce exploratory iterations.

---

## Executive Summary

ReasoningBank can improve RLM efficiency by **30-40%** on complex queries through learned exploration strategies. The recommended approach is a **four-layer hybrid bootstrap**:

0. **Sense data** (computed per ontology, provides navigational foundation)
1. **Curator-seeded core recipes** (6-8 stable, always-present strategies)
2. **Curriculum-learned task recipes** (self-improving through structured tasks)
3. **Trajectory-distilled ontology knowledge** (extracted from successful runs)

The key insight is that **sense data (Layer 0)** provides grounded, ontology-specific navigation that recipes operate on. This separation ensures recipes remain general while sense data provides specificity.

Expected improvements:
- Simple queries: 4-5 → 3-4 iterations (20-25% reduction)
- Complex queries: 9-10 → 6-7 iterations (30-35% reduction)
- Tool call efficiency: 40-50% improvement
- Convergence variance: ±2 → ±1 iterations
- Sense-enabled tool selection: ≥70% compliance with recommendations

---

## 1. The Bootstrap Problem

### The Chicken-and-Egg Situation

```
Without memories → System discovers everything from scratch → 9+ iterations
With memories    → System follows proven recipes           → 6-7 iterations

But: Where do initial memories come from?
```

ReasoningBank creates a learning loop:

```
RETRIEVE → INJECT → INTERACT → EXTRACT → STORE
    ↑                                      │
    └──────────────────────────────────────┘
```

The problem: New sessions start with **no memories**, forcing the system to:
- Rediscover exploration strategies every time
- Make suboptimal tool choices through trial-and-error
- Spend iterations on orientation that could be guided

### Empirical Evidence

From convergence analysis on the SIO process pattern query:

| Phase | Without Memory | With Recipe (Expected) |
|-------|---------------|------------------------|
| Orientation | 1 iteration | 1 iteration |
| Entity discovery | 2 iterations (search trial-and-error) | 1 iteration (guided) |
| Property discovery | 4 iterations (probe + describes) | 2 iterations (domain lookup) |
| Synthesis | 2 iterations | 2 iterations |
| **Total** | **9 iterations** | **6 iterations** |

The difference: **learned strategies vs discovered strategies**.

---

## 2. What Effective Procedural Memories Look Like

Procedural memories should encode **when and how** to use tools, not just that they exist.

### Memory Hierarchy

#### Level 1: Meta-Strategies (Universal)
```
"When exploring any ontology:
 1. Orient to available tools first
 2. Prefer metadata indexes over graph traversal
 3. Resolve entities by exact label before substring search
 4. Bound all exploration (never dump full graphs)
 5. Synthesize only after gathering sufficient evidence"
```

#### Level 2: Task-Type Recipes (Transferable)
```
"For 'What is X?' queries:
 - Call describe_entity(X) directly
 - Extract definition from outgoing_sample
 - If no definition, check rdfs:comment, skos:definition
 - Converge in 3-4 tool calls"

"For pattern synthesis queries:
 - Identify all entities mentioned
 - Use domain/range lookups to find connecting properties
 - Explore hierarchy if pattern involves specialization
 - Expect 6-8 tool calls before synthesis"
```

#### Level 3: Ontology-Specific Knowledge (Specialized)
```
"SIO-specific:
 - Uses dc:identifier heavily (2899 uses)
 - Process pattern: hasParticipant → hasInput/hasOutput (specialization)
 - Labels are reliable (1797 indexed)"

"PROV-specific:
 - Core triad: Entity, Activity, Agent
 - Uses prov:definition not rdfs:comment
 - Inverse properties: wasGeneratedBy ↔ generated"
```

### Memory Structure

Each memory item should contain:

```python
MemoryItem = {
    'id': str,                    # Unique identifier
    'title': str,                 # Short descriptive title
    'description': str,           # When to use this memory
    'content': str,               # The actual strategy/recipe
    'source_type': str,           # 'human' | 'curriculum' | 'distillation'
    'task_type': str,             # 'orientation' | 'entity' | 'hierarchy' | 'pattern' | 'query'
    'ontology': str | None,       # Specific ontology or None for universal
    'tags': List[str],            # Retrieval tags
    'created_at': str,            # ISO timestamp
    'validation': {               # Quality metrics
        'holdout_pass_rate': float,
        'retrieval_count': int,
        'success_when_used': float
    }
}
```

---

## 3. Bootstrap Strategy Options

### Option A: Curator-Seeded (Static)

**Approach**: Human experts write 10-20 canonical recipes that are always injected.

**Pros**:
- High quality, vetted content
- Immediate benefit from day one
- No cold-start problem

**Cons**:
- Doesn't scale to new ontologies
- Doesn't adapt based on experience
- Requires ongoing maintenance

**Verdict**: Necessary foundation, but insufficient alone.

---

### Option B: Curriculum Learning (Self-Improving)

**Approach**: Define a progression of tasks from simple to complex. Run tasks, extract memories from successful trajectories.

**Curriculum Levels**:

```
L1: Orientation
    "What namespaces are bound in {ontology}?"
    "How many classes and properties are in {ontology}?"
    "What annotation properties does {ontology} use?"

L2: Entity Discovery
    "What is {random_class}?"
    "Define {random_property}"
    "Describe {prominent_entity}"

L3: Hierarchy Navigation
    "What are the subclasses of {root_class}?"
    "What is the superclass chain of {leaf_class}?"
    "Is {class_a} a subclass of {class_b}?"

L4: Property Exploration
    "What properties have {class} as domain?"
    "What is the inverse of {property}?"
    "What are the most-used properties in {ontology}?"

L5: Pattern Synthesis
    "What is the {pattern_name} pattern in {ontology}?"
    "How do {entity_a} and {entity_b} relate?"
    "Describe the relationship between {entity_list}"

L6: Query Construction
    "Write a SPARQL query to find {target}"
    "Adapt this query template for {new_requirement}"
    "Execute and interpret the results"
```

**Learning Protocol**:
```
For each task:
  1. Run with current memories
  2. If converged AND grounded:
     - Extract trajectory artifact
     - Judge quality
     - If high quality: extract memories
     - Validate on holdout tasks
     - If passes: store
  3. Track metrics
```

**Pros**:
- Self-improving over time
- Task-relevant memories
- Scales to new ontologies

**Cons**:
- Requires initial exploration phase
- May extract noise without quality control
- Needs holdout validation infrastructure

**Verdict**: Powerful mechanism, needs quality gates.

---

### Option C: Trajectory Distillation (Offline)

**Approach**: Analyze successful trajectories offline to extract common patterns.

**Analysis Process**:
```python
# From a successful SIO trajectory:
patterns = {
    'tool_sequence': ['search', 'describe', 'probe', 'describe×3', 'synthesize'],
    'iteration_distribution': {
        'exploration': 1,
        'gathering': 6,
        'synthesis': 2
    },
    'effective_tools': ['describe_entity', 'search_by_label'],
    'unused_tools': ['predicate_frequency', 'find_path'],
    'key_decisions': [
        'Used probe_relationships to find hasParticipant',
        'Batched describe_entity calls for efficiency'
    ]
}

# Distill into memory:
memory = {
    'title': 'SIO Process Pattern Exploration',
    'content': '''
    For process patterns in SIO:
    1. Search "process" → find SIO_000006
    2. Describe process entity
    3. Probe relationships to find participant properties
    4. hasInput/hasOutput are subproperties of hasParticipant
    5. Describe each property for full pattern
    Expected: 8-10 iterations
    '''
}
```

**Pros**:
- Grounded in actual successful behavior
- Captures emergent strategies
- Can analyze many trajectories at scale

**Cons**:
- May overfit to specific runs
- Requires trajectory corpus
- Pattern extraction needs careful design

**Verdict**: Valuable for specialization, needs generalization checks.

---

### Option D: Hybrid Bootstrap (Recommended)

**Approach**: Combine all three methods in a layered architecture with quality control at each stage.

See Section 4 for detailed design.

---

## 4. Hybrid Bootstrap Architecture

### Four-Layer Memory System

The architecture includes a foundational **Layer 0** for ontology sense data, which provides the navigational substrate that recipes operate on. See [Ontology Sense Improvements](ont-sense-improvements.md) for detailed schema and implementation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 0: Sense Data (Computed Per Ontology)                                │
│  ─────────────────────────────────────────────                              │
│  • Generated once per ontology via build_sense()                            │
│  • sense_card: Always injected (~500 chars)                                 │
│  • sense_brief: Retrieved when needed (~2000 chars)                         │
│  • Provides ontology-specific navigation without LLM memory                 │
│                                                                             │
│  Sense Card Contains:                                                       │
│    - domain_scope (what the ontology covers)                                │
│    - key_classes (starting points for exploration)                          │
│    - key_properties (relationship vocabulary)                               │
│    - available_indexes (metadata shortcut indicators)                       │
│    - label_predicates (how to find labels)                                  │
│    - quick_hints (ontology-specific guidance)                               │
│                                                                             │
│  Grounding: All URIs in sense must exist in ontology (validated)            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: Core Recipes (Curator-Seeded)                                     │
│  ───────────────────────────────────────                                    │
│  • Always injected into every query                                         │
│  • 6-8 stable, universal strategies                                         │
│  • Human-authored and validated                                             │
│  • Provides baseline competence                                             │
│  • Includes Recipe 0: How to Use Sense Data                                 │
│                                                                             │
│  Examples:                                                                  │
│    - Recipe 0: How to Use Sense Data                                        │
│    - Ontology Orientation Recipe                                            │
│    - Single Entity Lookup Recipe                                            │
│    - Pattern Synthesis Recipe                                               │
│    - Hierarchy Exploration Recipe                                           │
│    - Metadata-First Principle                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: Task-Type Recipes (Curriculum-Learned)                            │
│  ───────────────────────────────────────────────                            │
│  • Retrieved by task type similarity                                        │
│  • Learned through curriculum progression                                   │
│  • Validated on holdout tasks before storage                                │
│  • Max 2 recipes injected per query                                         │
│                                                                             │
│  Examples:                                                                  │
│    - "For 'compare X and Y' queries, describe both then contrast"           │
│    - "For 'most common' queries, use predicate_frequency first"             │
│    - "For inverse property queries, check owl:inverseOf"                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: Ontology-Specific Knowledge (Trajectory-Distilled)                │
│  ───────────────────────────────────────────────────────────                │
│  • Retrieved by ontology identifier + task type                             │
│  • Extracted from successful runs on specific ontologies                    │
│  • Contains ontology-specific conventions and patterns                      │
│  • Max 1 recipe injected per query                                          │
│                                                                             │
│  Examples:                                                                  │
│    - "SIO uses dc:identifier for entity IDs"                                │
│    - "PROV process pattern involves Activity-Entity-Agent triad"            │
│    - "UniProt uses up:classifiedWith for taxonomy"                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Injection Strategy

The injection strategy now includes Layer 0 (sense data) as the foundation:

```python
def inject_context(
    query: str,
    ontology: str,
    sense: dict,
    memory_store: MemoryStore
) -> str:
    """Build complete context with sense data and memories."""

    # Layer 0: Always inject sense card (computed, not memory)
    context = format_sense_card(sense['sense_card'])

    # Optionally add sense brief sections based on query type
    context += get_sense_brief_sections(query, sense.get('sense_brief', {}))

    # Layer 1-3: Inject procedural memories
    memories = inject_memories(query, ontology, memory_store)
    context += format_memories(memories)

    return context


def inject_memories(query: str, ontology: str, memory_store: MemoryStore) -> List[MemoryItem]:
    """Select memories to inject for a query."""
    injected = []

    # Layer 1: Always inject core recipes (bounded)
    # Note: Recipe 0 (How to Use Sense Data) should be first
    core_recipes = memory_store.get_core_recipes()
    injected.extend(core_recipes[:2])  # Max 2 core recipes

    # Layer 2: Retrieve by task type
    task_type = classify_task_type(query)  # 'entity' | 'hierarchy' | 'pattern' | etc.
    task_recipes = memory_store.retrieve_by_task_type(task_type, k=2)
    injected.extend(task_recipes)

    # Layer 3: Retrieve ontology-specific (if available)
    if ontology:
        onto_knowledge = memory_store.retrieve_by_ontology(ontology, task_type, k=1)
        injected.extend(onto_knowledge)

    # Bound total injection
    return injected[:4]  # Never more than 4 memories


def get_sense_brief_sections(query: str, sense_brief: dict) -> str:
    """Auto-detect and retrieve relevant sense brief sections."""
    sections = []
    query_lower = query.lower()

    if any(word in query_lower for word in ['pattern', 'relate', 'connect']):
        sections.append(format_brief_section(sense_brief, 'patterns'))

    if any(word in query_lower for word in ['subclass', 'superclass', 'hierarchy', 'type']):
        sections.append(format_brief_section(sense_brief, 'hierarchy_overview'))

    if any(word in query_lower for word in ['sparql', 'query', 'select', 'construct']):
        sections.append(format_brief_section(sense_brief, 'starter_queries'))

    if any(word in query_lower for word in ['error', 'problem', 'issue', 'wrong']):
        sections.append(format_brief_section(sense_brief, 'gotchas'))

    return '\n'.join(sections)
```

### Context Integration

Memories are injected into the RLM context as structured guidance:

```python
def build_context_with_memories(base_context: str, memories: List[MemoryItem]) -> str:
    """Build context with injected procedural memories."""

    memory_section = """
## Relevant Procedural Knowledge

The following strategies have been effective for similar tasks:

"""
    for i, mem in enumerate(memories, 1):
        memory_section += f"""
### Strategy {i}: {mem['title']}
{mem['content']}

"""

    memory_section += """
Note: These are suggestions based on past experience. Adapt as needed for the current task.
"""

    return base_context + "\n" + memory_section
```

---

## 5. Core Recipes (Layer 1)

These 6-8 recipes form the foundation and are always available. Recipe 0 teaches how to use sense data and should be applied before all other recipes.

### Recipe 0: How to Use Sense Data

```markdown
## Recipe: How to Use Sense Data

**When to use**: Always, before any other recipe

**Procedure**:
1. Read `sense.domain_scope` to understand ontology coverage
2. Scan `sense.key_classes` for likely starting points
3. Note `sense.key_properties` for relationship vocabulary
4. Check `sense.label_predicates` to adjust search strategy:
   - If rdfs:label present: standard label search works
   - If only skos:prefLabel: may need different approach
5. Review `sense.available_indexes`:
   - by_label > 0: prefer exact label lookups
   - hierarchy > 100: use hierarchy tools, not describe chains
   - domains > 10: use domain lookup for property discovery
6. Glance at `sense.quick_hints` for ontology-specific guidance

**Then proceed with task-specific recipe**

**Key principle**: Sense data is navigation, not the answer. Use it to select tools, not to answer directly.

**Anti-patterns**:
- Ignoring sense and discovering everything from scratch
- Treating sense.domain_scope as the answer
- Not checking available_indexes before tool selection
```

### Recipe 1: Ontology Orientation

```markdown
## Recipe: Ontology Orientation

**When to use**: Starting exploration of any ontology

**Strategy**:
1. Print context summary to see graph size and namespaces
2. Note available tools (describe, search, probe, hierarchy, etc.)
3. Check if metadata tools exist (predicate_frequency, get_subclasses)
4. Identify naming conventions from namespace prefixes

**Expected iterations**: 1

**Key principle**: Understand the environment before acting
```

### Recipe 2: Single Entity Lookup

```markdown
## Recipe: Single Entity Lookup

**When to use**: Query asks "What is X?" or "Define X" or "Describe X"

**Strategy**:
1. Resolve X to URI:
   - First: exact label lookup (if available)
   - Fallback: search_by_label with substring
2. Call describe_entity(uri)
3. Extract definition from:
   - prov:definition (PROV ontologies)
   - rdfs:comment (most ontologies)
   - skos:definition (SKOS-based)
   - dcterms:description (Dublin Core)
4. If definition not in comment, check outgoing_sample
5. Synthesize answer with URI citation
6. Call FINAL_VAR(answer)

**Expected iterations**: 3-4

**Efficiency tip**: Don't probe relationships unless asked about connections
```

### Recipe 3: Pattern Synthesis

```markdown
## Recipe: Pattern Synthesis

**When to use**: Query asks about patterns, relationships between multiple entities,
or "how does X relate to Y"

**Strategy**:
1. Identify all entities mentioned in query
2. Resolve each entity to URI (batch if possible)
3. Find connecting properties:
   - First: domain/range lookup (O(1) if indexed)
   - Fallback: probe_relationships on primary entity
4. Check for property hierarchies (subPropertyOf relationships)
5. Look for inverse properties (owl:inverseOf)
6. Describe key properties (bound to 5-7)
7. Synthesize pattern description showing:
   - Entity roles
   - Property connections
   - Hierarchy relationships
8. Call FINAL_VAR(pattern_description)

**Expected iterations**: 6-8

**Key principle**: Gather all pieces before synthesizing the pattern
```

### Recipe 4: Hierarchy Exploration

```markdown
## Recipe: Hierarchy Exploration

**When to use**: Query asks about subclasses, superclasses, taxonomy, or "types of X"

**Strategy**:
1. Resolve target entity to URI
2. Use hierarchy tools if available:
   - get_subclasses(uri) for children
   - get_superclasses(uri) for parents
3. If no hierarchy tools:
   - Check meta.subs / meta.supers indexes
   - Or query for rdfs:subClassOf relationships
4. Bound results to 10-15 items
5. Get labels for each result
6. If deeper exploration needed, recurse (but bound depth to 2-3)
7. Format as hierarchy tree or list
8. Call FINAL_VAR(hierarchy)

**Expected iterations**: 3-5

**Efficiency tip**: Hierarchy indexes are pre-computed; prefer them over graph traversal
```

### Recipe 5: Metadata-First Principle

```markdown
## Recipe: Metadata-First Principle

**When to use**: Always (meta-strategy)

**Principle**: Prefer pre-computed metadata over graph traversal

**Specific guidance**:
1. For label lookups:
   - Use: by_label index or exact label tool (O(1))
   - Avoid: search_by_label substring scan (O(n))

2. For hierarchy:
   - Use: get_subclasses/get_superclasses or subs/supers indexes
   - Avoid: describe_entity chains or probe_relationships

3. For property discovery:
   - Use: domain/range indexes (find_properties_by_domain)
   - Avoid: probe_relationships when indexes suffice

4. For importance ranking:
   - Use: predicate_frequency tool
   - Avoid: guessing or sampling

**Rationale**: Graph queries cost iterations; index lookups are instant

**Expected savings**: 1-3 iterations on complex queries
```

### Recipe 6: Bounded Exploration

```markdown
## Recipe: Bounded Exploration

**When to use**: Always (safety constraint)

**Rules**:
1. Never request full graph dumps
2. Limit describe_entity calls to 10 per iteration
3. Limit search results to 20 items
4. Limit hierarchy depth to 3 levels
5. Limit outgoing/incoming triples to 20 samples

**When to stop gathering**:
- You have enough to answer the question
- Further exploration unlikely to change the answer
- You've hit 80% of max_iters without synthesizing

**Principle**: Bounded is better than complete; answer the question, don't map the ontology
```

### Recipe 7: Convergence Pattern

```markdown
## Recipe: Convergence Pattern

**When to use**: Always (protocol guidance)

**Standard flow**:
1. ORIENT (1 iter): Understand context and available tools
2. RESOLVE (1 iter): Find target entities
3. GATHER (2-5 iters): Collect relevant information
4. EXTRACT (1 iter): Pull out key facts
5. SYNTHESIZE (1 iter): Combine into answer
6. FINALIZE: Call FINAL_VAR(answer) or FINAL("answer")

**Convergence signals**:
- You have answered the question asked
- Evidence supports your answer
- Further exploration won't change the answer

**Anti-patterns**:
- Gathering without synthesizing
- Synthesizing without evidence
- Exploring tangentially related entities
- Reaching max_iters without calling FINAL
```

---

## 6. Curriculum Design (Layer 2)

### Task Progression

Each curriculum level builds on previous skills:

```
Level 1: Orientation (Foundation)
├── Learn: context interpretation, tool discovery
├── Tasks: namespace queries, statistics queries
└── Memories extracted: orientation strategies

Level 2: Entity Discovery (Building Block)
├── Learn: label resolution, entity description
├── Tasks: "What is X?", "Define Y"
├── Prerequisite: L1 orientation skills
└── Memories extracted: lookup strategies

Level 3: Hierarchy Navigation (Structure)
├── Learn: subclass/superclass traversal
├── Tasks: taxonomy queries, classification queries
├── Prerequisite: L2 entity skills
└── Memories extracted: hierarchy strategies

Level 4: Property Exploration (Relationships)
├── Learn: domain/range, inverses, property hierarchies
├── Tasks: property queries, relationship queries
├── Prerequisite: L3 hierarchy skills
└── Memories extracted: property strategies

Level 5: Pattern Synthesis (Integration)
├── Learn: multi-entity patterns, complex relationships
├── Tasks: pattern queries, comparison queries
├── Prerequisite: L2-L4 skills
└── Memories extracted: synthesis strategies

Level 6: Query Construction (Application)
├── Learn: SPARQL generation, template adaptation
├── Tasks: query writing, query modification
├── Prerequisite: L1-L5 skills
└── Memories extracted: query strategies
```

### Curriculum Execution Protocol

```python
def run_curriculum(ontology: str, memory_store: MemoryStore):
    """Execute curriculum for an ontology."""

    curriculum = load_curriculum_tasks(ontology)

    for level in curriculum.levels:
        print(f"Starting Level {level.number}: {level.name}")

        for task in level.tasks:
            # Setup
            ns = {}
            setup_ontology_context(ontology, ns)
            memories = memory_store.retrieve_relevant(task.query, ontology)

            # Execute
            answer, iterations, ns = rlm_run(
                task.query,
                build_context_with_memories(ns['meta'].summary(), memories),
                ns=ns,
                max_iters=task.expected_iters + 3  # Buffer
            )

            # Evaluate
            artifact = extract_trajectory_artifact(iterations, answer, task.query)
            judgment = judge_trajectory(artifact, ns)

            # Learn (if successful)
            if judgment['is_success'] and judgment['confidence'] in ['high', 'medium']:
                new_memories = extract_memories(artifact, judgment)

                for mem in new_memories:
                    # Validate before storing
                    if validate_memory(mem, memory_store, ontology):
                        memory_store.add(mem)
                        print(f"  + Stored memory: {mem['title']}")

            # Track metrics
            track_curriculum_progress(level, task, iterations, judgment)
```

### Task Templates

```python
CURRICULUM_TASKS = {
    'L1_orientation': [
        "What namespaces are bound in {ontology}?",
        "How many classes and properties are in {ontology}?",
        "What annotation properties does {ontology} use for labels?",
        "What is the base URI pattern for {ontology}?",
    ],
    'L2_entity': [
        "What is {class_name}?",
        "Define the property {property_name}",
        "Describe {entity_name} and its key characteristics",
        "What does {entity_name} represent in {ontology}?",
    ],
    'L3_hierarchy': [
        "What are the direct subclasses of {class_name}?",
        "What is the superclass hierarchy of {class_name}?",
        "List all leaf classes under {root_class}",
        "Is {class_a} a subclass of {class_b}?",
    ],
    'L4_properties': [
        "What properties have {class_name} as their domain?",
        "What is the range of property {property_name}?",
        "What is the inverse property of {property_name}?",
        "What are the most frequently used properties in {ontology}?",
    ],
    'L5_patterns': [
        "What is the {pattern_name} pattern in {ontology}?",
        "How do {entity_a} and {entity_b} relate to each other?",
        "Describe the relationship pattern between {entity_list}",
        "What pattern connects {class_a} to {class_b}?",
    ],
    'L6_queries': [
        "Write a SPARQL query to find all instances of {class_name}",
        "Adapt this query to filter by {constraint}: {query_template}",
        "What SPARQL pattern would retrieve {target_data}?",
    ],
}
```

---

## 7. Validation Pipeline

### Precondition: Sense Data Validation

Before any memory extraction or curriculum execution, sense data must be validated:

```python
def validate_sense_precondition(sense: dict, meta: GraphMeta) -> dict:
    """Validate sense data before proceeding with memory operations."""

    # Check grounding: all URIs must exist in ontology
    grounding = validate_sense_grounding(sense, meta)
    if not grounding['valid']:
        return {
            'proceed': False,
            'reason': f"Sense contains {grounding['error_count']} invalid URIs",
            'errors': grounding['errors']
        }

    # Check completeness: required fields present
    card = sense.get('sense_card', {})
    required = ['ontology_id', 'domain_scope', 'key_classes', 'available_indexes']
    missing = [f for f in required if f not in card or not card[f]]
    if missing:
        return {
            'proceed': False,
            'reason': f"Sense card missing required fields: {missing}"
        }

    # Check bounds: sense card should be compact
    card_size = len(str(card))
    if card_size > 1000:
        return {
            'proceed': True,
            'warning': f"Sense card is large ({card_size} chars), may impact context"
        }

    return {'proceed': True}
```

### Memory Quality Gates

Every memory must pass through quality gates before storage:

```
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDATION PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                               │
│  │  GATE 0:     │                                               │
│  │  Sense       │──────────────────────────────────────────┐    │
│  │  Valid?      │                                          │    │
│  └──────────────┘                                          │    │
│         │                                                  │    │
│    YES: Continue                                     NO: Stop   │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  GATE 1:     │     │  GATE 2:     │     │  GATE 3:     │    │
│  │  Dedup       │────▶│  Holdout     │────▶│  General-    │    │
│  │  Check       │     │  Validation  │     │  ization     │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│    Similar to          Pass rate on         Abstraction        │
│    existing?           holdout > 70%?       score > 0.7?       │
│         │                    │                    │             │
│    YES: Merge           NO: Reject          NO: Reject         │
│    NO: Continue                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Gate 0: Sense Validation

Before extracting or validating memories, verify sense data is grounded:

```python
def check_sense_validation(sense: dict, meta: GraphMeta) -> bool:
    """Gate 0: Ensure sense data is valid before memory operations."""

    result = validate_sense_precondition(sense, meta)
    if not result['proceed']:
        logging.warning(f"Sense validation failed: {result['reason']}")
        return False

    if 'warning' in result:
        logging.info(f"Sense warning: {result['warning']}")

    return True
```

### Gate 1: Deduplication

```python
def check_deduplication(new_memory: MemoryItem, store: MemoryStore) -> str:
    """Check if memory is duplicate or should be merged."""

    # Compute embedding similarity
    new_embedding = embed(new_memory['content'])

    for existing in store.all_memories():
        existing_embedding = embed(existing['content'])
        similarity = cosine_similarity(new_embedding, existing_embedding)

        if similarity > 0.9:
            # Very similar - merge or skip
            if new_memory['validation']['holdout_pass_rate'] > existing['validation']['holdout_pass_rate']:
                return 'replace'  # New is better
            else:
                return 'skip'  # Existing is better

        if similarity > 0.7:
            # Somewhat similar - consider merging
            return 'merge'

    return 'add'  # Novel memory
```

### Gate 2: Holdout Validation

```python
def validate_on_holdout(memory: MemoryItem, store: MemoryStore, ontology: str) -> bool:
    """Validate memory improves performance on holdout tasks."""

    holdout_tasks = get_holdout_tasks(memory['task_type'], ontology, n=5)

    results_with = []
    results_without = []

    for task in holdout_tasks:
        # Run WITH new memory
        memories_with = store.retrieve_relevant(task.query, ontology) + [memory]
        _, iters_with, _ = run_task(task, memories_with)
        results_with.append(len(iters_with))

        # Run WITHOUT new memory
        memories_without = store.retrieve_relevant(task.query, ontology)
        _, iters_without, _ = run_task(task, memories_without)
        results_without.append(len(iters_without))

    # Memory passes if it reduces iterations on majority of tasks
    improvements = sum(1 for w, wo in zip(results_with, results_without) if w < wo)
    pass_rate = improvements / len(holdout_tasks)

    return pass_rate >= 0.7  # At least 70% of tasks improved
```

### Gate 3: Generalization Check

```python
def check_generalization(memory: MemoryItem) -> float:
    """Score how generalizable a memory is (0-1)."""

    content = memory['content']
    score = 1.0

    # Penalize specific URIs (should use placeholders)
    uri_pattern = r'http://[^\s]+'
    uri_count = len(re.findall(uri_pattern, content))
    score -= uri_count * 0.1

    # Penalize specific ontology references (unless ontology-specific memory)
    if memory['ontology'] is None:
        onto_refs = ['SIO', 'PROV', 'DCAT', 'UniProt']
        for ref in onto_refs:
            if ref in content:
                score -= 0.15

    # Reward abstract patterns
    abstract_terms = ['entity', 'property', 'class', 'relationship', 'pattern']
    abstract_count = sum(1 for term in abstract_terms if term in content.lower())
    score += abstract_count * 0.05

    # Reward action verbs
    action_verbs = ['search', 'describe', 'probe', 'find', 'check', 'extract']
    action_count = sum(1 for verb in action_verbs if verb in content.lower())
    score += action_count * 0.03

    return max(0.0, min(1.0, score))
```

### Provenance Tracking

```python
@dataclass
class MemoryProvenance:
    source: str              # 'human' | 'curriculum' | 'distillation'
    created_at: str          # ISO timestamp
    created_from: str        # Task query or trajectory ID
    ontology_origin: str     # Which ontology it was learned from
    validation_date: str     # When last validated
    validation_results: dict # Holdout results
    retrieval_count: int     # How often retrieved
    success_when_used: float # Success rate when injected
```

---

## 8. Expected Impact

### Quantitative Improvements

| Metric | Without ReasoningBank | With ReasoningBank | Improvement |
|--------|----------------------|-------------------|-------------|
| Simple query iterations | 4-5 | 3-4 | 20-25% |
| Complex query iterations | 9-10 | 6-7 | 30-35% |
| Tool calls per query | 8-12 | 5-7 | 40-50% |
| Convergence variance | ±2 iterations | ±1 iteration | 50% |
| Novel ontology orientation | Full discovery | Guided transfer | 30-40% faster |

### Qualitative Improvements

1. **Consistency**: Proven strategies applied uniformly
2. **Efficiency**: Skip rediscovery of known patterns
3. **Transfer**: Knowledge from one ontology helps with others
4. **Adaptability**: System improves with experience
5. **Transparency**: Recipes are inspectable and debuggable

### Learning Curve

```
                    Effectiveness
                         │
                         │                    ╭─────── With ReasoningBank
                         │               ╭────╯
                         │          ╭────╯
                         │     ╭────╯
                         │╭────╯
                         ├────────────────────── Without ReasoningBank
                         │
                         └─────────────────────────────────▶
                              Experience (tasks completed)
```

---

## 9. Implementation Roadmap

### Phase 0: Sense Data Foundation (Week 1)

**Prerequisite**: Implement structured sense data before ReasoningBank recipes. See [Ontology Sense Improvements](ont-sense-improvements.md) for full details.

**Deliverables**:
- [ ] Define JSON schema for sense_card and sense_brief
- [ ] Update `build_sense()` with grounding constraints
- [ ] Implement post-generation validation
- [ ] Create sense card formatting for context injection
- [ ] Test on PROV, SIO, DCAT ontologies

**Success Criteria**:
- 100% grounding accuracy (no hallucinated URIs)
- Sense card ≤600 characters
- Validation function catches all invalid URIs

### Phase 1: Memory Foundation (Week 2-3)

**Deliverables**:
- [ ] Define MemoryItem schema
- [ ] Implement MemoryStore with retrieval
- [ ] Create 6-8 core recipes (Layer 1), including Recipe 0
- [ ] Integrate sense + memory injection into rlm_run()
- [ ] Basic tests for memory retrieval

**Success Criteria**:
- Core recipes inject correctly after sense card
- No regression on existing tests
- Memory retrieval returns relevant items

### Phase 2: Validation Pipeline (Week 3-4)

**Deliverables**:
- [ ] Implement deduplication check
- [ ] Implement holdout validation
- [ ] Implement generalization scoring
- [ ] Add provenance tracking
- [ ] Create holdout task sets for PROV, SIO

**Success Criteria**:
- Bad memories rejected by pipeline
- Good memories pass with >70% rate
- Provenance tracked for all memories

### Phase 3: Curriculum Learning (Week 5-6)

**Deliverables**:
- [ ] Define curriculum task templates
- [ ] Implement curriculum runner
- [ ] Run curriculum on PROV, SIO, DCAT
- [ ] Extract and validate memories
- [ ] Measure iteration improvements

**Success Criteria**:
- Curriculum completes without errors
- At least 10 valid memories extracted per ontology
- Measurable iteration reduction on holdout tasks

### Phase 4: Trajectory Distillation (Week 7-8)

**Deliverables**:
- [ ] Implement trajectory pattern extraction
- [ ] Create distillation pipeline
- [ ] Extract ontology-specific knowledge
- [ ] Validate distilled memories
- [ ] Integration with Layer 3

**Success Criteria**:
- Pattern extraction identifies key strategies
- Distilled memories pass validation
- Ontology-specific knowledge improves performance

### Phase 5: Evaluation & Tuning (Week 9-10)

**Deliverables**:
- [ ] Comprehensive benchmark on held-out ontologies
- [ ] A/B comparison: with vs without memories
- [ ] Tune injection limits (currently max 4)
- [ ] Document findings and recommendations
- [ ] Create monitoring dashboard

**Success Criteria**:
- 25%+ improvement on complex queries
- No regression on simple queries
- System stable under load

---

## 10. Success Metrics

### Primary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Iteration reduction (complex) | ≥25% | Mean iterations with vs without |
| Convergence rate | ≥95% | % queries that call FINAL without fallback |
| Iteration variance | ≤1 | StdDev of iterations for same query type |
| Memory quality | ≥70% | Holdout validation pass rate |

### Secondary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Memory retrieval relevance | ≥80% | Human judgment of top-3 retrieved |
| Answer quality preservation | No degradation | Groundedness score comparison |
| Novel ontology transfer | ≥15% improvement | First-run iterations vs baseline |
| Memory store growth | Logarithmic | Memories per ontology over time |

### Sense Data Metrics (Layer 0)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Sense grounding accuracy | 100% | % of URIs in sense that exist in ontology |
| Sense card size | ≤600 chars | Character count |
| Sense-enabled iteration reduction | ≥15% | Iterations with sense vs without |
| Tool selection compliance | ≥70% | % recommended tools used when available |
| Sense generation time | ≤5s | Time to generate sense for new ontology |

### Monitoring

```python
def log_rlm_run_metrics(query, ontology, memories_injected, iterations, converged, answer):
    """Log metrics for monitoring ReasoningBank effectiveness."""

    metrics = {
        'timestamp': datetime.now().isoformat(),
        'query_hash': hash(query),
        'ontology': ontology,
        'memories_injected': len(memories_injected),
        'memory_ids': [m['id'] for m in memories_injected],
        'iterations_used': len(iterations),
        'converged': converged,
        'tool_calls': sum(len(it.code_blocks) for it in iterations),
        'answer_length': len(answer),
    }

    # Log to metrics store for analysis
    metrics_store.append(metrics)
```

---

## 11. Risks and Mitigations

### Risk 1: Memory Pollution

**Risk**: Bad or outdated memories degrade performance.

**Mitigations**:
- Validation pipeline gates all memory storage
- Holdout validation requires measurable improvement
- Decay mechanism for unused memories
- Human review for flagged memories

### Risk 2: Overfitting

**Risk**: Memories too specific to training ontologies, fail to transfer.

**Mitigations**:
- Generalization scoring penalizes specific URIs
- Layer separation (universal vs ontology-specific)
- Cross-ontology validation in curriculum
- Regular refresh with new ontologies

### Risk 3: Context Bloat

**Risk**: Too many memories overwhelm the context.

**Mitigations**:
- Hard limit: max 4 memories injected
- Relevance ranking for retrieval
- Bounded memory content (max 500 chars each)
- Compression via summarization for verbose memories

### Risk 4: Rigidity

**Risk**: Following recipes blindly instead of adapting.

**Mitigations**:
- Recipes framed as "suggestions" not "requirements"
- Explicit "adapt to situation" instruction
- No penalty for deviating from recipe if successful
- Diverse recipes encourage flexibility

### Risk 5: Cold Start for New Ontologies

**Risk**: No ontology-specific memories available initially.

**Mitigations**:
- Layer 1 (core) and Layer 2 (task-type) always available
- Transfer learning from similar ontologies
- Fast curriculum run for new ontologies
- Graceful degradation to exploratory mode

---

## 12. Conclusion

ReasoningBank addresses a fundamental inefficiency in the RLM system: **rediscovering exploration strategies for every query**.

The hybrid bootstrap approach provides:

1. **Foundation** through Layer 0 sense data (ontology-specific navigation)
2. **Immediate value** through curator-seeded core recipes
3. **Self-improvement** through curriculum learning
4. **Specialization** through trajectory distillation
5. **Quality assurance** through the validation pipeline

Expected outcomes:
- **30-40% reduction** in iterations for complex queries
- **More consistent** convergence behavior
- **Transfer learning** across ontologies
- **Inspectable, debuggable** exploration strategies
- **Grounded guidance** through sense data validation

The key insight: **Memories encode when and how to use tools, not just that they exist.** Sense data provides the navigational substrate, while recipes teach efficient exploration strategies. Together, they transform the system from trial-and-error exploration to guided, efficient reasoning.

### Related Documents

- [Ontology Sense Improvements](ont-sense-improvements.md) - Detailed schema and implementation for Layer 0 sense data
- [System Recommendations](system-recommendations.md) - Overview of system improvements for reducing flakiness

---

## Appendix A: Memory Store Interface

```python
class MemoryStore:
    """Interface for procedural memory storage and retrieval."""

    def add(self, memory: MemoryItem) -> str:
        """Add a validated memory, return its ID."""

    def get(self, memory_id: str) -> MemoryItem:
        """Retrieve memory by ID."""

    def get_core_recipes(self) -> List[MemoryItem]:
        """Get Layer 1 core recipes (always present)."""

    def retrieve_by_task_type(self, task_type: str, k: int = 3) -> List[MemoryItem]:
        """Retrieve Layer 2 memories by task type similarity."""

    def retrieve_by_ontology(self, ontology: str, task_type: str, k: int = 2) -> List[MemoryItem]:
        """Retrieve Layer 3 ontology-specific memories."""

    def retrieve_relevant(self, query: str, ontology: str, k: int = 4) -> List[MemoryItem]:
        """Retrieve most relevant memories for a query (combines all layers)."""

    def update_usage(self, memory_id: str, was_successful: bool):
        """Track memory usage and success rate."""

    def prune_unused(self, days: int = 30):
        """Remove memories not retrieved in N days."""
```

## Appendix B: Example Memory Extraction

```python
def extract_memories_from_trajectory(
    artifact: dict,
    judgment: dict
) -> List[MemoryItem]:
    """Extract procedural memories from a successful trajectory."""

    memories = []

    # Only extract from high-quality trajectories
    if not judgment['is_success'] or judgment['confidence'] == 'low':
        return memories

    # Analyze tool usage pattern
    tool_sequence = []
    for iteration in artifact['iterations']:
        for block in iteration['code_blocks']:
            tools = re.findall(r'(\w+_\w+)\s*\(', block['code'])
            tool_sequence.extend(tools)

    # Extract strategy memory if pattern is clear
    if len(set(tool_sequence)) <= 5:  # Focused tool usage
        strategy_content = f"""
For queries like: "{artifact['query'][:50]}..."

Effective tool sequence:
{' → '.join(tool_sequence[:7])}

Key insight: {judgment.get('reason', 'Systematic exploration')}
"""
        memories.append(MemoryItem(
            id=str(uuid.uuid4()),
            title=f"Strategy: {classify_task_type(artifact['query'])}",
            description=f"Learned from successful {artifact['ontology']} exploration",
            content=strategy_content,
            source_type='distillation',
            task_type=classify_task_type(artifact['query']),
            ontology=artifact.get('ontology'),
            tags=['strategy', 'tool-sequence'],
            created_at=datetime.now(timezone.utc).isoformat(),
            validation={'holdout_pass_rate': 0.0, 'retrieval_count': 0, 'success_when_used': 0.0}
        ))

    return memories
```
