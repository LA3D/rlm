"""MemAlign: Judge Alignment via Dual-Memory Feedback.

Implements E-MA-0 through E-MA-6: baseline measurement, semantic memory
(principles), episodic memory (edge cases), feedback extraction,
memory scaling, MaTTS integration, and ALHF routing.

Architecture:
    Expert Feedback (natural language corrections on judge errors)
        |
        +---> PrincipleExtractor -> Semantic Memory (general rules)
        +---> EpisodeExtractor   -> Episodic Memory (specific cases)

    At judgment time:
        All principles + top-k relevant episodes -> Working Memory -> Enhanced Judge
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
from pathlib import Path

import dspy

from experiments.reasoningbank.prototype.core.mem import MemStore, Item
from experiments.reasoningbank.prototype.packers.judge_mem import pack_working_memory


# ---------------------------------------------------------------------------
# DSPy Signatures
# ---------------------------------------------------------------------------

class AlignedTrajectoryJudge(dspy.Signature):
    """Judge whether a trajectory successfully completed the task.
    Apply domain principles and learn from past cases.

    IMPORTANT: Read ALL principles carefully before judging. If a principle
    applies to this case, explicitly reference it in your reasoning.
    Also check past cases for similar situations.
    """
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The agent's final answer")
    sparql: str = dspy.InputField(desc="The SPARQL query produced")
    principles: str = dspy.InputField(desc="Evaluation principles from expert feedback - apply ALL relevant ones")
    past_cases: str = dspy.InputField(desc="Similar past cases with expert corrections - check for matching situations")

    success: bool = dspy.OutputField(desc="True if completed successfully, applying all relevant principles")
    reason: str = dspy.OutputField(desc="Explanation referencing applicable principles and past cases by name")


class PrincipleExtractor(dspy.Signature):
    """Distill a generalizable evaluation principle from expert feedback.

    The principle should be applicable to FUTURE similar cases, not just
    this specific task. Focus on the general pattern, not the specific query.
    """
    task: str = dspy.InputField(desc="The original task")
    agent_sparql: str = dspy.InputField(desc="The SPARQL query the agent produced")
    judge_verdict: bool = dspy.InputField(desc="What the judge said (may be wrong)")
    expert_verdict: bool = dspy.InputField(desc="What the expert says is correct")
    expert_reason: str = dspy.InputField(desc="Expert's natural language explanation")

    title: str = dspy.OutputField(desc="Short principle title (<=10 words)")
    principle: str = dspy.OutputField(desc="Generalizable evaluation rule applicable to future cases")
    scope: str = dspy.OutputField(desc="When this principle applies (e.g., 'named graph queries', 'entity lookups')")


class EpisodeExtractor(dspy.Signature):
    """Create a specific edge case record from expert feedback.

    The episode should capture the specific details of this case for
    future reference when judging similar tasks.
    """
    task: str = dspy.InputField(desc="The original task")
    agent_sparql: str = dspy.InputField(desc="The SPARQL produced")
    expert_verdict: bool = dspy.InputField(desc="Correct verdict")
    expert_reason: str = dspy.InputField(desc="Expert explanation")

    title: str = dspy.OutputField(desc="Short case title (<=10 words)")
    case_record: str = dspy.OutputField(desc="Case description with task, SPARQL, verdict, and reasoning")


class AlignedTrajectoryComparator(dspy.Signature):
    """Compare k trajectories and select the best approach.
    Use domain principles and past cases to evaluate query quality.

    Prefer: canonical patterns, complete projections, proper type constraints,
    correct named graph usage. Penalize: complex workarounds, missing clauses.
    """
    task: str = dspy.InputField(desc="The original question/task")
    trajectories_summary: str = dspy.InputField(
        desc="k trajectories with their SPARQL queries, numbered 0 to k-1")
    principles: str = dspy.InputField(desc="Evaluation principles from expert feedback")
    past_cases: str = dspy.InputField(desc="Similar past cases with expert corrections")

    best_index: int = dspy.OutputField(desc="0-indexed best trajectory number")
    ranking_reason: str = dspy.OutputField(desc="Why this trajectory is best, referencing principles")


class FeedbackRouter(dspy.Signature):
    """Route expert feedback to appropriate system components.

    Determine whether feedback should go to:
    - Judge memory (evaluation principles/episodes)
    - Agent L1 constraints (hard rules for query construction)
    - Agent L2 seeds (strategies for memory bank)

    Output 'N/A' for components that don't need this feedback.
    """
    feedback: str = dspy.InputField(desc="Expert's natural language feedback")
    task: str = dspy.InputField(desc="The original task")
    agent_sparql: str = dspy.InputField(desc="The SPARQL the agent produced")

    judge_principle: str = dspy.OutputField(desc="Principle for judge evaluation, or 'N/A'")
    agent_constraint: str = dspy.OutputField(desc="L1 hard constraint for agent query construction, or 'N/A'")
    agent_seed: str = dspy.OutputField(desc="L2 seed strategy for agent memory, or 'N/A'")


# ---------------------------------------------------------------------------
# Memory Loading
# ---------------------------------------------------------------------------

def load_judge_mem(
    principles_path: str = None,
    episodes_path: str = None,
) -> MemStore:
    """Load judge memory from seed files.

    Args:
        principles_path: Path to judge_principles.json
        episodes_path: Path to judge_episodes.json

    Returns:
        MemStore populated with principles and/or episodes
    """
    mem = MemStore()

    if principles_path:
        with open(principles_path) as f:
            for d in json.load(f):
                mem.add(Item(**d))

    if episodes_path:
        with open(episodes_path) as f:
            for d in json.load(f):
                mem.add(Item(**d))

    return mem


# ---------------------------------------------------------------------------
# Judge Functions
# ---------------------------------------------------------------------------

def judge_baseline(task: str, answer: str, sparql: str, verbose: bool = False) -> dict:
    """Judge using original TrajectoryJudge (no alignment).

    This is the baseline judge from phase1.py, reproduced here for
    consistent evaluation in the MemAlign harness.

    Args:
        task: The original question/task
        answer: The agent's final answer
        sparql: The SPARQL query produced
        verbose: Print inputs/outputs

    Returns:
        dict with 'success' (bool) and 'reason' (str)
    """
    from experiments.reasoningbank.prototype.run.phase1 import TrajectoryJudge

    if verbose:
        print(f"  [judge:baseline] task: {task[:80]}")
        print(f"  [judge:baseline] sparql: {sparql[:100]}")

    judge_fn = dspy.Predict(TrajectoryJudge, temperature=0.0)
    try:
        j = judge_fn(task=task, answer=answer, sparql=sparql or "")
        result = {'success': j.success, 'reason': j.reason}
        if verbose:
            print(f"  [judge:baseline] -> success={j.success}, reason={j.reason[:80]}")
        return result
    except Exception as e:
        return {'success': False, 'reason': f'Judgment failed: {e}'}


def judge_aligned(
    task: str, answer: str, sparql: str,
    judge_mem: MemStore,
    k_episodes: int = 3,
    verbose: bool = False,
) -> dict:
    """Judge with MemAlign working memory (principles + episodes).

    Retrieves ALL principles and top-k relevant episodes, packs them
    into working memory, and runs the AlignedTrajectoryJudge.

    Args:
        task: The original question/task
        answer: The agent's final answer
        sparql: The SPARQL query produced
        judge_mem: MemStore with principles and episodes
        k_episodes: Number of episodes to retrieve
        verbose: Print inputs/outputs

    Returns:
        dict with 'success' (bool) and 'reason' (str)
    """
    # 1. Load ALL principles (semantic memory)
    all_principles = [item for item in judge_mem.all() if item.src == 'principle']

    # 2. Retrieve relevant episodes (episodic memory)
    episode_hits = judge_mem.search(
        f"{task} {sparql}", k=k_episodes, polarity='episode'
    )
    episode_ids = [h['id'] for h in episode_hits]
    episodes = judge_mem.get(episode_ids, max_n=max(k_episodes, len(episode_ids))) if episode_ids else []

    if verbose:
        print(f"  [judge:aligned] {len(all_principles)} principles, {len(episodes)} episodes retrieved")
        for p in all_principles:
            print(f"    principle: {p.title}")
        for e in episodes:
            print(f"    episode: {e.title}")

    # 3. Pack working memory
    principles_text, episodes_text = pack_working_memory(all_principles, episodes)

    # 4. Run aligned judge
    judge_fn = dspy.Predict(AlignedTrajectoryJudge, temperature=0.0)
    try:
        j = judge_fn(
            task=task,
            answer=answer,
            sparql=sparql or "",
            principles=principles_text,
            past_cases=episodes_text,
        )
        result = {'success': j.success, 'reason': j.reason}
        if verbose:
            print(f"  [judge:aligned] -> success={j.success}")
            print(f"  [judge:aligned] reason: {j.reason[:120]}")
        return result
    except Exception as e:
        return {'success': False, 'reason': f'Aligned judgment failed: {e}'}


# ---------------------------------------------------------------------------
# Evaluation Harness (E-MA-0)
# ---------------------------------------------------------------------------

def evaluate_judge(
    judge_fn,
    eval_tasks: list[dict],
    verbose: bool = False,
) -> dict:
    """Run judge on eval tasks, compare to expert verdicts.

    Args:
        judge_fn: Callable(task, answer, sparql) -> {'success': bool, 'reason': str}
        eval_tasks: Tasks with 'expert_verdict', 'agent_sparql', etc.
        verbose: Print per-task details

    Returns:
        dict with accuracy, precision, recall, f1, and per-task details
    """
    details = []
    tp = fp = tn = fn = 0

    for t in eval_tasks:
        task_id = t['id']
        judge_result = judge_fn(
            task=t['query'],
            answer=t.get('agent_answer', ''),
            sparql=t.get('agent_sparql', ''),
        )
        predicted = judge_result['success']
        expected = t['expert_verdict']

        if predicted and expected:
            tp += 1; verdict = 'TP'
        elif predicted and not expected:
            fp += 1; verdict = 'FP'
        elif not predicted and not expected:
            tn += 1; verdict = 'TN'
        else:
            fn += 1; verdict = 'FN'

        detail = {
            'task_id': task_id,
            'predicted': predicted,
            'expected': expected,
            'verdict': verdict,
            'judge_reason': judge_result['reason'],
            'expert_reason': t.get('expert_reason', ''),
        }
        details.append(detail)

        if verbose:
            mark = 'OK' if predicted == expected else 'WRONG'
            print(f"  [{mark}] {task_id}: predicted={predicted}, expected={expected} ({verdict})")
            if predicted != expected:
                print(f"    Judge: {judge_result['reason'][:100]}")
                print(f"    Expert: {t.get('expert_reason', '')[:100]}")

    total = len(eval_tasks)
    correct = tp + tn
    accuracy = correct / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'total': total,
        'correct': correct,
        'details': details,
    }


# ---------------------------------------------------------------------------
# Feedback Extraction (E-MA-3)
# ---------------------------------------------------------------------------

def ingest_feedback(
    task: str,
    agent_sparql: str,
    judge_verdict: bool,
    expert_verdict: bool,
    expert_reason: str,
    judge_mem: MemStore,
    verbose: bool = False,
) -> list[Item]:
    """Process expert feedback -> extract principle + episode -> add to judge memory.

    Args:
        task: The original task
        agent_sparql: The SPARQL the agent produced
        judge_verdict: What the judge said (may be wrong)
        expert_verdict: What the expert says is correct
        expert_reason: Expert's natural language explanation
        judge_mem: MemStore to add extracted items to
        verbose: Print extraction details

    Returns:
        List of newly created Items (principle + episode)
    """
    items = []

    # Extract principle (generalizable rule)
    if verbose:
        print(f"  [ingest] Extracting principle from feedback...")

    p_ext = dspy.Predict(PrincipleExtractor, temperature=0.3)
    try:
        p = p_ext(
            task=task,
            agent_sparql=agent_sparql,
            judge_verdict=judge_verdict,
            expert_verdict=expert_verdict,
            expert_reason=expert_reason,
        )
        principle = Item(
            id=Item.make_id(p.title, p.principle),
            title=p.title[:100],
            desc=f"Scope: {p.scope[:80]}",
            content=p.principle,
            src='principle',
            tags=['extracted'],
        )
        items.append(principle)
        if verbose:
            print(f"    Principle: {p.title}")
            print(f"    Scope: {p.scope[:80]}")
    except Exception as e:
        print(f"  Principle extraction failed: {e}")

    # Extract episode (specific case)
    if verbose:
        print(f"  [ingest] Extracting episode from feedback...")

    e_ext = dspy.Predict(EpisodeExtractor, temperature=0.3)
    try:
        e = e_ext(
            task=task,
            agent_sparql=agent_sparql,
            expert_verdict=expert_verdict,
            expert_reason=expert_reason,
        )
        episode = Item(
            id=Item.make_id(e.title, e.case_record),
            title=e.title[:100],
            desc=f"Case for: {task[:50]}",
            content=e.case_record,
            src='episode',
            tags=['extracted'],
        )
        items.append(episode)
        if verbose:
            print(f"    Episode: {e.title}")
    except Exception as e:
        print(f"  Episode extraction failed: {e}")

    # Consolidate into judge memory
    added = judge_mem.consolidate(items, dedup=True)
    if verbose:
        print(f"  [ingest] Added {len(added)}/{len(items)} items to judge memory")

    return items


# ---------------------------------------------------------------------------
# MaTTS Integration (E-MA-5)
# ---------------------------------------------------------------------------

def compare_trajectories(
    task: str,
    trajectories: list[dict],
    judge_mem: MemStore,
    k_episodes: int = 3,
    verbose: bool = False,
) -> dict:
    """Compare k trajectories and select the best using aligned judgment.

    Args:
        task: The original question/task
        trajectories: List of dicts with 'sparql', 'answer', 'iters' keys
        judge_mem: MemStore with principles and episodes
        k_episodes: Number of episodes to retrieve
        verbose: Print details

    Returns:
        dict with 'best_index', 'ranking_reason'
    """
    # Build trajectory summary
    summary_parts = []
    for i, t in enumerate(trajectories):
        sparql = t.get('sparql', '(no SPARQL)')
        answer = t.get('answer', '(no answer)')[:200]
        iters = t.get('iters', '?')
        summary_parts.append(
            f"--- Trajectory {i} ({iters} iterations) ---\n"
            f"SPARQL:\n```sparql\n{sparql}\n```\n"
            f"Answer: {answer}"
        )
    summary = '\n\n'.join(summary_parts)

    # Load principles and episodes
    all_principles = [item for item in judge_mem.all() if item.src == 'principle']
    episode_hits = judge_mem.search(task, k=k_episodes, polarity='episode')
    episode_ids = [h['id'] for h in episode_hits]
    episodes = judge_mem.get(episode_ids, max_n=max(k_episodes, len(episode_ids))) if episode_ids else []

    principles_text, episodes_text = pack_working_memory(all_principles, episodes)

    if verbose:
        print(f"  [compare] {len(trajectories)} trajectories, "
              f"{len(all_principles)} principles, {len(episodes)} episodes")

    compare_fn = dspy.Predict(AlignedTrajectoryComparator, temperature=0.0)
    try:
        c = compare_fn(
            task=task,
            trajectories_summary=summary,
            principles=principles_text,
            past_cases=episodes_text,
        )
        result = {'best_index': c.best_index, 'ranking_reason': c.ranking_reason}
        if verbose:
            print(f"  [compare] Best: trajectory {c.best_index}")
            print(f"  [compare] Reason: {c.ranking_reason[:120]}")
        return result
    except Exception as e:
        return {'best_index': 0, 'ranking_reason': f'Comparison failed: {e}'}


def select_for_expert_review(
    rollout_results: list[dict],
    judgments: list[dict],
) -> list[dict]:
    """Surface most informative cases from k rollouts for expert review.

    Priority:
    1. Split judgments (some success, some failure) - most informative
    2. All-pass with high diversity in SPARQL - potential false positives
    3. All-fail - need investigation

    Args:
        rollout_results: List of dicts with 'sparql', 'answer', etc.
        judgments: Corresponding list of judge dicts with 'success', 'reason'

    Returns:
        Sorted list of review candidates with priority scores
    """
    candidates = []
    successes = [i for i, j in enumerate(judgments) if j['success']]
    failures = [i for i, j in enumerate(judgments) if not j['success']]

    if successes and failures:
        # Split judgments: most informative
        for i in successes:
            candidates.append({
                'index': i,
                'priority': 'high',
                'reason': 'Success in split judgment - verify not false positive',
                'sparql': rollout_results[i].get('sparql', ''),
                'judgment': judgments[i],
            })
        for i in failures:
            candidates.append({
                'index': i,
                'priority': 'high',
                'reason': 'Failure in split judgment - verify not false negative',
                'sparql': rollout_results[i].get('sparql', ''),
                'judgment': judgments[i],
            })
    elif len(successes) == len(rollout_results):
        # All pass - check for diversity (potential false positives)
        sparqls = [r.get('sparql', '') for r in rollout_results]
        unique = len(set(sparqls))
        if unique > 1:
            for i in range(len(rollout_results)):
                candidates.append({
                    'index': i,
                    'priority': 'medium',
                    'reason': f'All-pass with {unique} distinct SPARQL variants',
                    'sparql': rollout_results[i].get('sparql', ''),
                    'judgment': judgments[i],
                })
        else:
            candidates.append({
                'index': 0,
                'priority': 'low',
                'reason': 'All-pass unanimous - spot check',
                'sparql': rollout_results[0].get('sparql', ''),
                'judgment': judgments[0],
            })
    else:
        # All fail
        for i in failures:
            candidates.append({
                'index': i,
                'priority': 'high',
                'reason': 'All-fail - investigate root cause',
                'sparql': rollout_results[i].get('sparql', ''),
                'judgment': judgments[i],
            })

    # Sort: high > medium > low
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    candidates.sort(key=lambda c: priority_order.get(c['priority'], 3))
    return candidates


# ---------------------------------------------------------------------------
# ALHF Routing (E-MA-6)
# ---------------------------------------------------------------------------

def route_and_store(
    feedback: str,
    task_context: dict,
    judge_mem: MemStore,
    agent_mem: MemStore = None,
    verbose: bool = False,
) -> dict:
    """Route expert feedback to judge memory and/or agent memory.

    Args:
        feedback: Expert's natural language feedback
        task_context: dict with 'task', 'agent_sparql' keys
        judge_mem: Judge memory store (principles + episodes)
        agent_mem: Agent L2 memory store (optional)
        verbose: Print routing details

    Returns:
        dict with 'judge_items', 'agent_items', 'routing' keys
    """
    task = task_context.get('task', '')
    agent_sparql = task_context.get('agent_sparql', '')

    # Route feedback
    router = dspy.Predict(FeedbackRouter, temperature=0.3)
    try:
        r = router(feedback=feedback, task=task, agent_sparql=agent_sparql)
    except Exception as e:
        return {'judge_items': [], 'agent_items': [], 'routing': {'error': str(e)}}

    routing = {
        'judge_principle': r.judge_principle,
        'agent_constraint': r.agent_constraint,
        'agent_seed': r.agent_seed,
    }

    if verbose:
        print(f"  [route] Judge principle: {r.judge_principle[:80]}")
        print(f"  [route] Agent constraint: {r.agent_constraint[:80]}")
        print(f"  [route] Agent seed: {r.agent_seed[:80]}")

    judge_items = []
    agent_items = []

    # Store judge principle if applicable
    if r.judge_principle and r.judge_principle.strip().upper() != 'N/A':
        principle = Item(
            id=Item.make_id('routed_principle', r.judge_principle),
            title=f"Routed: {task[:40]}",
            desc=f"From expert feedback on: {task[:50]}",
            content=r.judge_principle,
            src='principle',
            tags=['routed', 'alhf'],
        )
        judge_mem.consolidate([principle], dedup=True)
        judge_items.append(principle)

    # Store agent constraint if applicable
    if agent_mem and r.agent_constraint and r.agent_constraint.strip().upper() != 'N/A':
        constraint = Item(
            id=Item.make_id('routed_constraint', r.agent_constraint),
            title=f"Constraint: {task[:40]}",
            desc=f"L1 constraint from feedback",
            content=r.agent_constraint,
            src='seed',
            tags=['constraint', 'alhf', 'l1'],
        )
        agent_mem.consolidate([constraint], dedup=True)
        agent_items.append(constraint)

    # Store agent seed if applicable
    if agent_mem and r.agent_seed and r.agent_seed.strip().upper() != 'N/A':
        seed = Item(
            id=Item.make_id('routed_seed', r.agent_seed),
            title=f"Seed: {task[:40]}",
            desc=f"L2 seed strategy from feedback",
            content=r.agent_seed,
            src='seed',
            tags=['seed', 'alhf', 'l2'],
        )
        agent_mem.consolidate([seed], dedup=True)
        agent_items.append(seed)

    return {
        'judge_items': judge_items,
        'agent_items': agent_items,
        'routing': routing,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_metrics(metrics: dict, label: str = ""):
    """Pretty-print evaluation metrics."""
    if label:
        print(f"\n=== {label} ===")
    print(f"  Accuracy:  {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})")
    print(f"  Precision: {metrics['precision']:.1%}")
    print(f"  Recall:    {metrics['recall']:.1%}")
    print(f"  F1:        {metrics['f1']:.1%}")
    print(f"  TP={metrics['tp']} FP={metrics['fp']} TN={metrics['tn']} FN={metrics['fn']}")


if __name__ == '__main__':
    import argparse
    import os

    parser = argparse.ArgumentParser(description='MemAlign: Judge Alignment via Dual-Memory Feedback')
    parser.add_argument('--eval-tasks', default='experiments/reasoningbank/tasks/judge_eval_tasks.json',
                        help='Path to evaluation tasks JSON')
    parser.add_argument('--judge-mem', metavar='FILE',
                        help='Path to judge principles JSON (enables aligned judge)')
    parser.add_argument('--episodes', metavar='FILE',
                        help='Path to judge episodes JSON')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Save metrics to JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--compare', action='store_true',
                        help='Run both baseline and aligned judges, compare results')

    args = parser.parse_args()

    # Load evaluation tasks
    with open(args.eval_tasks) as f:
        eval_tasks = json.load(f)
    print(f"Loaded {len(eval_tasks)} evaluation tasks")

    # Configure DSPy
    lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', temperature=0.0)
    dspy.configure(lm=lm)

    results = {}

    if args.compare or not args.judge_mem:
        # Run baseline judge
        print("\n--- Baseline Judge (no alignment) ---")
        baseline_metrics = evaluate_judge(
            judge_fn=judge_baseline,
            eval_tasks=eval_tasks,
            verbose=args.verbose,
        )
        print_metrics(baseline_metrics, "Baseline")
        results['baseline'] = baseline_metrics

    if args.judge_mem:
        # Load judge memory
        judge_mem = load_judge_mem(
            principles_path=args.judge_mem,
            episodes_path=args.episodes,
        )
        print(f"\nJudge memory: {len(judge_mem.all())} items")
        for item in judge_mem.all():
            print(f"  [{item.src}] {item.title}")

        # Run aligned judge
        print("\n--- Aligned Judge ---")
        aligned_fn = lambda task, answer, sparql: judge_aligned(
            task, answer, sparql, judge_mem, verbose=args.verbose
        )
        aligned_metrics = evaluate_judge(
            judge_fn=aligned_fn,
            eval_tasks=eval_tasks,
            verbose=args.verbose,
        )
        print_metrics(aligned_metrics, "Aligned")
        results['aligned'] = aligned_metrics

    # Save results
    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        # Strip non-serializable items from details
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nMetrics saved to {args.output}")
