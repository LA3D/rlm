"""E-RC-001: Reasoning Chain Exemplars Impact Experiment

Tests whether PDDL-INSTRUCT style reasoning chain examples improve
SPARQL query construction accuracy.

Conditions:
1. Baseline - AGENT_GUIDE.md only
2. Schema+ - AGENT_GUIDE.md + domain/range constraints
3. Exemplar-3 - AGENT_GUIDE.md + 3 reasoning chains
4. Exemplar-5 - AGENT_GUIDE.md + 5 reasoning chains

Usage:
    python rc_001_exemplar_impact.py [--condition baseline|schema|exemplar3|exemplar5|all]
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

# Ensure API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")


@dataclass
class TestTask:
    """A test task for evaluation."""
    id: str
    level: int
    question: str
    expected_patterns: list[str]  # Patterns that should appear in query
    anti_patterns: list[str]  # Patterns that should NOT appear


@dataclass
class TaskResult:
    """Result of running a single task."""
    task_id: str
    condition: str
    question: str
    generated_query: str
    reasoning_trace: str
    iterations: int
    passed: bool
    pass_reasons: list[str]
    fail_reasons: list[str]
    behavior_indicators: dict


# Test tasks (subset for quick validation)
TEST_TASKS = [
    TestTask(
        id="L1-basic",
        level=1,
        question="What is the protein with accession P12345?",
        expected_patterns=["up:Protein", "P12345"],
        anti_patterns=[]
    ),
    TestTask(
        id="L2-crossref",
        level=2,
        question="What are the GO annotations for insulin?",
        expected_patterns=["up:GO_Annotation", "up:annotation", "up:classifiedWith", "insulin"],
        anti_patterns=["?protein up:classifiedWith"]  # Wrong: classifiedWith is on Annotation
    ),
    TestTask(
        id="L3-filter",
        level=3,
        question="Find human proteins with kinase activity",
        expected_patterns=["up:Protein", "taxon", "9606", "kinase"],
        anti_patterns=["FILTER.*kinase.*label"]  # Should use GO classification, not label search
    ),
]


def load_agent_guide(ontology_path: str = "ontology/uniprot/AGENT_GUIDE.md") -> str:
    """Load the AGENT_GUIDE.md content."""
    guide_path = Path(ontology_path)
    if guide_path.exists():
        return guide_path.read_text()
    return "# UniProt Ontology Guide\n\nNo guide available."


def load_exemplars(count: int = 5) -> str:
    """Load reasoning chain exemplars."""
    exemplar_dir = Path(__file__).parent / "exemplars"
    exemplars = []

    # Load available exemplars
    exemplar_files = sorted(exemplar_dir.glob("uniprot_l*.md"))[:count]

    for f in exemplar_files:
        exemplars.append(f"---\n\n{f.read_text()}")

    if not exemplars:
        return ""

    return "\n\n# Reasoning Chain Exemplars\n\nFollow these step-by-step reasoning patterns:\n\n" + "\n".join(exemplars)


def build_schema_plus_context() -> str:
    """Build enhanced schema context with domain/range constraints."""
    return """
# Domain/Range Constraints for Query Construction

When building SPARQL patterns, verify these constraints:

## Key Property Constraints

| Property | Domain | Range | Usage |
|----------|--------|-------|-------|
| `up:annotation` | `up:Protein` | `up:Annotation` | Protein → Annotation |
| `up:classifiedWith` | `up:Annotation` | External URI | Annotation → GO/EC/etc |
| `up:encodedBy` | `up:Protein` | `up:Gene` | Protein → Gene |
| `up:organism` | `up:Protein` | `up:Taxon` | Protein → Organism |
| `up:catalyzedReaction` | `up:Enzyme` | `up:Reaction` | Enzyme → Reaction |

## Verification Steps

Before constructing a join pattern `?x <prop> ?y`:
1. Check: Is ?x's type in property's domain?
2. Check: Is ?y's expected type in property's range?
3. If no, find intermediate class or different property

## Common Anti-Patterns

- DON'T: `?protein up:classifiedWith ?go` (classifiedWith is on Annotation, not Protein)
- DON'T: `?protein a up:Disease_Annotation` (proteins aren't annotations)
- DON'T: Use rdfs:label FILTER for classifications (use proper GO/EC links)
"""


def log_experiment_event(log_file: Path, event: dict):
    """Append an event to experiment JSONL log."""
    import json
    with log_file.open("a") as f:
        f.write(json.dumps(event) + "\n")


def save_task_trajectory(condition: str, task: TestTask, prompt: str, output: str,
                         usage: dict, elapsed_seconds: float):
    """Save full trajectory for later analysis.

    Creates both:
    1. Human-readable markdown trace
    2. Machine-readable JSONL event log
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    trajectory_dir = Path(__file__).parent / "results" / "trajectories"
    trajectory_dir.mkdir(parents=True, exist_ok=True)

    # Human-readable trace
    trace_file = trajectory_dir / f"{task.id}_{condition}_{timestamp}.md"
    trace_content = f"""# Trajectory: {task.id} - {condition}

**Timestamp**: {datetime.now().isoformat()}
**Task ID**: {task.id}
**Condition**: {condition}
**Question**: {task.question}

---

## Prompt

{prompt}

---

## Response

{output}

---

## Metrics

- Input tokens: {usage['input_tokens']}
- Output tokens: {usage['output_tokens']}
- Total tokens: {usage['total_tokens']}
- Elapsed: {elapsed_seconds:.2f}s
"""
    trace_file.write_text(trace_content)

    # Machine-readable JSONL log
    jsonl_file = trajectory_dir / f"{task.id}_{condition}_{timestamp}.jsonl"
    import json
    events = [
        {
            "event": "task_start",
            "timestamp": datetime.now().isoformat(),
            "task_id": task.id,
            "condition": condition,
            "question": task.question
        },
        {
            "event": "llm_call",
            "timestamp": datetime.now().isoformat(),
            "prompt_chars": len(prompt),
            "input_tokens": usage['input_tokens']
        },
        {
            "event": "llm_response",
            "timestamp": datetime.now().isoformat(),
            "output_chars": len(output),
            "output_tokens": usage['output_tokens'],
            "elapsed_seconds": elapsed_seconds
        },
        {
            "event": "task_complete",
            "timestamp": datetime.now().isoformat(),
            "total_tokens": usage['total_tokens'],
            "elapsed_seconds": elapsed_seconds
        }
    ]

    with jsonl_file.open("w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    return trace_file, jsonl_file


def build_prompt(condition: str, task: TestTask) -> str:
    """Build the prompt for a given condition."""

    base_guide = load_agent_guide()

    # Build context based on condition
    if condition == "baseline":
        context = base_guide
    elif condition == "schema":
        context = base_guide + "\n\n" + build_schema_plus_context()
    elif condition == "exemplar3":
        context = base_guide + "\n\n" + load_exemplars(3)
    elif condition == "exemplar5":
        context = base_guide + "\n\n" + load_exemplars(5)
    else:
        context = base_guide

    prompt = f"""You are a SPARQL query construction agent for the UniProt knowledge base.

{context}

---

## Task

Construct a SPARQL query to answer this question:

**Question**: {task.question}

## Instructions

1. **Think step-by-step** about what concepts and properties you need
2. **Verify constraints** before building join patterns
3. **State your reasoning** explicitly at each step
4. **Check for anti-patterns** before finalizing

## Output Format

Provide your response in this format:

### Reasoning

[Your step-by-step reasoning, including:
- What concepts/classes are needed
- What properties connect them
- Any domain/range verification
- Anti-patterns to avoid]

### Query

```sparql
[Your final SPARQL query]
```

### Verification

[Brief verification that the query:
- Uses correct property paths
- Has appropriate filters
- Avoids known anti-patterns]
"""
    return prompt


def run_task(condition: str, task: TestTask, save_trajectory: bool = True) -> TaskResult:
    """Run a single task under a given condition.

    Args:
        condition: Which experimental condition
        task: The test task to run
        save_trajectory: If True, save full trajectory to file

    Returns:
        TaskResult with all metrics and analysis
    """
    import anthropic
    from datetime import datetime

    client = anthropic.Anthropic()

    prompt = build_prompt(condition, task)

    start_time = datetime.now()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed_seconds = (datetime.now() - start_time).total_seconds()

    output = response.content[0].text

    # Save trajectory if requested
    if save_trajectory:
        save_task_trajectory(
            condition=condition,
            task=task,
            prompt=prompt,
            output=output,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            },
            elapsed_seconds=elapsed_seconds
        )

    # Extract query from response
    query = ""
    if "```sparql" in output:
        start = output.find("```sparql") + 9
        end = output.find("```", start)
        query = output[start:end].strip()

    # Analyze behavior indicators
    indicators = analyze_behavior(output)

    # Check pass/fail
    passed, pass_reasons, fail_reasons = evaluate_result(task, query, output)

    return TaskResult(
        task_id=task.id,
        condition=condition,
        question=task.question,
        generated_query=query,
        reasoning_trace=output,
        iterations=1,  # Single-shot for now
        passed=passed,
        pass_reasons=pass_reasons,
        fail_reasons=fail_reasons,
        behavior_indicators=indicators
    )


def analyze_behavior(output: str) -> dict:
    """Analyze reasoning output for PDDL-INSTRUCT style indicators."""
    output_lower = output.lower()

    indicators = {
        "explicit_state_tracking": any(w in output_lower for w in
            ["state", "discovered", "known classes", "known properties"]),
        "verification_present": any(w in output_lower for w in
            ["verify", "verification", "check", "confirm"]),
        "constraint_checking": any(w in output_lower for w in
            ["domain", "range", "constraint"]),
        "anti_pattern_mention": any(w in output_lower for w in
            ["anti-pattern", "don't", "avoid", "wrong"]),
        "step_by_step": output_lower.count("step") >= 2,
        "explicit_reasoning": "reasoning" in output_lower or "because" in output_lower,
    }

    indicators["score"] = sum(indicators.values()) / len(indicators)

    return indicators


def evaluate_result(task: TestTask, query: str, output: str) -> tuple[bool, list[str], list[str]]:
    """Evaluate if the result passes."""
    pass_reasons = []
    fail_reasons = []

    query_lower = query.lower()

    # Check expected patterns
    for pattern in task.expected_patterns:
        if pattern.lower() in query_lower:
            pass_reasons.append(f"Contains expected: {pattern}")
        else:
            fail_reasons.append(f"Missing expected: {pattern}")

    # Check anti-patterns
    import re
    for anti in task.anti_patterns:
        if re.search(anti, query, re.IGNORECASE):
            fail_reasons.append(f"Contains anti-pattern: {anti}")

    # Pass if no failures and at least some expected patterns
    passed = len(fail_reasons) == 0 and len(pass_reasons) > 0

    return passed, pass_reasons, fail_reasons


def run_experiment(conditions: list[str], output_dir: str = "experiments/reasoning_chain_validation/results"):
    """Run the full experiment with comprehensive trajectory logging."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create experiment-level JSONL log
    experiment_log = output_path / f"experiment_{timestamp}.jsonl"
    log_experiment_event(experiment_log, {
        "event": "experiment_start",
        "timestamp": timestamp,
        "conditions": conditions,
        "tasks": [t.id for t in TEST_TASKS]
    })

    all_results = []

    for condition in conditions:
        print(f"\n{'='*60}")
        print(f"Condition: {condition.upper()}")
        print(f"{'='*60}")

        log_experiment_event(experiment_log, {
            "event": "condition_start",
            "condition": condition,
            "timestamp": datetime.now().isoformat()
        })

        for task in TEST_TASKS:
            print(f"\n  Task: {task.id} - {task.question[:50]}...")

            result = run_task(condition, task, save_trajectory=True)
            all_results.append(result)

            status = "PASS" if result.passed else "FAIL"
            print(f"  Result: {status}")
            print(f"  Behavior score: {result.behavior_indicators['score']:.2f}")

            if result.fail_reasons:
                for reason in result.fail_reasons[:2]:
                    print(f"    - {reason}")

            # Log task completion
            log_experiment_event(experiment_log, {
                "event": "task_complete",
                "task_id": task.id,
                "condition": condition,
                "passed": result.passed,
                "behavior_score": result.behavior_indicators['score'],
                "timestamp": datetime.now().isoformat()
            })

        log_experiment_event(experiment_log, {
            "event": "condition_complete",
            "condition": condition,
            "timestamp": datetime.now().isoformat()
        })

    # Compute summary statistics
    summary = compute_summary(all_results, conditions)

    # Save results
    results_file = output_path / f"rc_001_results_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "conditions": conditions,
            "tasks": [t.id for t in TEST_TASKS],
            "results": [asdict(r) for r in all_results],
            "summary": summary
        }, f, indent=2)

    # Log experiment completion
    log_experiment_event(experiment_log, {
        "event": "experiment_complete",
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(all_results),
        "summary": summary
    })

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    # Print summary table
    print(f"\n{'Condition':<12} {'Pass Rate':<12} {'Behavior Score':<15}")
    print("-" * 40)
    for cond in conditions:
        stats = summary[cond]
        print(f"{cond:<12} {stats['pass_rate']:.1%}{'':4} {stats['avg_behavior_score']:.2f}")

    print(f"\n{'='*60}")
    print("FILES SAVED")
    print(f"{'='*60}")
    print(f"Results JSON: {results_file}")
    print(f"Experiment log: {experiment_log}")
    print(f"Trajectories: {output_path / 'trajectories'}/ ({len(all_results)} files)")
    print(f"\nAnalyze trajectories with:")
    print(f"  python behavior_analysis.py {output_path / 'trajectories'}")

    return all_results, summary


def compute_summary(results: list[TaskResult], conditions: list[str]) -> dict:
    """Compute summary statistics by condition."""
    summary = {}

    for cond in conditions:
        cond_results = [r for r in results if r.condition == cond]

        pass_count = sum(1 for r in cond_results if r.passed)
        total = len(cond_results)

        behavior_scores = [r.behavior_indicators["score"] for r in cond_results]

        summary[cond] = {
            "pass_count": pass_count,
            "total": total,
            "pass_rate": pass_count / total if total > 0 else 0,
            "avg_behavior_score": sum(behavior_scores) / len(behavior_scores) if behavior_scores else 0,
            "behavior_breakdown": {
                indicator: sum(1 for r in cond_results if r.behavior_indicators.get(indicator, False)) / total
                for indicator in ["explicit_state_tracking", "verification_present", "constraint_checking",
                                  "anti_pattern_mention", "step_by_step", "explicit_reasoning"]
            }
        }

    return summary


def main():
    parser = argparse.ArgumentParser(description="E-RC-001: Reasoning Chain Exemplars Impact")
    parser.add_argument("--condition", choices=["baseline", "schema", "exemplar3", "exemplar5", "all"],
                        default="all", help="Which condition(s) to run")
    args = parser.parse_args()

    if args.condition == "all":
        conditions = ["baseline", "schema", "exemplar3", "exemplar5"]
    else:
        conditions = [args.condition]

    run_experiment(conditions)


if __name__ == "__main__":
    main()
