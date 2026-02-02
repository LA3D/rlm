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


# Trajectory formatting helper

def format_trajectory(trajectory: list[dict], max_chars: int = 4000) -> str:
    """Format execution trajectory for prompt injection.

    Prioritizes LAST steps (solution) over early exploration steps.

    Args:
        trajectory: List of {code, output} dicts from RLM execution
        max_chars: Maximum total characters to return

    Returns:
        Formatted string showing execution steps
    """
    if not trajectory:
        return "(no trajectory captured)"

    # Format all steps
    parts = []
    for i, step in enumerate(trajectory, 1):
        code = step.get('code', '')
        output = str(step.get('output', ''))[:300]
        parts.append(f"Step {i}:\n```python\n{code}\n```\n→ {output}")

    full_text = "\n".join(parts)

    # If under budget, return all
    if len(full_text) <= max_chars:
        return full_text

    # Otherwise prioritize: first step + last 3 steps (contains solution)
    first = parts[0] if parts else ""
    last_n = parts[-3:] if len(parts) > 3 else parts[1:]

    prioritized = [first, "...(earlier steps omitted)..."] + last_n
    result = "\n".join(prioritized)

    # Final truncation if still over
    return result[:max_chars]


# DSPy Signatures for Judge/Extract

class TrajectoryJudge(dspy.Signature):
    """Judge whether a trajectory successfully completed the task."""
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The agent's final answer")
    sparql: str = dspy.InputField(desc="The SPARQL query produced (if any)")

    success: bool = dspy.OutputField(desc="True if task was completed successfully")
    reason: str = dspy.OutputField(desc="Brief explanation of judgment")


class SuccessExtractor(dspy.Signature):
    """Extract transferable strategies from a successful trajectory.

    IMPORTANT: Base your procedure on the ACTUAL SPARQL query provided, not general knowledge.
    The procedure must reflect the specific patterns used in the sparql field.
    """
    task: str = dspy.InputField(desc="The original question/task")
    trajectory: str = dspy.InputField(desc="Full execution trajectory showing reasoning steps")
    answer: str = dspy.InputField(desc="The successful answer")
    sparql: str = dspy.InputField(desc="The ACTUAL SPARQL query that worked - base your procedure on THIS")

    title: str = dspy.OutputField(desc="Short title for this strategy (≤10 words)")
    procedure: str = dspy.OutputField(desc="Reusable procedure based on the SPARQL pattern that actually worked")


class FailureExtractor(dspy.Signature):
    """Extract lessons from a failed trajectory."""
    task: str = dspy.InputField(desc="The original question/task")
    trajectory: str = dspy.InputField(desc="Full execution trajectory showing reasoning steps")
    answer: str = dspy.InputField(desc="The failed/incomplete answer")
    sparql: str = dspy.InputField(desc="The SPARQL query (if any)")
    failure_reason: str = dspy.InputField(desc="Why the trajectory failed")

    title: str = dspy.OutputField(desc="Short title for this lesson (≤10 words)")
    pitfall: str = dspy.OutputField(desc="Description of what went wrong and how to avoid it")


class ContrastiveExtractor(dspy.Signature):
    """Extract lessons by contrasting success vs failure trajectories."""
    task: str = dspy.InputField(desc="The original question/task")
    success_traj: str = dspy.InputField(desc="Successful execution trajectory")
    failure_traj: str = dspy.InputField(desc="Failed execution trajectory")
    success_answer: str = dspy.InputField(desc="Answer from successful trajectory")
    failure_answer: str = dspy.InputField(desc="Answer from failed trajectory")

    title: str = dspy.OutputField(desc="Short title for this lesson (≤10 words)")
    lesson: str = dspy.OutputField(desc="What distinguished success from failure")


class PatternExtractor(dspy.Signature):
    """Extract common patterns from multiple successful trajectories."""
    task: str = dspy.InputField(desc="The original question/task")
    trajectories: str = dspy.InputField(desc="Multiple successful trajectories separated by ---")

    title: str = dspy.OutputField(desc="Short title for this pattern (≤10 words)")
    pattern: str = dspy.OutputField(desc="Common pattern observed across successes")


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


def extract(res: Result, task: str, judgment: dict, verbose: bool = False,
             temperature: float = 0.3) -> list[Item]:
    """Extract procedures from trajectory using polarity-aware extractors.

    Uses SuccessExtractor for successful trajectories, FailureExtractor for
    failed ones. Returns 1-3 Item objects per paper specification.

    Args:
        res: Result from RLM execution
        task: The original question/task
        judgment: dict with 'success' and 'reason' from judge()
        verbose: If True, print LLM inputs/outputs
        temperature: LLM temperature for extraction (0.3 for grounded output)

    Returns:
        List of 1-3 Item objects with appropriate 'src' polarity
    """
    items = []
    max_items = 3  # Per ReasoningBank paper
    traj_text = format_trajectory(res.trajectory)

    if judgment['success']:
        # Success extraction: transferable strategies
        if verbose:
            print(f"  [extract:success] inputs:")
            print(f"    task: {task[:100]}")
            print(f"    trajectory: {traj_text[:200]}...")
            print(f"    answer: {res.answer[:200]}...")
            print(f"    sparql: {(res.sparql or '')[:100]}")

        ext = dspy.Predict(SuccessExtractor, temperature=temperature)
        # Prepend SPARQL to trajectory so it's prominent
        enhanced_traj = f"SUCCESSFUL SPARQL (this is what worked):\n```sparql\n{res.sparql or 'N/A'}\n```\n\nEXECUTION STEPS:\n{traj_text}"
        try:
            e = ext(task=task, trajectory=enhanced_traj, answer=res.answer, sparql=res.sparql or "")
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
            print(f"    trajectory: {traj_text[:200]}...")
            print(f"    answer: {res.answer[:200]}...")
            print(f"    sparql: {(res.sparql or '')[:100]}")
            print(f"    failure_reason: {judgment['reason']}")

        ext = dspy.Predict(FailureExtractor, temperature=temperature)
        try:
            e = ext(
                task=task,
                trajectory=traj_text,
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


def contrastive_extract(task: str, success_res: Result, failure_res: Result,
                        verbose: bool = False, temperature: float = 1.0) -> list[Item]:
    """Extract lessons by contrasting successful vs failed trajectories.

    Args:
        task: The original question/task
        success_res: Result from successful trajectory
        failure_res: Result from failed trajectory
        verbose: If True, print LLM inputs/outputs
        temperature: LLM temperature for extraction

    Returns:
        List of contrastive lesson Items
    """
    if verbose:
        print(f"  [extract:contrastive] comparing success vs failure")

    ext = dspy.Predict(ContrastiveExtractor, temperature=temperature)
    try:
        e = ext(
            task=task,
            success_traj=format_trajectory(success_res.trajectory),
            failure_traj=format_trajectory(failure_res.trajectory),
            success_answer=success_res.answer,
            failure_answer=failure_res.answer,
        )
        item = Item(
            id=Item.make_id(e.title, e.lesson),
            title=e.title[:100],
            desc=f"Contrastive: {task[:40]}",
            content=e.lesson,
            src='contrastive',
            tags=['matts'],
        )
        if verbose:
            print(f"  [extract:contrastive] title: {e.title}")
            print(f"  [extract:contrastive] lesson: {e.lesson[:200]}...")
        return [item]
    except Exception as ex:
        print(f"  Contrastive extraction failed: {ex}")
        return []


def extract_common_patterns(task: str, successes: list[Result],
                            verbose: bool = False, temperature: float = 1.0) -> list[Item]:
    """Extract common patterns from multiple successful trajectories.

    Args:
        task: The original question/task
        successes: List of successful Result objects
        verbose: If True, print LLM inputs/outputs
        temperature: LLM temperature for extraction

    Returns:
        List of pattern Items
    """
    if verbose:
        print(f"  [extract:pattern] analyzing {len(successes)} successes")

    ext = dspy.Predict(PatternExtractor, temperature=temperature)
    try:
        trajs = "\n---\n".join([format_trajectory(r.trajectory) for r in successes])
        e = ext(task=task, trajectories=trajs)
        item = Item(
            id=Item.make_id(e.title, e.pattern),
            title=e.title[:100],
            desc=f"Pattern: {task[:40]}",
            content=e.pattern,
            src='pattern',
            tags=['matts'],
        )
        if verbose:
            print(f"  [extract:pattern] title: {e.title}")
            print(f"  [extract:pattern] pattern: {e.pattern[:200]}...")
        return [item]
    except Exception as ex:
        print(f"  Pattern extraction failed: {ex}")
        return []


def run_matts_parallel(
    task: str,
    ont: str,
    mem: MemStore,
    cfg: Cfg = None,
    k: int = 3,
    verbose: bool = False,
    dedup: bool = True,
) -> tuple[Result, list[Item]]:
    """Run k parallel trajectories, select best, extract contrastively (MaTTS).

    Memory-aware Test-Time Scaling: runs multiple rollouts in parallel,
    judges each, selects the best, and extracts contrastive lessons from
    comparing successes and failures.

    Args:
        task: The question/task to run
        ont: Path to ontology file
        mem: MemStore instance for procedural memory
        cfg: Layer configuration
        k: Number of parallel rollouts (default: 3)
        verbose: If True, print detailed output
        dedup: If True, deduplicate extracted items

    Returns:
        Tuple of (best Result, list of extracted Items)
    """
    if cfg is None:
        cfg = Cfg()

    if verbose:
        print(f"  [matts] Running {k} parallel rollouts...")

    # 1. Run k rollouts sequentially to avoid shared LM state issues
    results = [run(task, ont, cfg, mem) for _ in range(k)]

    if verbose:
        print(f"  [matts] Completed {len(results)} rollouts")

    # 2. Judge all results
    judgments = [judge(res, task, verbose=False) for res in results]

    if verbose:
        success_count = sum(1 for j in judgments if j['success'])
        print(f"  [matts] Judgments: {success_count}/{k} successful")

    # 3. Categorize results
    successes = [(i, results[i]) for i, j in enumerate(judgments) if j['success']]
    failures = [(i, results[i]) for i, j in enumerate(judgments) if not j['success']]

    # 4. Select best result (prefer success, then lowest iterations)
    if successes:
        best_idx = min(successes, key=lambda x: x[1].iters)[0]
    else:
        # All failed - pick one with most iterations (tried hardest)
        best_idx = max(range(len(results)), key=lambda i: results[i].iters)

    best_result = results[best_idx]
    best_judgment = judgments[best_idx]

    if verbose:
        status = '✓' if best_judgment['success'] else '✗'
        print(f"  [matts] Selected result #{best_idx}: {status} ({best_result.iters} iters)")

    # 5. Extract items
    items = []

    # 5a. Contrastive extraction (success vs failure)
    if successes and failures:
        success_res = successes[0][1]
        failure_res = failures[0][1]
        items.extend(contrastive_extract(task, success_res, failure_res, verbose))

    # 5b. Pattern extraction (multiple successes)
    if len(successes) >= 2:
        success_results = [r for _, r in successes]
        items.extend(extract_common_patterns(task, success_results, verbose))

    # 5c. Standard extraction from best result
    items.extend(extract(best_result, task, best_judgment, verbose))

    # 6. Consolidate with deduplication
    if items:
        added = mem.consolidate(items, dedup=dedup)
        if verbose:
            print(f"  [matts] Consolidated {len(added)}/{len(items)} items")

    return best_result, items


def run_closed_loop(
    tasks: list[dict],
    ont: str,
    mem: MemStore,
    cfg: Cfg = None,
    do_extract: bool = True,
    verbose: bool = False,
    dedup: bool = True,
) -> list[dict]:
    """Run E9-E12 closed-loop learning.

    Flow: for each task → run → judge → extract → consolidate

    Args:
        tasks: List of dicts with 'id' and 'query' keys
        ont: Path to ontology file
        mem: MemStore instance for procedural memory
        cfg: Layer configuration (defaults to L2-only if None)
        do_extract: If True, extract procedures from trajectories
        verbose: If True, print detailed LLM inputs/outputs
        dedup: If True, deduplicate during consolidation (default: True)

    Returns:
        List of result dicts for each task with keys:
        - task_id, query, converged, answer, sparql
        - judgment: {success, reason}
        - items: list of extracted Item objects
    """
    if cfg is None:
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
                added_ids = mem.consolidate(items, dedup=dedup)
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

    # Layer configuration
    parser.add_argument('--l0', action='store_true', help='Enable L0 sense card (~600 chars)')
    parser.add_argument('--l1', action='store_true', help='Enable L1 schema constraints (~1000 chars)')
    parser.add_argument('--l3', action='store_true', help='Enable L3 guide summary (~1000 chars)')

    # Memory persistence
    parser.add_argument('--load-mem', metavar='FILE', help='Load memory from JSON file')
    parser.add_argument('--save-mem', metavar='FILE', help='Save memory to JSON file')

    # MaTTS options
    parser.add_argument('--matts', action='store_true', help='Enable MaTTS parallel scaling')
    parser.add_argument('--matts-k', type=int, default=3, help='Number of MaTTS rollouts (default: 3)')

    # Deduplication control
    parser.add_argument('--no-dedup', action='store_true', help='Disable deduplication during consolidation')

    args = parser.parse_args()

    if args.test:
        # Test judge/extract with mock data (cheap, no RLM)
        test_judge_extract(verbose=args.verbose)
    else:
        # Initialize memory
        mem = MemStore()

        # Load existing memory if specified
        if args.load_mem:
            mem.load(args.load_mem)
            print(f"Loaded {len(mem.all())} items from {args.load_mem}")

        # Build layer configuration from CLI args
        cfg = Cfg(
            l0=Layer(args.l0, 600),
            l1=Layer(args.l1, 1000),
            l2=Layer(True, 2000),  # Always on for memory retrieval
            l3=Layer(args.l3, 1000),
        )

        # Show active layers
        active = []
        if cfg.l0.on: active.append('L0:sense')
        if cfg.l1.on: active.append('L1:schema')
        if cfg.l2.on: active.append('L2:memory')
        if cfg.l3.on: active.append('L3:guide')
        print(f"Active layers: {', '.join(active) if active else 'L2:memory (default)'}")

        # Dedup flag
        dedup = not args.no_dedup
        if not dedup:
            print("Deduplication: DISABLED")

        # Full closed-loop run
        tasks = [
            {'id': 'entity_lookup', 'query': 'What is Activity?'},
            {'id': 'property_find', 'query': 'What properties does Activity have?'},
            {'id': 'hierarchy', 'query': 'What are the subclasses of Entity?'},
        ]

        if args.matts:
            # MaTTS mode: run each task with parallel rollouts
            print(f"MaTTS mode: {args.matts_k} rollouts per task")
            results = []
            for t in tasks:
                print(f"\nTask: {t['id']}")
                res, items = run_matts_parallel(
                    t['query'], args.ont, mem, cfg,
                    k=args.matts_k, verbose=args.verbose, dedup=dedup
                )
                status = '✓' if res.converged else '✗'
                print(f"  {status} Answer: {res.answer[:80]}...")
                for item in items:
                    print(f"  [{item.src}] Extracted: {item.title[:50]}")
                results.append({
                    'task_id': t['id'],
                    'query': t['query'],
                    'converged': res.converged,
                    'answer': res.answer,
                    'sparql': res.sparql,
                    'items': items,
                })
        else:
            # Standard closed-loop mode
            results = run_closed_loop(tasks, args.ont, mem, cfg, args.extract,
                                      verbose=args.verbose, dedup=dedup)

        # Save memory if specified
        save_path = args.save_mem or ('experiments/reasoningbank/results/phase1_memory.json' if args.extract or args.matts else None)
        if save_path:
            mem.save(save_path)
            print(f"\nMemory saved: {len(mem.all())} items → {save_path}")

        # Print summary
        print(f"\n=== Results Summary ===")
        for r in results:
            status = '✓' if r.get('judgment', {}).get('success', r.get('converged', False)) else '✗'
            print(f"{status} {r['task_id']}: {len(r['items'])} items extracted")
