"""Task runner for executing RLM evaluation tasks."""

import math
import json
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
    }

    def __init__(self, config: dict = None):
        """Initialize task runner.

        Args:
            config: Optional global configuration dict
        """
        self.config = config or {}

    def run_task(self, task_path: Path, num_trials: int = None) -> EvalResult:
        """Run all trials for a task.

        Args:
            task_path: Path to task YAML file
            num_trials: Override number of trials (uses task default if None)

        Returns:
            EvalResult with all trial results and metrics
        """
        task = yaml.safe_load(task_path.read_text())
        trials = num_trials or task.get('trials', 5)

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

        return EvalResult(
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

    def _run_single_trial(self, task: dict, trial_num: int) -> TrialResult:
        """Execute one trial of a task."""
        try:
            # Setup namespace with ontologies
            ns = self._setup_namespace(task)

            # Run RLM
            answer, iterations = self._execute_rlm(task, ns)

            # Convert iterations to serializable format
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
                transcript=transcript
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

    def _setup_namespace(self, task: dict) -> dict:
        """Setup namespace with ontologies and tools."""
        ns = {}

        # Import and setup ontology tools if configured
        context = task.get('context', {})
        ontologies = context.get('ontologies', [])

        if ontologies:
            try:
                from rdflib import Dataset
                from rlm.dataset import DatasetMeta, mount_ontology
                from rlm.ontology import setup_ontology_context

                # Create dataset
                ds = Dataset()
                ds_meta = DatasetMeta(ds, name='eval_ds')
                ns['ds_meta'] = ds_meta

                # Mount ontologies
                for onto in ontologies:
                    name = onto.get('name', 'onto')
                    source = onto.get('source', '')

                    if source and Path(source).exists():
                        mount_ontology(ds_meta, name, source)

                # Setup ontology context
                setup_ontology_context(ns, ds_meta=ds_meta)

            except ImportError as e:
                print(f"Warning: Could not setup ontology context: {e}")

        return ns

    def _execute_rlm(self, task: dict, ns: dict) -> tuple[str, list]:
        """Execute RLM run for task."""
        try:
            from rlm.core import rlm_run

            max_iters = task.get('max_iterations', 15)
            query = task.get('query', '')

            answer, iterations = rlm_run(
                task=query,
                ns=ns,
                max_iterations=max_iters
            )

            return answer, iterations

        except ImportError:
            # Fallback for testing without full RLM
            return "Mock answer", []

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
