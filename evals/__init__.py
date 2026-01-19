"""RLM Evaluation Framework.

A comprehensive evaluation system for the RLM (Recursive Language Models) agent,
based on Anthropic's recommendations for AI agent evals.

Key Components:
- graders/: Evaluation graders (groundedness, convergence, etc.)
- runners/: Task execution and metrics calculation
- tasks/: YAML task definitions organized by category
- rubrics/: LLM grading rubrics

Usage:
    # Run all evals
    python -m evals.cli run

    # Run specific category
    python -m evals.cli run 'entity_discovery/*'

    # List available tasks
    python -m evals.cli list

    # Generate report
    python -m evals.cli report

See docs/eval-framework.md for detailed documentation.
"""

__version__ = '0.1.0'
