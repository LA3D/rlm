# Reasoning Chain Validation Experiments

**Created**: 2026-01-26
**Status**: Proposed
**Purpose**: Validate if PDDL-INSTRUCT style reasoning chains improve SPARQL query construction

## Research Questions

These experiments address the core questions from the PDDL-INSTRUCT inspired approach:

1. **E-RC-001**: Do reasoning chain exemplars improve query construction accuracy?
2. **E-RC-002**: Which architecture best supports state tracking during reasoning?
3. **E-RC-003**: Does detailed feedback improve learning from failures?
4. **E-RC-004**: Can we reliably detect correct vs incorrect reasoning patterns?

## Experiment Design Philosophy

Following the AGENT_GUIDE experiments pattern:
- Multiple conditions compared on same task
- Same ontology (UniProt) for direct comparison
- LLM judge + human validation for quality assessment
- Clear metrics: accuracy, iterations, behavior indicators

---

## E-RC-001: Reasoning Chain Exemplars vs No Examples

**Question**: Do PDDL-INSTRUCT style reasoning chain examples improve query construction?

### Design

| Condition | Description |
|-----------|-------------|
| **Baseline** | Current AGENT_GUIDE.md + GraphMeta summary |
| **Schema+** | Baseline + explicit domain/range constraints |
| **Exemplar-3** | Baseline + 3 reasoning chain exemplars |
| **Exemplar-5** | Baseline + 5 reasoning chain exemplars |

### Reasoning Chain Exemplar Format

```markdown
## Reasoning Chain: Find proteins with disease annotations

**Question**: "What proteins are associated with cancer?"

**Step 1: Identify concepts**
- Query asks for: proteins with disease associations
- State: {classes_known: [], properties_known: [], patterns_tried: []}
- Action: Search for "protein" and "disease" in ontology
- Result: Found up:Protein, up:Disease_Annotation
- Verification: Both classes exist ✓

**Step 2: Find connecting property**
- State: {classes_known: [up:Protein, up:Disease_Annotation], ...}
- Action: Find property linking Protein → Annotation
- Result: up:annotation (domain: up:Protein, range: up:Annotation)
- Verification: Domain/range compatible ✓

**Step 3: Construct pattern**
- State: {classes_known: [...], properties_known: [up:annotation], ...}
- Action: Build triple pattern
- Pattern: `?protein up:annotation ?ann . ?ann a up:Disease_Annotation .`
- Verification: Pattern consistent with constraints ✓

**Step 4: Add disease filter**
- Action: Add rdfs:label filter for "cancer"
- Pattern: `?ann rdfs:seeAlso ?disease . ?disease rdfs:label ?label . FILTER(CONTAINS(LCASE(?label), "cancer"))`
- Verification: Execute with LIMIT 5 ✓

**Final Query**:
```sparql
SELECT ?protein ?label WHERE {
  ?protein a up:Protein ;
           up:annotation ?ann .
  ?ann a up:Disease_Annotation ;
       rdfs:seeAlso ?disease .
  ?disease rdfs:label ?label .
  FILTER(CONTAINS(LCASE(?label), "cancer"))
} LIMIT 100
```

**Anti-pattern avoided**: Don't query `?protein a up:Disease_Annotation` - proteins aren't annotations.
```

### Test Tasks (5 tasks, increasing complexity)

1. **L1-Basic**: "What is the protein P12345?"
2. **L2-Cross-ref**: "What are the GO annotations for insulin?"
3. **L3-Filter**: "Find human proteins with kinase activity"
4. **L4-Multi-hop**: "What pathways involve proteins annotated with diabetes?"
5. **L5-Complex**: "Find E. coli K-12 genes encoding enzymes in glycolysis"

### Metrics

| Metric | What it Measures |
|--------|------------------|
| **Pass Rate** | % of tasks with correct SPARQL + valid results |
| **Iteration Count** | Number of RLM iterations to converge |
| **State Tracking** | Does reasoning mention state transitions? (0/1) |
| **Verification Steps** | Count of explicit verification statements |
| **Anti-pattern Avoidance** | Did it avoid known anti-patterns? (0/1) |

### Expected Outcome

If promising: Exemplar conditions should show:
- Higher pass rate than baseline (especially L4-L5)
- Lower iteration count (fewer exploratory steps)
- Explicit state tracking in reasoning
- More verification statements

---

## E-RC-002: Architecture Comparison for State Tracking

**Question**: Which architecture best supports PDDL-INSTRUCT style state tracking?

### Design

| Architecture | State Mechanism | Tools |
|--------------|-----------------|-------|
| **DSPy ReAct** | Implicit in trajectory | search, sparql, describe |
| **DSPy RLM** | Namespace variables | search, sparql + code |
| **Scratchpad** | Explicit `ns` dict | Direct functions |
| **Structured-State** | Explicit state schema | State-aware tools |

### Structured-State Architecture (New)

This is the key innovation to test - explicit PDDL-style state tracking:

```python
class QueryState(BaseModel):
    """Explicit state for query construction."""
    classes_discovered: list[str] = []
    properties_discovered: list[str] = []
    constraints_verified: list[str] = []  # "up:annotation domain=up:Protein"
    patterns_tried: list[str] = []
    current_query: str = ""
    execution_results: list[str] = []

class StateAwareAction(BaseModel):
    """Action with preconditions and effects."""
    action_type: Literal["explore_class", "find_property", "add_pattern", "verify_constraint", "execute_query"]
    target: str
    preconditions: list[str]  # What must be true in state
    expected_effects: list[str]  # What changes in state
    reasoning: str
```

### Test Protocol

Same 5 tasks as E-RC-001, run with each architecture:
- Provide same 5 exemplar reasoning chains to all
- Measure state tracking behavior

### Behavior Indicators

| Indicator | How to Measure |
|-----------|----------------|
| **Explicit State References** | Grep for "state", "discovered", "verified" in reasoning |
| **Precondition Checking** | Does agent verify constraints before using them? |
| **State Progression** | Does state grow monotonically (no regression)? |
| **Backtracking** | Does agent recognize when to abandon failed patterns? |

### Expected Outcome

If state tracking matters:
- Scratchpad and Structured-State should outperform ReAct/RLM on complex tasks
- Explicit state should correlate with higher pass rate
- Structured-State should show cleanest state progression

---

## E-RC-003: Detailed vs Binary Feedback Impact

**Question**: Does detailed execution feedback improve query construction? (PDDL-INSTRUCT key finding)

### Design

| Feedback Level | What Agent Sees After Query Execution |
|----------------|--------------------------------------|
| **None** | No execution, just construct query |
| **Binary** | "Query succeeded" or "Query failed" |
| **Results** | "Returned 47 rows" + sample row |
| **Detailed** | Results + type analysis + constraint verification |

### Detailed Feedback Example

```
Query executed successfully.

Results: 47 rows returned

Sample row:
  ?protein = <http://purl.uniprot.org/uniprot/P12345>
  ?label = "Insulin"

Type verification:
  ✓ ?protein: 100% are up:Protein (expected)
  ✓ ?ann: 100% are up:Disease_Annotation (expected)

Constraint check:
  ✓ up:annotation domain verified (all subjects are up:Protein)
  ✓ up:annotation range verified (all objects are up:Annotation)

Potential issues:
  - None detected
```

### Test Tasks

Focus on tasks where feedback matters most - those with subtle errors:
1. **Type confusion**: Query that returns results but wrong types
2. **Empty results**: Valid syntax but no matches (wrong pattern)
3. **Partial match**: Gets some results but misses others
4. **Redundant pattern**: Works but has unnecessary complexity

### Metrics

| Metric | What it Measures |
|--------|------------------|
| **Correction Rate** | After bad query, how often does agent correct? |
| **Correction Speed** | Iterations to correct after feedback |
| **Over-correction** | Does agent "fix" working queries? |
| **Learning Transfer** | Does fixing one error prevent similar errors? |

### Expected Outcome

Based on PDDL-INSTRUCT (49% binary → 64% detailed):
- Detailed feedback should show ~30% higher correction rate
- Binary feedback often leads to random changes rather than targeted fixes

---

## E-RC-004: Behavior Analysis Validation

**Question**: Can we reliably detect if the agent is reasoning correctly?

This is a meta-experiment - testing the behavior analysis framework itself.

### Design

Create 10 reasoning traces:
- 5 "good" traces (correct reasoning, successful queries)
- 5 "bad" traces (plausible but flawed reasoning)

### Good Trace Example (abbreviated)

```json
{
  "question": "Find proteins with kinase activity",
  "trace": [
    {"step": 1, "action": "search 'kinase'", "result": "found GO:0016301 kinase activity"},
    {"step": 2, "action": "search 'classifiedWith'", "result": "found up:classifiedWith property"},
    {"step": 3, "action": "verify domain/range", "result": "domain=up:Protein, range includes GO terms ✓"},
    {"step": 4, "action": "construct pattern", "result": "?p up:classifiedWith <GO:0016301>"},
    {"step": 5, "action": "execute", "result": "1,247 results, verified up:Protein types"}
  ],
  "expected_indicators": {
    "state_progression": true,
    "verification_present": true,
    "constraint_checking": true,
    "anti_pattern_avoided": true
  }
}
```

### Bad Trace Example (plausible but wrong)

```json
{
  "question": "Find proteins with kinase activity",
  "trace": [
    {"step": 1, "action": "search 'kinase protein'", "result": "found up:Protein"},
    {"step": 2, "action": "construct pattern", "result": "?p a up:Protein . ?p rdfs:label ?l . FILTER(CONTAINS(?l, 'kinase'))"},
    {"step": 3, "action": "execute", "result": "5,432 results"}
  ],
  "expected_indicators": {
    "state_progression": false,  // Jumped straight to pattern
    "verification_present": false,  // No verification
    "constraint_checking": false,  // Didn't check GO relationship
    "anti_pattern_avoided": false  // Used label filter instead of classification
  }
}
```

### Analysis Framework

```python
def analyze_trace(trace: dict) -> dict:
    """Analyze reasoning trace for PDDL-INSTRUCT style behavior."""

    indicators = {
        "state_progression": check_state_progression(trace),
        "verification_present": check_verification_steps(trace),
        "constraint_checking": check_constraint_checking(trace),
        "precondition_checking": check_preconditions(trace),
        "anti_pattern_avoidance": check_anti_patterns(trace),
        "explicit_reasoning": check_explicit_reasoning(trace)
    }

    score = sum(indicators.values()) / len(indicators)

    return {
        "indicators": indicators,
        "score": score,
        "classification": "good" if score >= 0.6 else "bad"
    }
```

### Metrics

| Metric | Target |
|--------|--------|
| **Precision** | % of "good" classifications that are actually good |
| **Recall** | % of good traces correctly classified as good |
| **F1 Score** | Harmonic mean |
| **False Positive Rate** | Bad traces misclassified as good |

### Expected Outcome

If behavior analysis is reliable:
- Should achieve >80% F1 on distinguishing good/bad traces
- False positive rate should be <20% (don't reward bad reasoning)

---

## Implementation Plan

### Phase 1: Exemplar Creation (E-RC-001 prep)

1. Create 5 high-quality reasoning chain exemplars for UniProt
2. Cover levels 1-5 of complexity
3. Include explicit state tracking, verification, anti-patterns

### Phase 2: Run E-RC-001

```bash
python experiments/reasoning_chain_validation/rc_001_exemplar_impact.py
```

Compare: Baseline vs Schema+ vs Exemplar-3 vs Exemplar-5

### Phase 3: Run E-RC-002 (if E-RC-001 promising)

```bash
python experiments/reasoning_chain_validation/rc_002_architecture_comparison.py
```

Compare: ReAct vs RLM vs Scratchpad vs Structured-State

### Phase 4: Run E-RC-003 and E-RC-004

These can run in parallel with Phase 3.

---

## Files

```
experiments/reasoning_chain_validation/
├── README.md                      # This file
├── exemplars/
│   ├── uniprot_l1_basic.md       # Level 1 exemplar ✓
│   ├── uniprot_l2_crossref.md    # Level 2 exemplar ✓
│   ├── uniprot_l3_filter.md      # Level 3 exemplar (TODO)
│   ├── uniprot_l4_multihop.md    # Level 4 exemplar (TODO)
│   └── uniprot_l5_complex.md     # Level 5 exemplar (TODO)
├── rc_001_exemplar_impact.py      # E-RC-001 runner ✓
├── rc_002_architecture_comparison.py  # E-RC-002 runner (TODO)
├── rc_003_feedback_impact.py      # E-RC-003 runner (TODO)
├── rc_004_behavior_analysis.py    # E-RC-004 runner (TODO)
├── behavior_analysis.py           # Shared analysis functions ✓
├── analyze_trajectories.py        # Trajectory analysis tool ✓
├── quick_test.py                  # Quick validation test ✓
└── results/
    ├── rc_001_results_*.json      # Experiment results
    ├── experiment_*.jsonl         # Experiment event log
    └── trajectories/              # Full reasoning traces
        ├── *.md                   # Human-readable traces
        └── *.jsonl                # Machine-readable logs
```

## Trajectory Logging

All experiments save comprehensive trajectories for analysis:

### Per-Task Trajectories

Each task generates two files:

1. **Markdown trace** (`{task_id}_{condition}_{timestamp}.md`):
   - Full prompt
   - Complete LLM response
   - Token usage and timing metrics

2. **JSONL event log** (`{task_id}_{condition}_{timestamp}.jsonl`):
   - Structured events (task_start, llm_call, llm_response, task_complete)
   - Timestamps and token counts
   - Machine-readable for programmatic analysis

### Experiment-Level Log

`experiment_{timestamp}.jsonl` tracks:
- Experiment start/complete
- Condition start/complete
- Task completion with pass/fail and behavior scores

### Analyzing Trajectories

```bash
# Analyze all trajectories
python analyze_trajectories.py results/trajectories

# Filter by condition
python analyze_trajectories.py results/trajectories --condition exemplar5

# Filter by task
python analyze_trajectories.py results/trajectories --task L2-crossref

# Save analysis report
python analyze_trajectories.py results/trajectories --output analysis_report.json
```

The analyzer computes:
- Average behavior scores per condition
- Classification breakdown (good/adequate/poor)
- Individual trajectory details
- Indicator presence frequencies

---

## Success Criteria

| Experiment | Success Indicator |
|------------|-------------------|
| **E-RC-001** | Exemplar-5 > 20% better pass rate than Baseline |
| **E-RC-002** | One architecture clearly outperforms on state tracking |
| **E-RC-003** | Detailed feedback > 25% better correction rate |
| **E-RC-004** | Behavior analysis achieves F1 > 0.8 |

If 3/4 succeed, the reasoning chains approach is validated for further investment.

---

## Related Documents

- [ontology-kr-affordances-for-llm-reasoning.md](../../docs/design/ontology-kr-affordances-for-llm-reasoning.md)
- [instruction-tuning-via-reasoning-chains.md](../../docs/design/instruction-tuning-via-reasoning-chains.md)
- [procedural-memory-curriculum.md](../../docs/planning/procedural-memory-curriculum.md)
- [AGENT_GUIDE experiments](../agent_guide_generation/)
