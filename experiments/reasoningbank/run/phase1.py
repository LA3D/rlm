"""Phase 1: Closed-Loop Learning (E9-E12).

ReasoningBank proper: retrieve → run → judge → extract → persist.

- E9: Judge + extract (append-only)
- E10: Add consolidation (merge/supersede)
- E11: Add forgetting (bounded bank)
- E12: MaTTS rollouts (N rollouts, select best, contrastive extraction)
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import dspy
from experiments.reasoningbank.core.mem import MemStore, Item
from experiments.reasoningbank.run.rlm import run, Result
from experiments.reasoningbank.ctx.builder import Cfg, Layer


# DSPy Signatures for Judge/Extract

class TrajectoryJudge(dspy.Signature):
    """Judge whether a trajectory successfully completed the task."""
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The agent's final answer")
    sparql: str = dspy.InputField(desc="The SPARQL query produced (if any)")

    success: bool = dspy.OutputField(desc="True if task was completed successfully")
    reason: str = dspy.OutputField(desc="Brief explanation of judgment")


class SuccessExtractor(dspy.Signature):
    """Extract transferable strategies from a successful trajectory."""
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The successful answer")
    sparql: str = dspy.InputField(desc="The SPARQL query that worked")

    title: str = dspy.OutputField(desc="Short title for this strategy (≤10 words)")
    procedure: str = dspy.OutputField(desc="Reusable procedure explaining why this succeeded")


class FailureExtractor(dspy.Signature):
    """Extract lessons from a failed trajectory."""
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The failed/incomplete answer")
    sparql: str = dspy.InputField(desc="The SPARQL query (if any)")
    failure_reason: str = dspy.InputField(desc="Why the trajectory failed")

    title: str = dspy.OutputField(desc="Short title for this lesson (≤10 words)")
    pitfall: str = dspy.OutputField(desc="Description of what went wrong and how to avoid it")


def judge(res: Result, task: str, verbose: bool = False) -> dict:
    """Judge trajectory success using TrajectoryJudge signature.

    Args:
        res: Result from RLM execution
        task: The original question/task for context
        verbose: If True, print LLM inputs/outputs

    Returns:
        dict with 'success' (bool) and 'reason' (str)
    """
    if not res.converged:
        return {'success': False, 'reason': 'Did not converge'}

    if verbose:
        print(f"  [judge] inputs:")
        print(f"    task: {task[:100]}")
        print(f"    answer: {res.answer[:200]}...")
        print(f"    sparql: {(res.sparql or '')[:100]}")

    judge_fn = dspy.Predict(TrajectoryJudge, temperature=0.0)
    try:
        j = judge_fn(task=task, answer=res.answer, sparql=res.sparql or "")
        result = {'success': j.success, 'reason': j.reason}
        if verbose:
            print(f"  [judge] outputs: success={j.success}, reason={j.reason}")
        return result
    except Exception as e:
        return {'success': False, 'reason': f'Judgment failed: {e}'}


def extract(res: Result, task: str, judgment: dict, verbose: bool = False) -> list[Item]:
    """Extract procedures from trajectory using polarity-aware extractors.

    Uses SuccessExtractor for successful trajectories, FailureExtractor for
    failed ones. Returns 1-3 Item objects per paper specification.

    Args:
        res: Result from RLM execution
        task: The original question/task
        judgment: dict with 'success' and 'reason' from judge()
        verbose: If True, print LLM inputs/outputs

    Returns:
        List of 1-3 Item objects with appropriate 'src' polarity
    """
    items = []
    max_items = 3  # Per ReasoningBank paper

    if judgment['success']:
        # Success extraction: transferable strategies
        if verbose:
            print(f"  [extract:success] inputs:")
            print(f"    task: {task[:100]}")
            print(f"    answer: {res.answer[:200]}...")
            print(f"    sparql: {(res.sparql or '')[:100]}")

        ext = dspy.Predict(SuccessExtractor)
        try:
            e = ext(task=task, answer=res.answer, sparql=res.sparql or "")
            item = Item(
                id=Item.make_id(e.title, e.procedure),
                title=e.title[:100],
                desc=f"Strategy for: {task[:50]}",
                content=e.procedure,
                src='success',
                tags=[],
            )
            items.append(item)
            if verbose:
                print(f"  [extract:success] outputs:")
                print(f"    title: {e.title}")
                print(f"    procedure: {e.procedure[:300]}...")
        except Exception as ex:
            print(f"  Success extraction failed: {ex}")
    else:
        # Failure extraction: lessons learned
        if verbose:
            print(f"  [extract:failure] inputs:")
            print(f"    task: {task[:100]}")
            print(f"    answer: {res.answer[:200]}...")
            print(f"    sparql: {(res.sparql or '')[:100]}")
            print(f"    failure_reason: {judgment['reason']}")

        ext = dspy.Predict(FailureExtractor)
        try:
            e = ext(
                task=task,
                answer=res.answer,
                sparql=res.sparql or "",
                failure_reason=judgment['reason']
            )
            item = Item(
                id=Item.make_id(e.title, e.pitfall),
                title=e.title[:100],
                desc=f"Pitfall for: {task[:50]}",
                content=e.pitfall,
                src='failure',
                tags=[],
            )
            items.append(item)
            if verbose:
                print(f"  [extract:failure] outputs:")
                print(f"    title: {e.title}")
                print(f"    pitfall: {e.pitfall[:300]}...")
        except Exception as ex:
            print(f"  Failure extraction failed: {ex}")

    return items[:max_items]

def run_closed_loop(
    tasks: list[dict],
    ont: str,
    mem: MemStore,
    do_extract: bool = True,
    verbose: bool = False,
) -> list[dict]:
    """Run E9-E12 closed-loop learning.

    Flow: for each task → run → judge → extract → consolidate

    Args:
        tasks: List of dicts with 'id' and 'query' keys
        ont: Path to ontology file
        mem: MemStore instance for procedural memory
        do_extract: If True, extract procedures from trajectories
        verbose: If True, print detailed LLM inputs/outputs

    Returns:
        List of result dicts for each task with keys:
        - task_id, query, converged, answer, sparql
        - judgment: {success, reason}
        - items: list of extracted Item objects
    """
    cfg = Cfg(l2=Layer(True, 2000))
    results = []

    for t in tasks:
        print(f"\nTask: {t['id']}")
        res = run(t['query'], ont, cfg, mem)

        # Step 1: Judge with task context
        j = judge(res, t['query'], verbose=verbose)
        status = '✓' if j['success'] else '✗'
        print(f"  {status} Judgment: {j['reason'][:60]}")

        # Build result record
        record = {
            'task_id': t['id'],
            'query': t['query'],
            'converged': res.converged,
            'answer': res.answer,
            'sparql': res.sparql,
            'judgment': j,
            'items': [],
        }

        # Step 2-3: Extract and consolidate
        if do_extract:
            items = extract(res, t['query'], j, verbose=verbose)
            if items:
                added_ids = mem.consolidate(items)
                record['items'] = items
                for item in items:
                    polarity = f"[{item.src}]"
                    print(f"  {polarity} Extracted: {item.title[:50]}")

        results.append(record)

    return results


def test_judge_extract(verbose: bool = True):
    """Test judge/extract with mock Results (no RLM calls).

    Uses synthetic Result objects to test the closed-loop logic
    without expensive LLM calls from run().
    """
    from experiments.reasoningbank.core.instrument import Metrics

    print("=== Testing judge/extract with mock Results ===\n")
    mem = MemStore()

    # Mock successful result
    success_res = Result(
        answer="Activity is a class in PROV-O representing something that occurs over time and acts upon or with entities.",
        sparql="SELECT ?class WHERE { ?class a owl:Class . FILTER(CONTAINS(STR(?class), 'Activity')) }",
        converged=True,
        iters=3,
        leakage=Metrics(),
        trace=[],
    )

    # Mock failed result (no SPARQL)
    failure_res = Result(
        answer="I couldn't find information about Activity in the ontology.",
        sparql=None,
        converged=True,
        iters=5,
        leakage=Metrics(),
        trace=[],
    )

    # Mock non-converged result
    nonconv_res = Result(
        answer="Error: max iterations",
        sparql=None,
        converged=False,
        iters=12,
        leakage=Metrics(),
        trace=[],
    )

    test_cases = [
        ("success_case", "What is Activity?", success_res),
        ("failure_case", "What is Activity?", failure_res),
        ("nonconverged_case", "What is Activity?", nonconv_res),
    ]

    results = []
    for name, task, res in test_cases:
        print(f"\n--- {name} ---")
        print(f"Task: {task}")
        print(f"Answer: {res.answer[:100]}...")
        print(f"Converged: {res.converged}")

        j = judge(res, task, verbose=verbose)
        print(f"Judgment: success={j['success']}, reason={j['reason']}")

        items = extract(res, task, j, verbose=verbose)
        print(f"Extracted {len(items)} items:")
        for item in items:
            print(f"  [{item.src}] {item.title}")
            print(f"    Content: {item.content[:200]}...")

        if items:
            mem.consolidate(items)

        results.append({'name': name, 'judgment': j, 'items': items})

    print(f"\n=== Summary ===")
    print(f"Memory store: {len(mem.all())} items")
    for item in mem.all():
        print(f"  [{item.src}] {item.id}: {item.title}")

    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run Phase 1 closed-loop experiments')
    parser.add_argument('--ont', default='ontology/prov.ttl', help='Ontology path')
    parser.add_argument('--extract', action='store_true', help='Enable extraction')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test', action='store_true', help='Run mock test (no RLM calls)')
    args = parser.parse_args()

    if args.test:
        # Test judge/extract with mock data (cheap, no RLM)
        test_judge_extract(verbose=args.verbose)
    else:
        # Full closed-loop run
        mem = MemStore()
        tasks = [
            {'id': 'entity_lookup', 'query': 'What is Activity?'},
            {'id': 'property_find', 'query': 'What properties does Activity have?'},
            {'id': 'hierarchy', 'query': 'What are the subclasses of Entity?'},
        ]

        results = run_closed_loop(tasks, args.ont, mem, args.extract, verbose=args.verbose)

        # Save memory
        if args.extract:
            mem.save('experiments/reasoningbank/results/phase1_memory.json')
            print(f"\nMemory saved: {len(mem.all())} items")

        # Print summary
        print(f"\n=== Results Summary ===")
        for r in results:
            status = '✓' if r['judgment']['success'] else '✗'
            print(f"{status} {r['task_id']}: {len(r['items'])} items extracted")
