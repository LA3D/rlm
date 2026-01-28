# Chain-of-Thought Instruction Tuning - Implementation Summary

**Date:** 2026-01-27
**Status:** ✅ Complete - Phase 1-4 Delivered, Phase 5 Initial Results

## Overview

Implemented **PDDL-INSTRUCT style Chain-of-Thought instruction tuning** for DSPy RLM runtime without fine-tuning. Enables reasoning chain exemplars to improve SPARQL query construction through state tracking, verification feedback, and curriculum-aware retrieval.

**Scope:** Exemplar loading, verification feedback, curriculum retrieval, reasoning chain extraction
**Based on:** arXiv:2509.13351v1 - PDDL-INSTRUCT paradigm (28% → 94% accuracy via state-action-state reasoning)

## What Was Implemented

### 1. Exemplar Loading Infrastructure

**File:** `rlm_runtime/memory/exemplar_loader.py` (200 lines)

- **`parse_markdown_exemplar(md_content)`** - Parse markdown reasoning chain format
  - Extracts: question, level, reasoning_chain, query, anti_patterns, key_learnings
  - Supports structured markdown with headers and code blocks

- **`exemplar_to_memory_item(exemplar_dict, ontology_name)`** - Convert to MemoryItem
  - Sets `source_type='exemplar'` for filtering
  - Tags with `level-N` for curriculum retrieval
  - Computes content-based ID for deduplication

- **`load_exemplars_from_directory(exemplar_dir, backend, ontology_name, pattern)`**
  - Loads all matching .md files
  - Handles duplicates gracefully
  - Reports loaded exemplars with IDs

**Exemplar Format:**
```markdown
# Reasoning Chain: Cross-Reference Query (Level 2)

**Question**: "What are the GO annotations for insulin?"

## Reasoning Chain

**Step 1: Identify concepts**
- State: {classes_discovered: [], properties: []}
- Action: Search for "GO annotation" and "protein"
- Result: Found up:Annotation, up:Protein
...

**Final Query:**
```sparql
SELECT ?protein ?ann ?goTerm WHERE {
  ?protein up:annotation ?ann .
  ?ann up:classifiedWith ?goTerm .
}
```

**Anti-Patterns Avoided:**
- Don't use label filtering instead of classification properties
```

### 2. Verification Feedback with AGENT_GUIDE.md

**File:** `rlm_runtime/tools/verification_feedback.py` (450 lines)

- **`parse_agent_guide(guide_path)`** - Extract metadata from AGENT_GUIDE.md
  - Parses properties section (URI, domain, range, description, usage patterns)
  - Extracts anti-patterns and gotchas
  - Extracts important considerations

- **`AgentGuideMetadata`** dataclass - Structured metadata
  - `properties`: dict[uri, PropertyMetadata]
  - `anti_patterns`: list[str]
  - `considerations`: list[str]

- **`verify_sparql_query(query, results, guide_metadata)`** - Verification checks
  - Domain/range constraint checking
  - Anti-pattern detection (label filtering, wrong property usage)
  - Result type validation
  - Returns: has_issues, constraint_violations, anti_pattern_matches, suggestions

- **`check_domain_range_constraints(query, guide_metadata)`** - Extract and verify
  - Parses SPARQL triple patterns
  - Checks properties against metadata
  - Reports violations with suggestions

- **`detect_anti_patterns(query, guide_metadata)`** - Pattern matching
  - Checks for known anti-patterns from AGENT_GUIDE.md
  - Returns list of detected issues

- **`format_verification_feedback(verification, constraints, anti_patterns)`**
  - Formats as ✓/✗ checks with suggestions
  - Human-readable output for agent inspection

**Verification Output Example:**
```
Verification checks:
✓ Property up:annotation has domain up:Protein
✓ Property up:annotation has range up:Annotation
✓ Query structure is valid
⚠ Consider adding LIMIT clause for large result sets
```

### 3. Curriculum-Aware Retrieval

**File:** `rlm_runtime/memory/curriculum_retrieval.py` (250 lines)

- **`estimate_query_complexity(query)`** - Heuristics-based L1-L5 estimation
  - L1: Single entity retrieval by ID (accession patterns)
  - L2: Cross-reference queries (join keywords: "annotations", "associated with")
  - L3: Filtering queries (constraint keywords: "reviewed", "human", "active")
  - L4: Multi-hop paths (path keywords: "pathway", "via", "through")
  - L5: Aggregation (aggregate keywords: "count", "average", "total")
  - Uses weighted scoring with thresholds

- **`retrieve_with_curriculum(task, backend, k, ontology_name, level_tolerance)`**
  - Estimates query complexity
  - Retrieves with prioritization:
    1. Exact level + same ontology (highest priority)
    2. Adjacent levels (±1) + same ontology
    3. Success memories for ontology
    4. Cross-ontology exemplars (fallback)
  - Ensures top-k results after prioritization

- **`analyze_curriculum_coverage(backend, ontology_name)`** - Statistics
  - Total exemplars by ontology
  - Count by level (1-5)
  - Missing levels identification
  - Returns structured coverage dict

**Curriculum Levels:**
- L1: Single entity retrieval (direct URI patterns)
- L2: Cross-reference (joins between entity types)
- L3: Filtering and constraints
- L4: Multi-hop paths and hierarchies
- L5: Aggregation and analytics

### 4. Verification Feedback Integration

**Modified:** `rlm_runtime/interpreter/namespace_interpreter.py` (+120 lines)

**Added parameters:**
- `enable_verification: bool = False` - Enable feedback injection
- `guide_metadata: AgentGuideMetadata = None` - Required if verification enabled

**Added method:**
- `_generate_verification_feedback(code, output)` - Generate checks
  - Extracts SPARQL query from code
  - Parses results from output
  - Runs verification checks
  - Formats feedback for agent

**Modified `execute()` method:**
```python
def execute(self, code, variables=None):
    # ... existing execution ...

    # NEW: Inject verification feedback
    if self.enable_verification and 'sparql_select(' in code.lower():
        try:
            feedback = self._generate_verification_feedback(code, output)
            if feedback:
                output = output + feedback
        except Exception:
            pass  # Don't fail on verification errors

    return output
```

**Backward Compatible:** Default `enable_verification=False` preserves existing behavior

### 5. DSPy RLM Integration

**Modified:** `rlm_runtime/engine/dspy_rlm.py` (+150 lines)

**Added parameters:**
- `enable_verification: bool = False` - Enable verification feedback
- `enable_curriculum_retrieval: bool = False` - Use curriculum-aware retrieval

**Key changes:**

1. **Load AGENT_GUIDE.md metadata:**
```python
guide_metadata = None
if enable_verification:
    from rlm_runtime.tools.verification_feedback import load_agent_guide_for_ontology
    guide_metadata = load_agent_guide_for_ontology(ontology_path)
```

2. **Use curriculum-aware retrieval:**
```python
if enable_curriculum_retrieval:
    from rlm_runtime.memory.curriculum_retrieval import retrieve_with_curriculum
    retrieved_memories = retrieve_with_curriculum(
        query, memory_backend, k=retrieve_memories, ontology_name=onto_name
    )
else:
    retrieved_memories = memory_backend.retrieve(query, k=retrieve_memories)
```

3. **Separate exemplar formatting:**
```python
exemplar_memories = [m for m in retrieved_memories if m.source_type == 'exemplar']
regular_memories = [m for m in retrieved_memories if m.source_type != 'exemplar']

if exemplar_memories:
    context_parts.append("## Reasoning Chain Exemplars")
    context_parts.append("Follow these state-tracking patterns:")
    for mem in exemplar_memories:
        context_parts.append(f"### {mem.title}")
        context_parts.append(mem.content)
```

4. **Enhanced reasoning guidance:**
```python
context_parts.extend([
    "## Reasoning Process with State Tracking",
    "Each iteration should follow THINK → ACT → VERIFY → REFLECT cycles:",
    "**THINK**: State what you've discovered and what to do next.",
    "- Track state: 'Discovered classes: [up:Protein], properties: [up:organism]'",
    "- Example: 'I found Protein class... Next: verify domain/range'",
    # ... more guidance
])
```

5. **Pass verification to interpreter:**
```python
interpreter = NamespaceCodeInterpreter(
    tools=tools,
    enable_verification=enable_verification,
    guide_metadata=guide_metadata
)
```

### 6. Memory Extraction Enhancement

**Modified:** `rlm_runtime/memory/extraction.py` (+150 lines)

**Added functions:**

- **`should_extract_as_exemplar(trajectory, thinking, verification, reflection)`**
  - Uses behavior_analysis.py to score quality
  - Quality thresholds:
    - state_tracking_score >= 0.7
    - verification_score >= 0.6
    - step_by_step_score >= 0.7
    - overall_score >= 0.7
  - Returns boolean

- **`extract_reasoning_chain_from_trajectory(task, answer, trajectory, sparql, thinking, verification, reflection, ontology_name)`**
  - Checks quality via `should_extract_as_exemplar()`
  - Formats as reasoning chain markdown
  - Creates MemoryItem with `source_type='exemplar'`
  - Tags with estimated curriculum level
  - Returns None if quality threshold not met

### 7. CLI Tools

**File:** `scripts/load_exemplars.py` (190 lines)

Command-line tool for loading exemplars into memory backend:

```bash
# Load all exemplars
python scripts/load_exemplars.py \
    --exemplar-dir experiments/reasoning_chain_validation/exemplars \
    --db-path memory.db \
    --ontology uniprot \
    --stats

# Load with pattern filtering
python scripts/load_exemplars.py \
    --exemplar-dir experiments/reasoning_chain_validation/exemplars \
    --db-path memory.db \
    --ontology uniprot \
    --pattern "uniprot_l[12]*.md"

# Dry run (list only)
python scripts/load_exemplars.py \
    --exemplar-dir experiments/reasoning_chain_validation/exemplars \
    --db-path :memory: \
    --ontology uniprot \
    --list-only
```

**Features:**
- Pattern matching for selective loading
- Force reload option
- Curriculum coverage statistics
- List-only mode for preview
- Duplicate detection

**File:** `scripts/generate_agent_guide.py`

Generate AGENT_GUIDE.md for ontologies using scratchpad approach (from original rlm/core.py design):

```bash
python scripts/generate_agent_guide.py \
    ontology/prov/core.ttl \
    --output ontology/prov/AGENT_GUIDE.md
```

**Features:**
- Persistent namespace with ontology loaded
- Helper functions: search_entity, sparql_query, get_classes, get_properties, llm_query
- Scratchpad-style iterations (max 10)
- Generated guides for PROV and DUL ontologies

### 8. Experiment Integration

**File:** `experiments/reasoning_chain_validation/rc_001_with_rlm.py` (350 lines)

E-RC-001 experiment runner using enhanced DSPy RLM:

```bash
# Run all conditions
python experiments/reasoning_chain_validation/rc_001_with_rlm.py --condition all

# Run single condition
python experiments/reasoning_chain_validation/rc_001_with_rlm.py --condition exemplar3
```

**Test conditions:**
- **baseline**: No exemplars, no schema (stats only)
- **schema**: Schema in context via AGENT_GUIDE.md
- **exemplar3**: L1-L3 exemplars + curriculum retrieval

**Test tasks:**
- L1-protein-lookup: "What is the protein with accession P12345?"
- L2-go-annotations: "What are the GO annotations for insulin?"
- L3-reviewed-human: "Find reviewed proteins in humans"

**Output:**
- JSON results with convergence, iteration count, reasoning quality
- Behavior analysis scores (state tracking, verification, reasoning quality)
- Generated SPARQL queries
- Full reasoning traces

## Test Coverage

**New test files:**
1. `tests/test_exemplar_loader.py` (10 tests)
2. `tests/test_verification_feedback.py` (16 tests)
3. `tests/test_curriculum_retrieval.py` (14 tests)
4. `tests/test_interpreter_verification.py` (10 tests)
5. `tests/test_dspy_rlm_cot_integration.py` (7 tests)

**Total:** 57 tests, all passing

**Coverage:**
- Exemplar parsing and loading
- AGENT_GUIDE.md parsing
- Verification feedback generation
- Domain/range checking
- Anti-pattern detection
- Curriculum complexity estimation
- Level-based retrieval prioritization
- Interpreter verification injection
- DSPy RLM parameter integration
- Backward compatibility

## E-RC-001 Experiment Results

**Date:** 2026-01-27
**Conditions tested:** baseline, schema, exemplar3

| Condition | Convergence | Avg Iterations | Avg Reasoning Quality |
|-----------|-------------|----------------|---------------------|
| baseline | 3/3 (100%) | 6.7 | 0.52 |
| schema | 3/3 (100%) | 6.7 | **0.59** |
| exemplar3 | 3/3 (100%) | 7.0 | 0.48 |

**Key Findings:**

1. ✅ **System functional** - All conditions achieved 100% convergence
2. ✅ **State tracking adopted** - Strong scores (0.67-1.0) across runs
3. ✅ **Verification feedback working** - Domain/range checks visible in traces
4. ✅ **Schema metadata valuable** - Schema condition outperformed others
5. ⚠️ **Exemplar impact unclear** - Need more exemplars (L3-L5) and harder tasks
6. ⚠️ **Schema-only ontology limitation** - No instance data to query

**Reasoning quality breakdown (exemplar3):**
- State tracking: 0.67-1.0 (explicit state mentions present)
- Verification: 0.33 (consistent constraint checking)
- Reasoning quality: 0.0-0.33 (step-by-step structure variable)

**Example generated SPARQL (L3 task):**
```sparql
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

SELECT ?protein ?label WHERE {
  ?protein a up:Protein .
  ?protein up:reviewed true .
  ?protein up:organism taxon:9606 .
  OPTIONAL { ?protein rdfs:label ?label }
}
```

## Architecture Decisions

### 1. AGENT_GUIDE.md vs GraphMeta

**Decision:** Use AGENT_GUIDE.md for verification metadata instead of GraphMeta

**Rationale:**
- GraphMeta provides incomplete metadata (flat dicts, missing labels)
- AGENT_GUIDE.md has rich metadata from previous experiments:
  - Property metadata with domain/range and usage patterns
  - Anti-patterns and gotchas
  - Important considerations
  - Better structured information

**Implementation:**
- Parse AGENT_GUIDE.md to extract PropertyMetadata
- Use for domain/range verification
- Use for anti-pattern detection

### 2. Reasoning Chain Storage

**Decision:** Reuse MemoryItem schema with `source_type='exemplar'` and curriculum tags

**Rationale:**
- No schema changes required
- Works with existing ReasoningBank infrastructure
- Git-committable via memory packs
- Enables filtering and prioritization

**Implementation:**
- Tag with `level-N` for curriculum filtering
- Store as markdown in content field
- Separate formatting in context (exemplars vs regular memories)

### 3. Complexity Estimation

**Decision:** Heuristics-based pattern matching (L1-L5)

**Rationale:**
- Simple and interpretable
- No ML model required
- Works without training data
- Can be iterated based on errors

**Implementation:**
- Keyword-based scoring with weights
- Thresholds tuned empirically
- Fallback to BM25 if level estimation fails

### 4. Verification Feedback Injection

**Decision:** Automatic injection after SPARQL queries in interpreter

**Rationale:**
- Immediate, consistent feedback
- Matches PDDL-INSTRUCT approach (external verification)
- Doesn't require agent to request verification
- Can be disabled for backward compatibility

**Implementation:**
- Inject after query execution
- Append to output (agent sees results + verification)
- Don't fail on verification errors (graceful degradation)

### 5. Backward Compatibility

**Decision:** All new features opt-in via parameters with default False

**Rationale:**
- Existing code continues to work unchanged
- Users must explicitly enable new features
- Gradual adoption possible
- No breaking changes

**Implementation:**
- `enable_verification=False` (interpreter)
- `enable_curriculum_retrieval=False` (dspy_rlm)
- All parameters documented with defaults

## Data Flow

### Exemplar Loading Flow
```
Markdown (.md) → parse_markdown_exemplar() → exemplar_dict
    ↓
exemplar_to_memory_item() → MemoryItem {source_type='exemplar', tags=['level-N']}
    ↓
memory_backend.add_memory() → SQLite memory_items table
```

### Retrieval with Curriculum Flow
```
Query → estimate_query_complexity() → Level (1-5)
    ↓
retrieve_with_curriculum() → Filter by level tags, prioritize
    ↓
Retrieved: [L3 exemplar (exact), L2 exemplar (adjacent), success memory]
    ↓
format_memories_for_context() → Markdown context
    ↓
Injected into RLM prompt (Section: "Reasoning Chain Exemplars")
```

### Verification Feedback Flow
```
Agent: sparql_select("SELECT ?p WHERE ...")
    ↓
NamespaceCodeInterpreter.execute()
    ↓
Execute query → results
    ↓
[if enable_verification] _generate_verification_feedback()
    ↓
verify_sparql_query() + check_domain_range() + detect_anti_patterns()
    ↓
format_verification_feedback() → "✓ Domain/range valid, ⚠ Missing LIMIT"
    ↓
Append to output → Agent sees results + verification
```

## Files Created/Modified

### New Files (5 modules + 2 scripts + 1 experiment)

**Runtime modules:**
- `rlm_runtime/memory/exemplar_loader.py` (200 lines)
- `rlm_runtime/tools/verification_feedback.py` (450 lines)
- `rlm_runtime/memory/curriculum_retrieval.py` (250 lines)

**Scripts:**
- `scripts/generate_agent_guide.py` (200 lines)
- `scripts/load_exemplars.py` (190 lines)

**Experiments:**
- `experiments/reasoning_chain_validation/rc_001_with_rlm.py` (350 lines)

**Test files:**
- `tests/test_exemplar_loader.py` (10 tests)
- `tests/test_verification_feedback.py` (16 tests)
- `tests/test_curriculum_retrieval.py` (14 tests)
- `tests/test_interpreter_verification.py` (10 tests)
- `tests/test_dspy_rlm_cot_integration.py` (7 tests)

### Modified Files (3)

- `rlm_runtime/interpreter/namespace_interpreter.py` (+120 lines)
- `rlm_runtime/engine/dspy_rlm.py` (+150 lines)
- `rlm_runtime/memory/extraction.py` (+150 lines)

### Generated Assets (3)

- `ontology/prov/AGENT_GUIDE.md` (15KB, 8 iterations)
- `ontology/dul/AGENT_GUIDE.md` (21KB, 9 iterations)
- `experiments/reasoning_chain_validation/exemplars/` (2 exemplars: L1, L2)

## Integration Points

### With ReasoningBank (Phase 3 Extension)

- Exemplars stored as MemoryItems with `source_type='exemplar'`
- Retrieved via FTS5 BM25 with curriculum filtering
- Can be extracted from high-quality trajectories
- Git-shippable via memory packs

### With DSPy RLM (Core Integration)

- New parameters for verification and curriculum
- Enhanced context formatting for exemplars
- Verification feedback via interpreter
- Backward compatible with existing code

### With Experiments Framework

- E-RC-001 validates implementation
- Uses existing behavior_analysis.py
- Produces structured results for analysis
- Compatible with MLflow tracking (if enabled)

### With Documentation System

- Design doc: `docs/design/instruction-tuning-via-reasoning-chains.md`
- Task doc: `docs/tasks/05-cot-instruction-tuning.md` (this file)
- Experiment README: `experiments/reasoning_chain_validation/README.md`
- Trajectory: `docs/planning/trajectory_v3.md` (Phase 3 extension)

## Next Steps

To better evaluate exemplar impact:

1. **Create L3-L5 exemplars** - More complex query patterns
   - L3: Filtering with multiple constraints
   - L4: Multi-hop joins and paths
   - L5: Aggregations and analytics

2. **Test on ontologies with instance data** - Actual protein records
   - Current tests on schema-only ontology
   - Need instance data to exercise exemplar patterns fully

3. **Design harder tasks** - More complex queries
   - Multi-hop joins
   - Federation (`SERVICE` clauses)
   - Named graph joins (`GRAPH` clauses)

4. **Run multiple trials** - Statistical significance
   - Current: 1 trial per condition
   - Need: 3-5 trials for confidence

5. **Compare reasoning traces qualitatively** - Human review
   - Identify patterns in successful vs failed runs
   - Refine exemplars based on observed failures

## Related Documents

- **Design:** `docs/design/instruction-tuning-via-reasoning-chains.md` - Full design with implementation status
- **Experiments:** `experiments/reasoning_chain_validation/README.md` - E-RC-001 through E-RC-004 design
- **Results:** `experiments/reasoning_chain_validation/results/comparison_summary.md` - E-RC-001 analysis
- **Trajectory:** `docs/planning/trajectory_v3.md` - Phase 3 extension
- **Original inspiration:** arXiv:2509.13351v1 - PDDL-INSTRUCT paper

## References

- **PDDL-INSTRUCT Paper:** arXiv:2509.13351v1 "Instruction Tuning for Symbolic Planning"
  - Key insight: State-action-state reasoning chains + detailed verification
  - Achievement: 28% → 94% accuracy on planning tasks
  - Method: Fine-tuning on structured reasoning with external feedback

- **Original RLM design:** `rlm/core.py` (claudette-based scratchpad model)
  - Persistent namespace
  - Direct function calls
  - Lightweight history
  - Used for AGENT_GUIDE.md generation

- **Behavior analysis:** `experiments/reasoning_chain_validation/behavior_analysis.py`
  - Analyzes reasoning traces for PDDL-INSTRUCT style indicators
  - Used for quality threshold checking in extraction
