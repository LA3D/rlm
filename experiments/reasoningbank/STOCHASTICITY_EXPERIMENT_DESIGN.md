# Stochasticity in LLM Trajectories: Experiment Design

**Date**: 2026-02-03
**Background**: Investigating how to effectively sample different regions of "reasoning space" in LLM agent trajectories, analogous to different random seeds sampling different regions of phase space in molecular dynamics.

---

## The Problem

Observed in smoke test:
- **Simple tasks**: Identical trajectories despite temperature=0.7
- **Complex tasks**: Divergence only at later iterations (9-12)

**Question**: How do we reliably generate diverse trajectories for the same task?

---

## Analogy to Molecular Dynamics

| MD Concept | LLM Analog | Notes |
|------------|------------|-------|
| Random seed | API seed parameter | Anthropic has beta support |
| Temperature | Temperature parameter | Only helps if distribution is flat |
| Initial conditions | Prompt/context | Changes the entire trajectory |
| Phase space | Reasoning space | The space of possible solution paths |
| Energy landscape | Probability landscape | Peaked = deterministic, flat = stochastic |

**Key insight**: Temperature doesn't CREATE variation, it PERMITS variation where uncertainty exists.

---

## Proposed Methods to Induce Trajectory Diversity

### Method 1: API Seed Parameter

```python
# Explicitly set different seeds per rollout
lm = dspy.LM(
    'anthropic/claude-sonnet-4-5-20250929',
    temperature=0.7,
    seed=rollout_id  # Different seed per rollout
)
```

**Pros**: Direct control over randomness
**Cons**: Anthropic's seed is "best effort", may not guarantee variation

### Method 2: Prompt Perturbation (Recommended)

Change the INPUT rather than just the sampling:

```python
PERTURBATION_STRATEGIES = [
    # Strategy A: Rephrase query
    lambda q: rephrase_query(q),

    # Strategy B: Add task identifier
    lambda q: f"[TaskID: {random_id()}] {q}",

    # Strategy C: Reorder context sections
    lambda q, ctx: shuffle_context_sections(ctx) + q,

    # Strategy D: Add thinking prompt
    lambda q: f"Think step by step. {q}",

    # Strategy E: Add random prefix
    lambda q: f"Rollout {rollout_id}. {q}",
]
```

**Pros**:
- Changes the model's internal state
- More like changing initial conditions in MD
- Well-supported in literature (Self-Consistency, etc.)

**Cons**:
- May affect task semantics if not careful
- Need to validate perturbations don't change task meaning

### Method 3: Context Shuffling

Reorder elements within the L0/L1 context:

```python
def shuffle_ontology_context(sense_card: str) -> str:
    """Shuffle the order of predicates/classes in sense card."""
    sections = parse_sense_card_sections(sense_card)
    random.shuffle(sections)
    return format_sense_card(sections)
```

**Rationale**: The order of information in context affects attention patterns and thus reasoning paths.

### Method 4: Few-Shot Example Shuffling

If using examples in context:

```python
def get_shuffled_examples(examples: list, seed: int) -> list:
    """Return examples in different order per rollout."""
    rng = random.Random(seed)
    shuffled = examples.copy()
    rng.shuffle(shuffled)
    return shuffled
```

---

## Experimental Design

### Experiment S1: Baseline Variance

**Goal**: Measure inherent variance with current setup (no interventions)

```
Task: 10 tasks from uniprot_subset_tasks.json
Rollouts: k=10 per task
Configuration: temperature=0.7, no seed, no perturbation
Metrics:
  - Trajectory similarity (Jaccard on tool sequences)
  - Divergence point (first iteration where paths differ)
  - Outcome variance (success rate per task)
```

### Experiment S2: Seed Parameter Effect

**Goal**: Test if explicit seed creates different trajectories

```
Task: 5 representative tasks
Rollouts: k=5 per task
Condition A: seed=None (current)
Condition B: seed=rollout_id (explicit different seeds)
Compare: Trajectory similarity between conditions
```

### Experiment S3: Prompt Perturbation Effect

**Goal**: Test if prompt perturbation creates meaningful diversity

```
Task: 5 representative tasks
Rollouts: k=5 per task
Perturbations:
  - P0: Original (no change)
  - P1: Add "[Attempt N]" prefix
  - P2: Rephrase query
  - P3: Shuffle context order
  - P4: Add "Think differently than before"
Compare:
  - Trajectory similarity
  - Solution diversity (different SPARQL approaches)
  - Success rate (perturbations shouldn't hurt)
```

### Experiment S4: Context Shuffling Effect

**Goal**: Test if context order affects reasoning paths

```
Task: 5 representative tasks
Rollouts: k=5 per task
Condition A: Fixed context order
Condition B: Shuffled context (different per rollout)
Compare: Trajectory similarity, solution paths
```

---

## Implementation Plan

### Phase 1: Add Seed Support

```python
# Modify run_uniprot.py
def run_uniprot(
    task: str,
    ont_path: str,
    cfg: Cfg,
    mem: MemStore|None = None,
    endpoint: str = 'uniprot',
    max_iters: int = 12,
    max_calls: int = 25,
    temperature: float = 0.0,
    seed: int|None = None,  # ADD: explicit seed
    verbose: bool = True,
    ...
) -> Result:

    # Configure LM with seed
    lm_kwargs = {'temperature': temperature}
    if seed is not None:
        lm_kwargs['seed'] = seed

    lm = dspy.LM(
        'anthropic/claude-sonnet-4-5-20250929',
        api_key=os.environ['ANTHROPIC_API_KEY'],
        **lm_kwargs
    )
```

### Phase 2: Add Prompt Perturbation

```python
# Add to phase1_uniprot.py
def perturb_query(query: str, rollout_id: int, strategy: str = 'prefix') -> str:
    """Apply perturbation strategy to query."""
    if strategy == 'prefix':
        return f"[Attempt {rollout_id}] {query}"
    elif strategy == 'rephrase':
        return rephrase_with_llm(query, rollout_id)
    elif strategy == 'thinking':
        prompts = [
            "Think step by step.",
            "Consider multiple approaches.",
            "Be thorough in your exploration.",
            "Try a different strategy.",
            "Focus on the key constraints.",
        ]
        return f"{prompts[rollout_id % len(prompts)]} {query}"
    else:
        return query
```

### Phase 3: Add Trajectory Similarity Metrics

```python
def trajectory_similarity(traj1: list, traj2: list) -> float:
    """Compute Jaccard similarity of tool call sequences."""
    tools1 = set(t['tool'] for t in traj1)
    tools2 = set(t['tool'] for t in traj2)

    intersection = len(tools1 & tools2)
    union = len(tools1 | tools2)

    return intersection / union if union > 0 else 1.0

def find_divergence_point(traj1: list, traj2: list) -> int:
    """Find first iteration where trajectories diverge."""
    for i, (t1, t2) in enumerate(zip(traj1, traj2)):
        if t1['code'] != t2['code']:
            return i
    return min(len(traj1), len(traj2))
```

---

## Success Criteria

1. **Diversity**: Different rollouts should produce measurably different trajectories
   - Target: Average pairwise Jaccard < 0.8 (not too similar)

2. **Validity**: Perturbations shouldn't hurt success rate
   - Target: Perturbed success rate >= 90% of baseline

3. **Coverage**: Different rollouts should explore different solution strategies
   - Target: At least 2 distinct SPARQL patterns per task (when possible)

---

## Connection to ReasoningBank Methodology

The ReasoningBank paper uses:
- **temperature=0.7** for generation
- **k=3-5 parallel trajectories** for MaTTS
- **Self-contrast** across trajectories

Our investigation suggests that temperature alone may not be sufficient for simple tasks. **Prompt perturbation could enhance MaTTS** by ensuring diverse trajectories even on simpler tasks.

---

## References

- Wang et al., "Self-Consistency Improves Chain of Thought Reasoning in Language Models" (2023)
- ReasoningBank paper §3.3 on MaTTS methodology
- Anthropic API documentation on seed parameter (beta)
- https://aclanthology.org/2025.findings-emnlp.594.pdf - Stochastic LLM Evaluation
- https://unstract.com/blog/understanding-why-deterministic-output-from-llms-is-nearly-impossible/

---

## Next Steps

1. [ ] Implement seed parameter support in run_uniprot.py
2. [ ] Implement prompt perturbation strategies
3. [ ] Run Experiment S1 (baseline variance measurement)
4. [ ] Run Experiment S3 (prompt perturbation effect)
5. [ ] Analyze results and decide on best approach for MaTTS
