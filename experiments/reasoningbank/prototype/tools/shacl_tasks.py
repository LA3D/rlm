"""SHACL example task loader for ReasoningBank learning.

Converts SHACL-annotated examples into tasks for closed-loop learning.
These are NOT procedural memory - they are the TASK CORPUS the agent runs on.

The learning flow:
1. Load SHACL examples as tasks (this module)
2. Agent runs on tasks using exploration tools
3. Trajectories get judged (success/failure)
4. Strategies extracted from successful trajectories
5. Strategies stored in L2 procedural memory

What goes into L2 (procedural memory):
- "When querying protein-disease associations, explore up:Disease_Annotation first"
- General, transferable strategies extracted from trajectories

NOT what goes into L2:
- Raw SHACL examples (question + SPARQL pairs)
- Task-specific query templates

Usage:
    from experiments.reasoningbank.prototype.tools.shacl_tasks import load_shacl_tasks

    tasks = load_shacl_tasks('ontology/uniprot')
    for task in tasks[:5]:
        print(f"{task.id}: {task.query[:50]}...")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from experiments.reasoningbank.prototype.tools.uniprot_examples import (
        load_examples, SPARQLExample, categorize_by_complexity
    )
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')
    from experiments.reasoningbank.prototype.tools.uniprot_examples import (
        load_examples, SPARQLExample, categorize_by_complexity
    )


@dataclass
class Task:
    """A task for ReasoningBank learning.

    This represents a competency question from a SHACL example.
    The agent will attempt to answer this using exploration tools.
    """
    id: str                     # Example filename/identifier
    query: str                  # Competency question (natural language)
    expected_sparql: str        # Reference SPARQL query
    endpoint: str               # Target endpoint URL
    keywords: list[str] = field(default_factory=list)
    complexity: str = 'unknown'  # 'simple', 'moderate', 'complex'

    def __repr__(self):
        return f"Task({self.id!r}, {len(self.query)} chars, {self.complexity})"


def example_to_task(example: SPARQLExample, complexity: str = 'unknown') -> Task:
    """Convert a SPARQLExample to a Task."""
    return Task(
        id=example.id,
        query=example.comment,
        expected_sparql=example.query,
        endpoint=example.target,
        keywords=example.keywords,
        complexity=complexity,
    )


def load_shacl_tasks(
    ontology_path: str,
    examples_subdir: str = 'examples',
    max_tasks: Optional[int] = None,
    complexity_filter: Optional[list[str]] = None,
) -> list[Task]:
    """Load SHACL examples as tasks for ReasoningBank learning.

    Args:
        ontology_path: Path to ontology directory (e.g., 'ontology/uniprot')
        examples_subdir: Subdirectory containing examples
        max_tasks: Maximum number of tasks to load (None = all)
        complexity_filter: Only load tasks of these complexities
            e.g., ['simple', 'moderate'] to exclude complex queries

    Returns:
        List of Task objects ready for ReasoningBank learning loop
    """
    ontology_path = Path(ontology_path)
    examples_dir = ontology_path / examples_subdir

    if not examples_dir.exists():
        return []

    # Load all examples
    all_examples = []

    # Load from subdirectories (e.g., UniProt/, neXtProt/)
    for subdir in examples_dir.iterdir():
        if subdir.is_dir():
            all_examples.extend(load_examples(subdir))

    # Also load from examples directory itself
    all_examples.extend(load_examples(examples_dir))

    if not all_examples:
        return []

    # Categorize by complexity
    categories = categorize_by_complexity(all_examples)

    # Build task list with complexity labels
    tasks = []

    for complexity, examples in categories.items():
        if complexity_filter and complexity not in complexity_filter:
            continue

        for ex in examples:
            if ex.comment:  # Only include examples with competency questions
                tasks.append(example_to_task(ex, complexity))

    # Sort by ID for reproducibility
    tasks.sort(key=lambda t: t.id)

    # Apply limit
    if max_tasks:
        tasks = tasks[:max_tasks]

    return tasks


def get_task_stats(tasks: list[Task]) -> dict:
    """Get statistics about a task corpus.

    Returns:
        {total, by_complexity, by_endpoint, keywords}
    """
    stats = {
        'total': len(tasks),
        'by_complexity': {},
        'by_endpoint': {},
        'top_keywords': {},
    }

    for task in tasks:
        # Complexity
        c = task.complexity
        stats['by_complexity'][c] = stats['by_complexity'].get(c, 0) + 1

        # Endpoint
        ep = task.endpoint.split('/')[-2] if '/' in task.endpoint else task.endpoint
        stats['by_endpoint'][ep] = stats['by_endpoint'].get(ep, 0) + 1

        # Keywords
        for kw in task.keywords:
            stats['top_keywords'][kw] = stats['top_keywords'].get(kw, 0) + 1

    # Sort keywords by frequency
    stats['top_keywords'] = dict(
        sorted(stats['top_keywords'].items(), key=lambda x: -x[1])[:20]
    )

    return stats


def sample_tasks(
    tasks: list[Task],
    n: int = 10,
    complexity: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[Task]:
    """Sample tasks from corpus with optional filtering.

    Args:
        tasks: Full task corpus
        n: Number of tasks to sample
        complexity: Filter by complexity level
        keyword: Filter by keyword

    Returns:
        Sampled task list
    """
    filtered = tasks

    if complexity:
        filtered = [t for t in filtered if t.complexity == complexity]

    if keyword:
        filtered = [t for t in filtered if keyword in t.keywords]

    return filtered[:n]


def format_task_for_agent(task: Task) -> str:
    """Format a task as input for the agent.

    This is what gets passed to the RLM - just the competency question.
    The expected_sparql is NOT included (that's for evaluation).
    """
    return task.query


def format_task_with_context(task: Task) -> str:
    """Format task with minimal context for debugging.

    Includes endpoint hint but NOT the expected SPARQL.
    """
    return f"""Question: {task.query}

Target endpoint: {task.endpoint}
Keywords: {', '.join(task.keywords)}"""


# =============================================================================
# Test function
# =============================================================================

def test_shacl_tasks():
    """Test SHACL task loading."""
    print("Testing SHACL task loader...\n")

    # Load tasks
    tasks = load_shacl_tasks('ontology/uniprot')
    print(f"Loaded {len(tasks)} tasks\n")

    if not tasks:
        print("No tasks found. Check ontology/uniprot/examples/ exists.")
        return

    # Show stats
    stats = get_task_stats(tasks)
    print("=== Task Statistics ===")
    print(f"Total: {stats['total']}")
    print(f"By complexity: {stats['by_complexity']}")
    print(f"By endpoint: {stats['by_endpoint']}")
    print(f"Top keywords: {list(stats['top_keywords'].keys())[:10]}")

    # Show samples
    print("\n=== Sample Tasks ===")
    for task in sample_tasks(tasks, n=3, complexity='simple'):
        print(f"\n{task.id} ({task.complexity}):")
        print(f"  Q: {task.query[:80]}...")
        print(f"  Endpoint: {task.endpoint}")
        print(f"  Keywords: {task.keywords}")
        print(f"  SPARQL: {task.expected_sparql[:60]}...")

    # Show agent format
    print("\n=== Agent Input Format ===")
    task = tasks[0]
    print(format_task_for_agent(task))

    print("\n✓ SHACL task loader OK")


if __name__ == '__main__':
    test_shacl_tasks()
