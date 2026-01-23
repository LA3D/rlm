"""Task runner for executing RLM evaluation tasks."""

import math
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from ..graders import (
    GroundednessGrader,
    ConvergenceGrader,
    AnswerContainsGrader,
    EvidencePatternGrader,
    ToolCalledGrader,
    SparqlStructuralGrader,
    AffordanceUtilizationGrader,
    OutcomeVerificationGrader,
    LLMJudgeGrader,
)
from ..graders.base import GradeResult


@dataclass
class TrialResult:
    """Result of a single trial."""
    trial_number: int
    passed: bool
    answer: str
    iterations: int
    grader_results: dict[str, dict]
    transcript: list
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    # New fields for artifact capture (Rung 1)
    sparql: Optional[str] = None
    evidence: Optional[dict] = None
    converged: bool = True
    # Think-Act-Verify-Reflect reasoning fields
    thinking: Optional[str] = None
    verification: Optional[str] = None
    reflection: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvalResult:
    """Result of running all trials for a task."""
    task_id: str
    task_query: str
    trial_results: list[TrialResult]
    pass_at_k: float
    pass_power_k: float
    avg_iterations: float
    avg_groundedness: float
    total_trials: int
    passed_trials: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')

    def to_dict(self) -> dict:
        return {
            'task_id': self.task_id,
            'task_query': self.task_query,
            'pass_at_k': self.pass_at_k,
            'pass_power_k': self.pass_power_k,
            'avg_iterations': self.avg_iterations,
            'avg_groundedness': self.avg_groundedness,
            'total_trials': self.total_trials,
            'passed_trials': self.passed_trials,
            'timestamp': self.timestamp,
            'trial_results': [t.to_dict() for t in self.trial_results]
        }

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Task: {self.task_id}\n"
            f"  pass@{self.total_trials}: {self.pass_at_k:.1%}\n"
            f"  pass^{self.total_trials}: {self.pass_power_k:.1%}\n"
            f"  Passed: {self.passed_trials}/{self.total_trials}\n"
            f"  Avg iterations: {self.avg_iterations:.1f}\n"
            f"  Avg groundedness: {self.avg_groundedness:.1%}"
        )


def calculate_pass_at_k(results: list[bool], k: int) -> float:
    """Calculate probability of at least one success in k trials.

    Formula: 1 - C(n-c, k) / C(n, k)
    where n = total trials, c = successes
    """
    n = len(results)
    c = sum(results)

    if n < k:
        return float(c > 0)

    if n - c < k:
        return 1.0

    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def calculate_pass_power_k(results: list[bool], k: int) -> float:
    """Calculate probability of all k trials succeeding.

    Formula: C(c, k) / C(n, k)
    where n = total trials, c = successes
    """
    n = len(results)
    c = sum(results)

    if n < k or c < k:
        return 0.0

    return math.comb(c, k) / math.comb(n, k)


class TaskRunner:
    """Run eval tasks with multiple trials."""

    # Grader registry
    GRADERS = {
        'groundedness': GroundednessGrader,
        'convergence': ConvergenceGrader,
        'answer_contains': AnswerContainsGrader,
        'evidence_pattern': EvidencePatternGrader,
        'tool_called': ToolCalledGrader,
        'sparql_structural': SparqlStructuralGrader,
        'affordance_utilization': AffordanceUtilizationGrader,
        'outcome_verification': OutcomeVerificationGrader,
        'llm_judge': LLMJudgeGrader,
    }

    def __init__(self, config: dict = None):
        """Initialize task runner.

        Args:
            config: Optional global configuration dict (keys: enable_mlflow, memory_db_path, enable_memory)
        """
        self.config = config or {}

        # Initialize memory backend if enabled
        self.memory_backend = None
        if self.config.get('enable_memory', False):
            from rlm_runtime.memory import SQLiteMemoryBackend
            memory_db = self.config.get('memory_db_path', 'evals/memory.db')
            self.memory_backend = SQLiteMemoryBackend(memory_db)
            print(f"ReasoningBank enabled: {memory_db}")

    def run_task(self, task_path: Path, num_trials: int = None) -> EvalResult:
        """Run all trials for a task.

        Args:
            task_path: Path to task YAML file
            num_trials: Override number of trials (uses task default if None)

        Returns:
            EvalResult with all trial results and metrics
        """
        raw = yaml.safe_load(task_path.read_text())
        # Support both formats:
        # - {task: {...}} (preferred)
        # - {...} (legacy)
        task = raw.get('task', raw) if isinstance(raw, dict) else raw

        if num_trials is not None:
            if num_trials < 1:
                raise ValueError(f"num_trials must be >= 1, got {num_trials}")
            trials = num_trials
        else:
            trials = task.get('trials', 5)

        # Setup MLflow run for this task if enabled (Rung 3)
        enable_mlflow = self.config.get('enable_mlflow', False)
        mlflow_run_active = False

        if enable_mlflow:
            try:
                import mlflow
                from rlm_runtime.logging.mlflow_integration import log_run_params, log_run_tags, log_run_metrics

                # Start nested run for this task
                task_id = task.get('id', task_path.stem)
                mlflow.start_run(run_name=f"task-{task_id}", nested=True)
                mlflow_run_active = True

                # Log task parameters
                log_run_params(
                    query=task.get('query', ''),
                    task_id=task_id,
                    category=task.get('category', 'unknown'),
                    difficulty=task.get('difficulty', 'unknown'),
                    max_iterations=task.get('max_iterations', 10)
                )

                # Log task tags for filtering
                log_run_tags(
                    task_id=task_id,
                    custom_tags={
                        'category': task.get('category', 'unknown'),
                        'difficulty': task.get('difficulty', 'unknown')
                    }
                )
            except Exception as e:
                import warnings
                warnings.warn(f"MLflow logging failed: {e}", UserWarning)
                mlflow_run_active = False

        # Run trials
        trial_results = []
        for trial_num in range(trials):
            result = self._run_single_trial(task, trial_num)
            trial_results.append(result)

        # Calculate metrics
        passes = [r.passed for r in trial_results]
        k = trials

        # Calculate average groundedness from grader results
        groundedness_scores = []
        for r in trial_results:
            if 'groundedness' in r.grader_results:
                gs = r.grader_results['groundedness'].get('details', {}).get('groundedness_score', 0)
                groundedness_scores.append(gs)

        avg_groundedness = sum(groundedness_scores) / len(groundedness_scores) if groundedness_scores else 0.0

        result = EvalResult(
            task_id=task.get('id', task_path.stem),
            task_query=task.get('query', ''),
            trial_results=trial_results,
            pass_at_k=calculate_pass_at_k(passes, k),
            pass_power_k=calculate_pass_power_k(passes, k),
            avg_iterations=sum(r.iterations for r in trial_results) / len(trial_results),
            avg_groundedness=avg_groundedness,
            total_trials=trials,
            passed_trials=sum(passes)
        )

        # Log metrics to MLflow if active (Rung 3)
        if mlflow_run_active:
            try:
                from rlm_runtime.logging.mlflow_integration import log_run_metrics
                import mlflow

                # Calculate convergence rate
                converged_count = sum(1 for r in trial_results if r.converged)
                convergence_rate = converged_count / len(trial_results) if trial_results else 0

                # Log aggregated metrics
                log_run_metrics(
                    iteration_count=result.avg_iterations,
                    converged=convergence_rate,
                    pass_at_k=result.pass_at_k,
                    pass_power_k=result.pass_power_k,
                    groundedness=avg_groundedness
                )

                # End nested run
                mlflow.end_run()
            except Exception as e:
                import warnings
                warnings.warn(f"MLflow metrics logging failed: {e}", UserWarning)

        return result

    def _run_single_trial(self, task: dict, trial_num: int) -> TrialResult:
        """Execute one trial of a task."""
        try:
            # Setup namespace and build context
            ns, context = self._setup_namespace_and_context(task)

            # Check if DSPy backend should be used
            use_dspy = self.config.get('use_dspy', False)

            # Variables to capture artifacts
            sparql = None
            evidence = None
            converged = True
            thinking = None
            verification = None
            reflection = None

            if use_dspy:
                # Run DSPy RLM - returns DSPyRLMResult with full artifacts
                result = self._execute_dspy_rlm(task, ns, context)
                answer = result.answer
                iterations = result.trajectory
                transcript = self._serialize_dspy_trajectory(iterations)
                # Capture artifacts (Rung 1)
                sparql = result.sparql
                evidence = result.evidence
                converged = result.converged
                # Capture Think-Act-Verify-Reflect reasoning fields
                thinking = result.thinking
                verification = result.verification
                reflection = result.reflection
                # Add extracted artifacts to transcript for graders
                if sparql or evidence:
                    transcript.append({
                        "sparql": sparql,
                        "evidence": evidence if evidence else {}
                    })
            else:
                # Run legacy claudette-backed RLM
                answer, iterations = self._execute_rlm(task, ns, context)
                transcript = self._serialize_transcript(iterations)

            # Grade with all configured graders
            grader_results = {}
            overall_pass = True

            for grader_config in task.get('graders', []):
                grader = self._get_grader(grader_config)
                result = grader.grade(transcript, answer, task)
                grader_results[grader_config['type']] = {
                    'passed': result.passed,
                    'score': result.score,
                    'reason': result.reason,
                    'details': result.details
                }
                if not result.passed:
                    overall_pass = False

            return TrialResult(
                trial_number=trial_num,
                passed=overall_pass,
                answer=answer,
                iterations=len(iterations),
                grader_results=grader_results,
                transcript=transcript,
                sparql=sparql,
                evidence=evidence,
                converged=converged,
                thinking=thinking,
                verification=verification,
                reflection=reflection
            )

        except Exception as e:
            return TrialResult(
                trial_number=trial_num,
                passed=False,
                answer="",
                iterations=0,
                grader_results={},
                transcript=[],
                error=str(e)
            )

    def _setup_namespace_and_context(self, task: dict) -> tuple[dict, str]:
        """Setup namespace and build the context string for the run."""
        ns: dict = {}

        # Setup ontology context (local schema/affordances)
        ctx = task.get('context', {}) or {}
        ontologies = ctx.get('ontologies', []) or []

        ontology_summaries: list[str] = []
        if ontologies:
            from rlm.ontology import setup_ontology_context

            for onto in ontologies:
                name = onto.get('name', 'ont')
                source = onto.get('source', '')
                if source and Path(source).exists():
                    setup_ontology_context(source, ns, name=name)
                    meta = ns.get(f"{name}_meta")
                    if meta is not None and hasattr(meta, "summary"):
                        ontology_summaries.append(meta.summary())

        # Setup SPARQL context (remote execution)
        sparql_cfg = ctx.get('sparql', {}) or {}
        endpoint = sparql_cfg.get('endpoint')
        if endpoint:
            from rlm.sparql_handles import setup_sparql_context
            setup_sparql_context(ns, default_endpoint=endpoint)

        # Build context string
        context_parts = [
            "You are constructing and executing SPARQL queries.",
            "Use progressive disclosure: inspect schema first, then run bounded queries.",
            "",
            "## Strategy",
            "1. If local ontology is loaded, use query() to explore schema FIRST (instant, no network)",
            "2. Then test simple queries on remote endpoint",
            "3. Refine iteratively based on results",
            "4. Submit final answer with SUBMIT(answer='...', sparql='...', evidence={...})",
        ]

        if ontology_summaries:
            context_parts.extend(["", "## Loaded ontology summaries:"])
            context_parts.extend(ontology_summaries)
            context_parts.extend([
                "",
                "Use query() function to explore these local ontologies before querying remote endpoint.",
                "Example: query(\"SELECT ?class WHERE { ?class a owl:Class } LIMIT 10\", name='local_schema')"
            ])

        if endpoint:
            context_parts.extend([
                "",
                f"## SPARQL endpoint: {endpoint}",
                "Call sparql_query(query, max_results=100, name='result_name') to execute remote SPARQL.",
                "Remote queries may include GRAPH and SERVICE clauses when needed.",
                "Note: Remote queries are slower than local ontology queries. Use local first for schema exploration.",
            ])

        # Add SUBMIT syntax examples
        context_parts.extend([
            "",
            "## Submitting Results",
            "When ready, use SUBMIT with keyword arguments (NOT positional):",
            "",
            "SUBMIT(",
            "    answer='Your natural language answer explaining what was found',",
            "    sparql='PREFIX ... SELECT ... WHERE { ... }',",
            "    evidence={'key': 'value', 'sample_results': [...]}",
            ")",
            "",
            "IMPORTANT: SUBMIT requires keyword arguments. Do NOT use: SUBMIT(answer, sparql, evidence)",
        ])

        # Add task-specific context hints (if present)
        hints = ctx.get('hints')
        if hints:
            context_parts.extend(["", "## Task Hints:", str(hints)])

        return ns, "\n".join(context_parts)

    def _execute_rlm(self, task: dict, ns: dict, context: str) -> tuple[str, list]:
        """Execute an RLM run for a task (claudette-backed)."""
        from rlm.core import rlm_run

        # Prefer explicit max_iterations, otherwise infer from convergence grader config.
        max_iters = task.get('max_iterations')
        if max_iters is None:
            for grader in task.get('graders', []) or []:
                if grader.get('type') == 'convergence' and grader.get('max_iterations') is not None:
                    max_iters = grader.get('max_iterations')
                    break
        if max_iters is None:
            max_iters = 10

        query = task.get('query', '')

        answer, iterations, _final_ns = rlm_run(
            query=query,
            context=context,
            ns=ns,
            max_iters=max_iters,
            verbose=False,
        )

        return answer, iterations

    def _execute_dspy_rlm(self, task: dict, ns: dict, context: str):
        """Execute an RLM run using DSPy backend.

        Returns:
            DSPyRLMResult with answer, sparql, evidence, trajectory, converged
        """
        from rlm_runtime.engine.dspy_rlm import run_dspy_rlm_with_tools
        from rlm_runtime.tools import make_sparql_tools

        # Prefer explicit max_iterations, otherwise infer from convergence grader config.
        max_iters = task.get('max_iterations')
        if max_iters is None:
            for grader in task.get('graders', []) or []:
                if grader.get('type') == 'convergence' and grader.get('max_iterations') is not None:
                    max_iters = grader.get('max_iterations')
                    break
        if max_iters is None:
            max_iters = 10

        query = task.get('query', '')

        # Extract SPARQL endpoint from task context
        ctx = task.get('context', {}) or {}
        sparql_cfg = ctx.get('sparql', {}) or {}
        endpoint = sparql_cfg.get('endpoint')

        if not endpoint:
            raise ValueError("DSPy backend requires SPARQL endpoint in task context")

        # Extract configuration with defaults
        max_results = sparql_cfg.get('max_results', 100)
        timeout = sparql_cfg.get('timeout', 30.0)
        ontology_name = sparql_cfg.get('name', 'remote')

        # Build tools for remote SPARQL
        tools = make_sparql_tools(
            endpoint=endpoint,
            ns=ns,
            max_results=max_results,
            timeout=timeout
        )

        # Add local ontology tools if ontologies were loaded
        ontologies = ctx.get('ontologies', []) or []
        if ontologies:
            from rlm_runtime.tools import make_ontology_tools

            for onto in ontologies:
                name = onto.get('name', 'ont')
                meta = ns.get(f"{name}_meta")
                if meta is not None:
                    # Get local ontology query tools
                    local_tools = make_ontology_tools(meta, include_sparql=True)

                    # Rename sparql_select to query to match prompt guidance
                    # (prompt says "use query() to explore local ontologies")
                    if 'sparql_select' in local_tools:
                        local_tools['query'] = local_tools.pop('sparql_select')

                    # Add local tools to tool surface
                    tools.update(local_tools)

        # Generate IDs for memory provenance
        run_id = f"eval-{task.get('id', 'unknown')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        trajectory_id = f"t-{uuid.uuid4().hex[:8]}"

        # Run DSPy RLM with tools - returns full result object
        result = run_dspy_rlm_with_tools(
            query=query,
            context=context,
            tools=tools,
            ontology_name=ontology_name,
            ns=ns,
            max_iterations=max_iters,
            verbose=False,
            # Memory parameters
            memory_backend=self.memory_backend,
            retrieve_memories=3 if self.memory_backend else 0,
            extract_memories=bool(self.memory_backend),
            run_id=run_id if self.memory_backend else None,
            trajectory_id=trajectory_id if self.memory_backend else None,
        )

        return result

    def _serialize_dspy_trajectory(self, trajectory: list) -> list:
        """Convert DSPy trajectory to transcript format for graders."""
        transcript = []

        for i, step in enumerate(trajectory, 1):
            if isinstance(step, dict):
                # DSPy trajectory steps are already dicts with 'code' and 'output'
                iter_dict = {
                    'iteration': i,
                    'response': '',  # DSPy doesn't have separate response text
                    'code_blocks': [{
                        'code': step.get('code', ''),
                        'result': {
                            'stdout': step.get('output', ''),
                            'stderr': ''
                        }
                    }]
                }
                transcript.append(iter_dict)

        return transcript

    def _serialize_transcript(self, iterations: list) -> list:
        """Convert RLMIteration objects to serializable dicts."""
        transcript = []

        for iteration in iterations:
            if hasattr(iteration, '__dict__'):
                # RLMIteration object
                iter_dict = {
                    'iteration': getattr(iteration, 'iteration', 0),
                    'response': getattr(iteration, 'response', ''),
                    'code_blocks': []
                }

                for block in getattr(iteration, 'code_blocks', []):
                    block_dict = {
                        'code': getattr(block, 'code', ''),
                        'result': {
                            'stdout': getattr(block.result, 'stdout', '') if hasattr(block, 'result') and block.result else '',
                            'stderr': getattr(block.result, 'stderr', '') if hasattr(block, 'result') and block.result else ''
                        }
                    }
                    iter_dict['code_blocks'].append(block_dict)

                transcript.append(iter_dict)
            elif isinstance(iteration, dict):
                transcript.append(iteration)

        return transcript

    def _get_grader(self, config: dict):
        """Get grader instance from config."""
        grader_type = config.get('type', '')
        grader_class = self.GRADERS.get(grader_type)

        if grader_class is None:
            raise ValueError(f"Unknown grader type: {grader_type}")

        return grader_class.from_config(config)


def save_result(result: EvalResult, output_dir: Path):
    """Save eval result to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save full result
    result_path = output_dir / f"{result.task_id}_{result.timestamp.replace(':', '-')}.json"
    with open(result_path, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)

    # Save transcript separately for debugging
    transcript_dir = output_dir / 'transcripts'
    transcript_dir.mkdir(exist_ok=True)

    for trial in result.trial_results:
        if trial.transcript:
            transcript_path = transcript_dir / f"{result.task_id}_trial{trial.trial_number}.json"
            with open(transcript_path, 'w') as f:
                json.dump(trial.transcript, f, indent=2)

    return result_path
