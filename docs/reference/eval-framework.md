# RLM Evaluation Framework

Based on [Anthropic's recommendations for AI agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), this document defines a comprehensive evaluation framework for the RLM (Recursive Language Models) system.

## 1. RLM Agent Characteristics

RLM is a **research-style agent** that:
- Explores RDF ontologies through a REPL loop
- Executes Python code to query and reason about data
- Uses procedural memory to learn from past trajectories
- Produces grounded answers based on retrieved evidence

This means our evals should combine:
- **Groundedness checks** - Is the answer supported by REPL observations?
- **Coverage validation** - Did the agent explore relevant parts of the ontology?
- **Efficiency metrics** - Did it converge without excessive iterations?

---

## 2. Eval Types for RLM

### 2.1 Capability Evals (Target: Low Initial Pass Rate)

Test what the agent CAN accomplish. These start hard and improve over time.

| Eval Category | Description | Initial Target |
|--------------|-------------|----------------|
| Entity Discovery | Find and describe ontology entities | 30-50% pass |
| Hierarchy Navigation | Traverse class/property hierarchies | 20-40% pass |
| Cross-Ontology Queries | Reason across multiple mounted ontologies | 10-30% pass |
| Complex Inference | Multi-step reasoning with SPARQL | 10-20% pass |

### 2.2 Regression Evals (Target: ~100% Pass Rate)

Maintain reliability on solved tasks. Move capability evals here once stable.

| Eval Category | Description | Target |
|--------------|-------------|--------|
| Basic REPL Operations | search_entity, describe_entity work | 100% |
| Memory Operations | mem_add, mem_query execute correctly | 100% |
| Snapshot/Load | Dataset state persists correctly | 100% |
| FINAL_VAR Pattern | Agent terminates with valid answer | 95%+ |

### 2.3 Multi-Turn Evals

Test full RLM loop behavior across iterations.

| Eval Type | Description |
|-----------|-------------|
| Convergence | Does the agent reach FINAL_VAR within N iterations? |
| Memory Influence | Does retrieved memory improve behavior? |
| Error Recovery | Does the agent recover from REPL errors? |

---

## 3. Eval Case Structure

### 3.1 Task Definition (YAML Format)

```yaml
task:
  id: "prov-entity-lookup_001"
  category: "entity_discovery"
  difficulty: "easy"

  # Input
  query: "What is prov:InstantaneousEvent and what are its properties?"
  context:
    ontologies:
      - name: prov
        source: ontology/prov.ttl
    memories: []  # Optional pre-loaded memories

  # Success Criteria
  graders:
    - type: groundedness
      required_evidence:
        - pattern: "InstantaneousEvent"
          source: "describe_entity|search_entity"
    - type: answer_contains
      must_include:
        - "subclass of Event"  # Or similar factual claim
    - type: convergence
      max_iterations: 8
    - type: bounded_output
      max_chars_per_iteration: 2000

  # Trial Configuration
  trials: 5
  pass_threshold: 0.6  # 3/5 must pass
```

### 3.2 Grader Types for RLM

#### Groundedness Grader
Verifies answers are supported by REPL observations.

```python
class GroundednessGrader:
    """Check that final answer cites evidence from REPL."""

    def grade(self, transcript: list[RLMIteration], answer: str) -> dict:
        # Extract all REPL outputs from transcript
        evidence = self._extract_repl_outputs(transcript)

        # Check if key claims in answer appear in evidence
        claims = self._extract_claims(answer)
        grounded_claims = []
        ungrounded_claims = []

        for claim in claims:
            if self._is_supported(claim, evidence):
                grounded_claims.append(claim)
            else:
                ungrounded_claims.append(claim)

        return {
            'passed': len(ungrounded_claims) == 0,
            'groundedness_score': len(grounded_claims) / len(claims),
            'ungrounded_claims': ungrounded_claims
        }
```

#### Convergence Grader
Checks that agent terminates properly.

```python
class ConvergenceGrader:
    """Check agent converged within iteration limit."""

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations

    def grade(self, transcript: list[RLMIteration], answer: str) -> dict:
        converged = answer and answer != "No answer provided"
        within_limit = len(transcript) <= self.max_iterations

        return {
            'passed': converged and within_limit,
            'converged': converged,
            'iterations': len(transcript),
            'within_limit': within_limit
        }
```

#### Evidence Pattern Grader
Checks that specific tools were used to find evidence.

```python
class EvidencePatternGrader:
    """Check that required evidence patterns appear in transcript."""

    def __init__(self, required_patterns: list[dict]):
        self.required_patterns = required_patterns

    def grade(self, transcript: list[RLMIteration], answer: str) -> dict:
        found_patterns = []
        missing_patterns = []

        for pattern in self.required_patterns:
            if self._pattern_in_transcript(pattern, transcript):
                found_patterns.append(pattern)
            else:
                missing_patterns.append(pattern)

        return {
            'passed': len(missing_patterns) == 0,
            'found': found_patterns,
            'missing': missing_patterns
        }
```

#### LLM Rubric Grader
Uses a second LLM to evaluate answer quality.

```python
class LLMRubricGrader:
    """Use LLM to evaluate answer against rubric."""

    def __init__(self, rubric_path: str):
        self.rubric = Path(rubric_path).read_text()

    def grade(self, transcript: list[RLMIteration], answer: str,
              task_query: str) -> dict:
        prompt = f"""Evaluate this agent's answer against the rubric.

Task: {task_query}
Answer: {answer}

Rubric:
{self.rubric}

Return JSON: {{"passed": bool, "score": 0-10, "reasoning": "..."}}"""

        response = llm_query(prompt, {})
        return json.loads(response)
```

---

## 4. Metrics to Track

### 4.1 Primary Metrics

| Metric | Formula | Purpose |
|--------|---------|---------|
| **pass@k** | P(≥1 success in k trials) | Capability measurement |
| **pass^k** | P(all k trials succeed) | Consistency measurement |
| **Iteration Count** | Mean iterations to converge | Efficiency |
| **Groundedness Score** | grounded_claims / total_claims | Answer quality |

### 4.2 Secondary Metrics

| Metric | Description |
|--------|-------------|
| Token Usage | Total tokens per task (input + output) |
| Cost | API cost per successful task |
| Latency | Time to convergence |
| Error Rate | % of iterations with REPL errors |
| Memory Hit Rate | % of runs where memory was retrieved and used |

### 4.3 Metric Calculation

```python
def calculate_pass_at_k(results: list[bool], k: int) -> float:
    """Calculate probability of at least one success in k trials."""
    n = len(results)
    c = sum(results)  # Number of successes

    if n - c < k:
        return 1.0

    # 1 - P(all k failures)
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)

def calculate_pass_power_k(results: list[bool], k: int) -> float:
    """Calculate probability of all k trials succeeding."""
    n = len(results)
    c = sum(results)

    if c < k:
        return 0.0

    return math.comb(c, k) / math.comb(n, k)
```

---

## 5. Eval Implementation

### 5.1 Directory Structure

```
evals/
├── tasks/                    # Task definitions
│   ├── entity_discovery/
│   │   ├── prov_entity_001.yaml
│   │   ├── prov_hierarchy_002.yaml
│   │   └── ...
│   ├── memory_influence/
│   │   └── ...
│   └── regression/
│       └── ...
├── graders/                  # Grader implementations
│   ├── __init__.py
│   ├── groundedness.py
│   ├── convergence.py
│   ├── evidence_pattern.py
│   └── llm_rubric.py
├── rubrics/                  # LLM grading rubrics
│   ├── answer_quality.md
│   ├── code_quality.md
│   └── exploration_quality.md
├── runners/                  # Eval execution
│   ├── __init__.py
│   ├── task_runner.py
│   ├── trial_runner.py
│   └── reporter.py
├── results/                  # Output artifacts
│   ├── transcripts/
│   ├── metrics/
│   └── reports/
└── config.yaml               # Global eval configuration
```

### 5.2 Task Runner

```python
# evals/runners/task_runner.py
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class EvalResult:
    task_id: str
    trial_results: list[dict]
    pass_at_k: float
    pass_power_k: float
    avg_iterations: float
    avg_groundedness: float

class TaskRunner:
    """Run eval tasks with multiple trials."""

    def __init__(self, config_path: Path):
        self.config = yaml.safe_load(config_path.read_text())
        self.graders = self._load_graders()

    def run_task(self, task_path: Path) -> EvalResult:
        task = yaml.safe_load(task_path.read_text())

        # Setup environment
        ns = self._setup_namespace(task)

        # Run trials
        trial_results = []
        for trial in range(task.get('trials', 5)):
            result = self._run_single_trial(task, ns.copy())
            trial_results.append(result)

        # Calculate metrics
        passes = [r['passed'] for r in trial_results]
        k = task.get('trials', 5)

        return EvalResult(
            task_id=task['id'],
            trial_results=trial_results,
            pass_at_k=calculate_pass_at_k(passes, k),
            pass_power_k=calculate_pass_power_k(passes, k),
            avg_iterations=sum(r['iterations'] for r in trial_results) / len(trial_results),
            avg_groundedness=sum(r.get('groundedness', 0) for r in trial_results) / len(trial_results)
        )

    def _run_single_trial(self, task: dict, ns: dict) -> dict:
        """Execute one trial of a task."""
        from rlm.core import rlm_run

        # Run RLM
        answer, iterations = rlm_run(
            task=task['query'],
            ns=ns,
            max_iterations=task.get('max_iterations', 15)
        )

        # Grade with all graders
        grader_results = {}
        overall_pass = True

        for grader_config in task['graders']:
            grader = self._get_grader(grader_config)
            result = grader.grade(iterations, answer)
            grader_results[grader_config['type']] = result
            if not result['passed']:
                overall_pass = False

        return {
            'passed': overall_pass,
            'iterations': len(iterations),
            'answer': answer,
            'grader_results': grader_results,
            'transcript': [asdict(i) for i in iterations]
        }
```

### 5.3 CLI Interface

```python
# evals/cli.py
import click
from pathlib import Path

@click.group()
def cli():
    """RLM Evaluation CLI."""
    pass

@cli.command()
@click.argument('task_pattern', default='*')
@click.option('--trials', '-t', default=5, help='Trials per task')
@click.option('--output', '-o', default='evals/results', help='Output directory')
def run(task_pattern: str, trials: int, output: str):
    """Run eval tasks matching pattern."""
    runner = TaskRunner(Path('evals/config.yaml'))

    tasks = list(Path('evals/tasks').glob(f'**/{task_pattern}.yaml'))
    click.echo(f"Found {len(tasks)} tasks")

    for task_path in tasks:
        click.echo(f"Running: {task_path.stem}")
        result = runner.run_task(task_path)

        # Save results
        save_result(result, Path(output))

        # Print summary
        click.echo(f"  pass@{trials}: {result.pass_at_k:.2%}")
        click.echo(f"  pass^{trials}: {result.pass_power_k:.2%}")
        click.echo(f"  avg iterations: {result.avg_iterations:.1f}")

@cli.command()
@click.argument('results_dir', default='evals/results')
def report(results_dir: str):
    """Generate eval report from results."""
    generate_report(Path(results_dir))
```

---

## 6. Initial Eval Tasks (Start Here)

Following Anthropic's advice to start with "20-50 simple tasks drawn from real failures":

### 6.1 Entity Discovery (10 tasks)

```yaml
# evals/tasks/entity_discovery/prov_instant_event_001.yaml
task:
  id: "prov_instant_event_001"
  category: "entity_discovery"
  difficulty: "easy"
  query: "What is prov:InstantaneousEvent?"
  context:
    ontologies:
      - name: prov
        source: ontology/prov.ttl
  graders:
    - type: groundedness
      required_evidence:
        - pattern: "InstantaneousEvent"
    - type: convergence
      max_iterations: 5
    - type: answer_contains
      keywords: ["event", "instant", "time"]
  trials: 5
```

### 6.2 Hierarchy Navigation (10 tasks)

```yaml
# evals/tasks/hierarchy/prov_activity_hierarchy_001.yaml
task:
  id: "prov_activity_hierarchy_001"
  category: "hierarchy"
  difficulty: "medium"
  query: "What are the subclasses of prov:Activity?"
  context:
    ontologies:
      - name: prov
        source: ontology/prov.ttl
  graders:
    - type: groundedness
    - type: convergence
      max_iterations: 8
    - type: evidence_pattern
      required:
        - function: "probe_relationships|describe_entity"
          contains: "subclass"
  trials: 5
```

### 6.3 Memory Influence (5 tasks)

```yaml
# evals/tasks/memory/memory_improves_behavior_001.yaml
task:
  id: "memory_improves_001"
  category: "memory_influence"
  difficulty: "hard"

  # Two-phase eval
  phases:
    - name: "cold_start"
      query: "Describe prov:Activity and its relationships"
      memories: []

    - name: "warm_start"
      query: "Describe prov:Entity and its relationships"
      memories:
        - from_phase: "cold_start"
          extract: true

  graders:
    - type: memory_influence
      expect: "warm_start iterations < cold_start iterations"
    - type: groundedness
  trials: 3
```

### 6.4 Regression (10 tasks)

```yaml
# evals/tasks/regression/basic_search_001.yaml
task:
  id: "basic_search_001"
  category: "regression"
  difficulty: "trivial"
  query: "Search for 'Activity' in the PROV ontology"
  context:
    ontologies:
      - name: prov
        source: ontology/prov.ttl
  graders:
    - type: tool_called
      required: ["search_entity"]
    - type: convergence
      max_iterations: 3
  trials: 3
  pass_threshold: 1.0  # Must pass all trials
```

---

## 7. Best Practices for RLM Evals

### 7.1 Grade Outcomes, Not Process

❌ **Bad:** Require specific tool call sequence
```yaml
graders:
  - type: exact_sequence
    sequence: [search_entity, describe_entity, FINAL_VAR]
```

✅ **Good:** Check that answer is grounded and correct
```yaml
graders:
  - type: groundedness
  - type: answer_contains
    keywords: ["expected", "facts"]
```

### 7.2 Read Transcripts Regularly

```python
# In development, always inspect failed trials
def debug_failure(result: EvalResult):
    for i, trial in enumerate(result.trial_results):
        if not trial['passed']:
            print(f"=== Trial {i} Failed ===")
            print(f"Answer: {trial['answer']}")
            print(f"Grader results: {trial['grader_results']}")
            print("Transcript:")
            for iteration in trial['transcript']:
                print(f"  Iter {iteration['iteration']}: {iteration['code_blocks'][:100]}...")
```

### 7.3 Calibrate LLM Graders

```python
# Periodically check LLM grader against human judgment
def calibrate_llm_grader(grader: LLMRubricGrader, samples: int = 20):
    """Compare LLM grades to human expert grades."""
    tasks = random.sample(all_tasks, samples)

    for task in tasks:
        llm_grade = grader.grade(task.transcript, task.answer)
        human_grade = get_human_grade(task)  # Manual review

        if llm_grade['passed'] != human_grade['passed']:
            log_disagreement(task, llm_grade, human_grade)

    calculate_agreement_score()
```

### 7.4 Balance Positive and Negative Cases

Include tasks that SHOULD fail:
```yaml
# evals/tasks/negative/hallucination_detection_001.yaml
task:
  id: "hallucination_neg_001"
  category: "negative"
  query: "Describe the FakeClass that doesn't exist in PROV"
  expected_behavior: "Agent should report entity not found"
  graders:
    - type: answer_contains
      keywords: ["not found", "does not exist", "no results"]
    - type: no_hallucination
      forbidden_claims: ["FakeClass is defined as", "FakeClass has properties"]
```

---

## 8. Eval Lifecycle

### 8.1 Development Flow

```
1. Identify failure mode → Write capability eval task
2. Run eval (expect low pass rate initially)
3. Improve agent/prompts
4. Re-run eval, track improvement
5. When pass@k > 90%, move to regression suite
6. Monitor regression suite for drift
```

### 8.2 CI Integration

```yaml
# .github/workflows/evals.yml
name: RLM Evals
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run regression evals
        run: |
          python -m evals.cli run 'regression/*' --trials 3
      - name: Check pass rate
        run: |
          python -m evals.cli check --min-pass-rate 0.95

  capability:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - name: Run capability evals
        run: |
          python -m evals.cli run '*' --trials 5
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: eval-results
          path: evals/results/
```

---

## 9. Getting Started

### Step 1: Create Initial Task Set

```bash
mkdir -p evals/tasks/{entity_discovery,hierarchy,memory,regression}
```

Write 5-10 tasks in each category based on real queries you've tested.

### Step 2: Implement Core Graders

Start with:
1. `GroundednessGrader` - Essential for research agents
2. `ConvergenceGrader` - Basic termination check
3. `AnswerContainsGrader` - Simple keyword matching

### Step 3: Run First Eval

```bash
python -m evals.cli run 'entity_discovery/*' --trials 3
```

### Step 4: Read Transcripts

For EVERY failure, read the full transcript. This is how you learn what's actually happening.

### Step 5: Iterate

Improve prompts/tools → Re-run evals → Track metrics over time.

---

## 10. References

- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [RLM Paper Protocol](../rlmpaper/)
- [Trajectory Document](../planning/trajectory.md)
- [Testing Campaign](../tests/README.md)
