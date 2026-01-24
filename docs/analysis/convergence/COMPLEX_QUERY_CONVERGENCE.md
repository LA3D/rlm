# Complex Query Convergence Analysis: SIO Process Pattern

## Executive Summary

Complex queries requiring **pattern synthesis across multiple entities** need significantly more iterations than simple entity descriptions:

| Query Type | Entities | Tool Calls | Iterations | Pattern |
|------------|----------|------------|------------|---------|
| **Simple** (prov:Activity) | 1 | 1-2 | 4-5 | Explore → Fetch → Extract → Synthesize |
| **Complex** (SIO Process Pattern) | 4+ | 11 | 9 | Explore → Multi-Fetch → Probe → Extract → Synthesize |

**Key Finding**: Complex pattern queries need **nearly 2x the iterations** of simple queries.

---

## Query Under Analysis

**Simple Query**: "What is prov:Activity?"
- Single entity lookup
- Direct definition retrieval
- Minimal relationship exploration

**Complex Query**: "What is the process pattern in SIO? Describe how processes relate to their participants and inputs/outputs."
- Multiple entity lookup (Process, Participant, Input, Output, hasParticipant, isParticipantIn)
- Relationship hierarchy exploration
- Pattern synthesis across entities

---

## Iteration-by-Iteration Breakdown: Complex Query

### Iteration 1: Environment Exploration
**Action**: Examine context
```python
print(context)
```
**Result**: See GraphMeta summary (1726 classes, 238 properties)
**Decision**: Need to search for Process-related entities

---

### Iteration 2: Initial Search
**Action**: Search for "process"
```python
sio_search_by_label("process")
```
**Result**: Found multiple process-related entities
```
[('http://semanticscience.org/resource/SIO_000006', 'process'),
 ('http://semanticscience.org/resource/SIO_000015', 'process attribute'),
 ...]
```
**Decision**: Need to describe the main process entity (SIO_000006)

---

### Iteration 3: Describe Process
**Action**: Get process definition
```python
sio_describe_entity("http://semanticscience.org/resource/SIO_000006")
```
**Result**: Got full process entity data including definition
```
{
  'uri': 'http://semanticscience.org/resource/SIO_000006',
  'label': 'process',
  'definition': 'an entity that is identifiable only through the unfolding of time...',
  ...
}
```
**Decision**: Need to explore relationships (participants, inputs, outputs)

---

### Iteration 4: Probe Relationships
**Action**: Find related properties
```python
sio_probe_relationships("http://semanticscience.org/resource/SIO_000006")
```
**Result**: Found participant-related properties
```
{
  'outgoing': [
    {'predicate': 'has participant', 'object': '...'},
    {'predicate': 'has input', 'object': '...'},
    ...
  ]
}
```
**Decision**: Need to describe these relationship properties

---

### Iteration 5: Search for Input/Output
**Action**: Find input and output properties
```python
sio_search_by_label("has input")
sio_search_by_label("has output")
```
**Result**: Found URIs for input/output properties
**Decision**: Need to describe these properties

---

### Iteration 6: Describe Input/Output Properties
**Action**: Get definitions for input/output
```python
sio_describe_entity("SIO_000230")  # has input
sio_describe_entity("SIO_000229")  # has output
sio_describe_entity("SIO_000132")  # has participant
```
**Result**: Got full property definitions and hierarchies
**Learning**:
- `has input` is subPropertyOf `has participant`
- `has output` is subPropertyOf `has participant`

---

### Iteration 7: Describe Inverse Properties
**Action**: Get inverse relationship info
```python
sio_describe_entity("SIO_000062")  # is participant in
sio_describe_entity("SIO_000139")  # is input in
sio_describe_entity("SIO_000138")  # is output of
```
**Result**: Got complete bidirectional relationship data
**Decision**: Now have all pieces, need to extract pattern

---

### Iteration 8: Data Processing
**Action**: Extract hierarchy and relationships
```python
# Process gathered data
# Extract subPropertyOf relationships
# Build hierarchy structure
```
**Result**: Structured pattern information ready for synthesis
**Decision**: Ready to synthesize final answer

---

### Iteration 9: Synthesis & Convergence ✅
**Action**: Combine all information into coherent pattern description
```python
FINAL_VAR(answer)
```
**Result**: Comprehensive pattern description including:
- Process definition
- Participant hierarchy (general → input/output specialization)
- Bidirectional relationships (has participant ↔ is participant in)
- Domain/range constraints

---

## Complexity Factors Analysis

### Why Complex Queries Need More Iterations

#### 1. **Multiple Entity Discovery** (Iterations 2, 5)
Simple query: 1 entity (prov:Activity)
Complex query: 6+ entities (Process, hasParticipant, isParticipantIn, hasInput, hasOutput, etc.)

**Implication**: Need search iterations for each entity type

#### 2. **Relationship Exploration** (Iteration 4)
Simple query: Not needed (just describe entity)
Complex query: Must probe relationships to find connected properties

**Implication**: +1 iteration for probe_relationships()

#### 3. **Hierarchical Understanding** (Iterations 6-7)
Simple query: Single entity, no hierarchy
Complex query: Property hierarchies (hasInput subPropertyOf hasParticipant)

**Implication**: Must describe each level of hierarchy

#### 4. **Bidirectional Relationships** (Iteration 7)
Simple query: N/A
Complex query: Both forward (has participant) and inverse (is participant in)

**Implication**: Must describe both directions

#### 5. **Pattern Synthesis** (Iteration 8-9)
Simple query: Direct answer from definition
Complex query: Must synthesize pattern from multiple pieces

**Implication**: +1 iteration for data processing before synthesis

---

## Tool Usage Comparison

### Simple Query (prov:Activity)
```
Tool calls: 1-2
├─ prov_describe_entity: 1
└─ (maybe llm_query for synthesis)
```

### Complex Query (SIO Process Pattern)
```
Tool calls: 11
├─ sio_search_by_label: 3 (find process, input, output)
├─ sio_describe_entity: 7 (process + 6 properties)
└─ sio_probe_relationships: 1 (find related properties)
```

**Insight**: Complex query needs **5-6x more tool calls** to gather all related information.

---

## Convergence Pattern Comparison

### Simple Query Pattern (4-5 iterations)
```
1. Explore environment
2. Call describe_entity()
3. Extract definition
4. Synthesize answer
5. FINAL()
```

**Linear flow**: One entity → One extraction → One synthesis

### Complex Query Pattern (9 iterations)
```
1. Explore environment
2. Search for main entity
3. Describe main entity
4. Probe relationships
5. Search for related entities
6. Describe related entities (batch 1)
7. Describe related entities (batch 2)
8. Process/extract pattern
9. Synthesize and FINAL()
```

**Branching flow**: Multiple entities → Multiple extractions → Pattern recognition → Synthesis

---

## Phase Distribution

### Simple Query
- Exploration: 1 iteration (20%)
- Data gathering: 1 iteration (20%)
- Processing: 1 iteration (20%)
- Synthesis: 2 iterations (40%)

**Total**: 4-5 iterations

### Complex Query
- Exploration: 1 iteration (11%)
- Data gathering: 6 iterations (67%)  ← **Major difference**
- Processing: 1 iteration (11%)
- Synthesis: 1 iteration (11%)

**Total**: 9 iterations

**Key Insight**: Complex queries spend **67% of time in data gathering** vs 20% for simple queries.

---

## Quality of Synthesized Answer

### Simple Query Answer (196 chars)
```
An activity is something that occurs over a period of time and acts upon
or with entities; it may include consuming, processing, transforming,
modifying, relocating, using, or generating entities.
```
**Quality**: Good - direct definition from ontology

### Complex Query Answer (2,039 chars)
```
The process pattern in SIO follows a hierarchical structure centered
around the core concept of a process (SIO_000006)...

**Relationship Hierarchy:**
1. **Participant Relationships (General Level):**
   - has participant (SIO_000132): domain = process
   - is participant in (SIO_000062): range = process

2. **Input Relationships (Specialized Participants):**
   - has input (SIO_000230): subPropertyOf has participant
   - is input in (SIO_000139): subPropertyOf is participant in

3. **Output Relationships (Specialized Participants):**
   - has output (SIO_000229): subPropertyOf has participant
   - is output of (SIO_000138): subPropertyOf is participant in

**Pattern Structure:**
[Detailed hierarchy and relationship descriptions]
```
**Quality**: Excellent - synthesized pattern with hierarchy, examples, structure

**Insight**: More iterations enable **richer, more comprehensive answers**.

---

## Implications for max_iters Configuration

### Recommended Values

| Query Complexity | Max Iterations | Example |
|------------------|----------------|---------|
| **Trivial** | 3 | "What is 2+2?" |
| **Simple** | 5 | "What is prov:Activity?" |
| **Moderate** | 8 | "What are the subclasses of Activity?" |
| **Complex** | 10-12 | "Describe the process pattern in SIO" |
| **Very Complex** | 15+ | "Compare process patterns across 3 ontologies" |

### Why Not Always Use max_iters=15?

**Reasons for appropriate limits**:
1. **Cost**: Each iteration = 1 API call ($)
2. **Time**: More iterations = longer response time
3. **Diminishing Returns**: Most queries converge earlier
4. **Early Termination**: LLM calls FINAL() as soon as ready (doesn't use all iterations)

**Best Practice**: Set max_iters based on expected query complexity.

---

## Predicting Required Iterations

### Heuristics for Estimating Iteration Needs

```python
def estimate_iterations(query):
    iterations = 1  # Base: exploration

    # Count entities mentioned
    entities = count_entities_in_query(query)
    iterations += entities * 1.5  # Each entity needs search + describe

    # Check for relationship words
    if any(word in query for word in ['relate', 'connect', 'pattern', 'hierarchy']):
        iterations += 2  # probe_relationships + synthesis

    # Check for comparison
    if any(word in query for word in ['compare', 'difference', 'versus']):
        iterations += entities * 2  # Need to describe all, then compare

    # Add synthesis buffer
    iterations += 2

    return int(iterations)

# Examples:
estimate_iterations("What is prov:Activity?")
# → 1 (explore) + 1.5 (1 entity) + 2 (synthesis) = 4-5

estimate_iterations("What is the process pattern in SIO?")
# → 1 (explore) + 6 (4 entities * 1.5) + 2 (relationships) + 2 (synthesis) = 11

estimate_iterations("Compare process patterns in PROV and SIO")
# → 1 (explore) + 6 (2 ontologies * 2 entities * 1.5) + 4 (comparison) + 2 = 13
```

---

## Validation Experiments

### Experiment 1: max_iters=8 (Insufficient)
**Result**: Did NOT converge
**Last iteration**: Still gathering data (describing inverse properties)
**Conclusion**: Complex queries need synthesis time after data gathering

### Experiment 2: max_iters=12 (Sufficient)
**Result**: Converged at iteration 9
**Unused iterations**: 3
**Conclusion**: Appropriate buffer allows natural convergence

### Experiment 3: Impact of URI Expansion Fix
**Without fix**: Would need +1-2 iterations per failed describe_entity()
**With fix**: All describe_entity() calls succeed on first try
**Savings**: Potentially 6-12 iterations saved (critical for complex queries)

---

## Conclusions

1. **Complex queries scale non-linearly** with number of entities and relationships
   - 1 entity = 4-5 iterations
   - 4 entities + relationships = 9 iterations (~2x, not 4x)

2. **Data gathering dominates** complex query execution
   - 67% of iterations spent calling tools
   - Only 11% spent on final synthesis

3. **Tool fixes matter more** for complex queries
   - Simple query: 1-2 tool calls (fix saves 1 iteration)
   - Complex query: 11 tool calls (fix saves 6+ iterations)

4. **Quality scales with iterations**
   - More iterations = richer synthesis
   - Complex patterns require complete data before synthesis

5. **Appropriate max_iters prevents frustration**
   - Too low: Non-convergence despite correct approach
   - Too high: Unnecessary cost
   - Sweet spot: Expected iterations + 20% buffer

---

## Recommendations for Test Writers

### Testing Simple Queries
```python
answer, iterations, ns = rlm_run(
    "What is prov:Activity?",
    context,
    max_iters=5  # Simple entity lookup
)
```

### Testing Complex Queries
```python
answer, iterations, ns = rlm_run(
    "Describe the process pattern in SIO",
    context,
    max_iters=12  # Pattern synthesis across entities
)
```

### Testing Very Complex Queries
```python
answer, iterations, ns = rlm_run(
    "Compare process patterns in PROV, SIO, and BFO",
    context,
    max_iters=20  # Multi-ontology comparison
)
```

---

## Future Work

Potential optimizations to reduce iteration count for complex queries:

1. **Batch describe_entity()**: Allow describing multiple entities in one call
2. **Smart search**: Return entities + descriptions in one call
3. **Pattern templates**: Pre-synthesized common patterns
4. **Hierarchical caching**: Cache frequently accessed hierarchies

However, these optimizations may reduce **transparency** and **groundedness** of the RLM protocol.
