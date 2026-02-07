#!/usr/bin/env python
"""E-MA-3: Feedback Extraction (Learning From New Corrections).

Tests whether expert corrections can be automatically extracted into
principles + episodes that improve judge accuracy.

Protocol:
    1. Run E-MA-2 aligned judge on 10 eval tasks
    2. Identify errors (expected: Task 2 false negative)
    3. Ingest expert feedback for each error
    4. Re-evaluate all tasks with updated memory
    5. Report before/after accuracy and extracted items

Usage:
    python experiments/reasoningbank/run_e_ma_3.py -v

    # Custom paths
    python experiments/reasoningbank/run_e_ma_3.py \
        --principles experiments/reasoningbank/seed/judge_principles.json \
        --episodes experiments/reasoningbank/seed/judge_episodes.json \
        -v
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import os
from datetime import datetime

import dspy

from experiments.reasoningbank.prototype.run.memalign import (
    evaluate_judge, judge_aligned, load_judge_mem,
    ingest_feedback, print_metrics,
)


# Expert corrections for known errors.
# These simulate an expert reviewing judge mistakes and providing feedback.
EXPERT_CORRECTIONS = {
    # Task 2: False negative - judge rejects correct query
    '2_bacteria_taxa': {
        'expert_verdict': True,
        'expert_reason': (
            'The query is CORRECT. The FROM clause principle applies only to '
            'specialized named graphs (e.g., taxonomy at '
            '<http://sparql.uniprot.org/taxonomy>, UniRef clusters). '
            'Core UniProt data like taxonomic subclass relationships accessed '
            'via rdfs:subClassOf are in the default graph and do NOT require '
            'a FROM clause. The judge is being overly strict.'
        ),
    },
    # Task 121: Sometimes still a false positive - disease URI vs name
    '121_proteins_diseases': {
        'expert_verdict': False,
        'expert_reason': (
            'The query returns disease names (strings via skos:prefLabel) '
            'instead of disease URIs as the ground truth expects. Also missing '
            "type constraint '?disease a up:Disease'. The expected pattern "
            'returns the disease entity directly, not its label.'
        ),
    },
}


def run_e_ma_3(
    eval_tasks_path: str,
    principles_path: str,
    episodes_path: str,
    output_dir: str,
    verbose: bool = False,
):
    """Run E-MA-3: Feedback extraction and re-evaluation."""

    # Load evaluation tasks
    with open(eval_tasks_path) as f:
        eval_tasks = json.load(f)
    print(f"Loaded {len(eval_tasks)} evaluation tasks")

    # Load initial judge memory (E-MA-2 state)
    judge_mem = load_judge_mem(
        principles_path=principles_path,
        episodes_path=episodes_path,
    )
    n_initial = len(judge_mem.all())
    print(f"Initial judge memory: {n_initial} items "
          f"({len([i for i in judge_mem.all() if i.src == 'principle'])} principles, "
          f"{len([i for i in judge_mem.all() if i.src == 'episode'])} episodes)")

    # Step 1: Run E-MA-2 judge (before feedback)
    print("\n" + "=" * 60)
    print("Step 1: E-MA-2 Aligned Judge (BEFORE feedback)")
    print("=" * 60)
    before_fn = lambda task, answer, sparql: judge_aligned(
        task, answer, sparql, judge_mem, verbose=verbose
    )
    before_metrics = evaluate_judge(before_fn, eval_tasks, verbose=verbose)
    print_metrics(before_metrics, "Before Feedback")

    # Step 2: Identify errors and ingest feedback
    print("\n" + "=" * 60)
    print("Step 2: Ingesting Expert Feedback for Errors")
    print("=" * 60)
    all_extracted = []
    n_errors = 0
    n_corrected = 0

    for detail, task_data in zip(before_metrics['details'], eval_tasks):
        if detail['predicted'] == detail['expected']:
            continue  # Correct, no feedback needed

        task_id = detail['task_id']
        n_errors += 1

        # Check if we have expert correction for this error
        correction = EXPERT_CORRECTIONS.get(task_id)
        if not correction:
            # Use the expert_reason from the task file
            correction = {
                'expert_verdict': task_data['expert_verdict'],
                'expert_reason': task_data.get('expert_reason', f'Judge was wrong on {task_id}'),
            }

        print(f"\n  Error: {task_id} ({detail['verdict']})")
        print(f"    Judge said: {detail['predicted']}, Expert says: {correction['expert_verdict']}")
        print(f"    Expert reason: {correction['expert_reason'][:120]}...")

        items = ingest_feedback(
            task=task_data['query'],
            agent_sparql=task_data.get('agent_sparql', ''),
            judge_verdict=detail['predicted'],
            expert_verdict=correction['expert_verdict'],
            expert_reason=correction['expert_reason'],
            judge_mem=judge_mem,
            verbose=verbose,
        )
        all_extracted.extend(items)
        n_corrected += 1

    n_final = len(judge_mem.all())
    print(f"\n  Errors found: {n_errors}")
    print(f"  Corrections ingested: {n_corrected}")
    print(f"  Items extracted: {len(all_extracted)}")
    print(f"  Memory: {n_initial} -> {n_final} items (+{n_final - n_initial})")

    # Show extracted items
    if all_extracted:
        print("\n  Extracted items:")
        for item in all_extracted:
            print(f"    [{item.src}] {item.title}")
            print(f"      {item.content[:100]}...")

    # Step 3: Re-evaluate with updated memory
    print("\n" + "=" * 60)
    print("Step 3: Re-evaluating with Updated Memory (AFTER feedback)")
    print("=" * 60)
    after_fn = lambda task, answer, sparql: judge_aligned(
        task, answer, sparql, judge_mem, verbose=verbose
    )
    after_metrics = evaluate_judge(after_fn, eval_tasks, verbose=verbose)
    print_metrics(after_metrics, "After Feedback")

    # Step 4: Comparison
    print("\n" + "=" * 60)
    print("COMPARISON: Before vs After Feedback")
    print("=" * 60)
    print(f"{'Metric':<12} {'Before':>8} {'After':>8} {'Delta':>8}")
    print("-" * 40)
    for metric in ['accuracy', 'precision', 'recall', 'f1']:
        before_val = before_metrics[metric]
        after_val = after_metrics[metric]
        delta = after_val - before_val
        sign = '+' if delta >= 0 else ''
        print(f"{metric:<12} {before_val:>7.1%} {after_val:>7.1%} {sign}{delta:>6.1%}")

    # Show verdict flips
    flips = []
    for b, a in zip(before_metrics['details'], after_metrics['details']):
        if b['predicted'] != a['predicted']:
            direction = 'fixed' if a['predicted'] == a['expected'] else 'regressed'
            flips.append({
                'task_id': b['task_id'],
                'before': b['verdict'],
                'after': a['verdict'],
                'direction': direction,
            })

    if flips:
        print(f"\nVerdict flips:")
        for f in flips:
            mark = 'OK' if f['direction'] == 'fixed' else 'WRONG'
            print(f"  [{mark}] {f['task_id']}: {f['before']} -> {f['after']} ({f['direction']})")
    else:
        print("\nNo verdict flips.")

    # Check success criteria
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    criteria = {
        'Accuracy improved': after_metrics['accuracy'] > before_metrics['accuracy'],
        'No regressions': all(
            not (b['predicted'] == b['expected'] and a['predicted'] != a['expected'])
            for b, a in zip(before_metrics['details'], after_metrics['details'])
        ),
        'Extracted items generalizable': len(
            [i for i in all_extracted if i.src == 'principle']
        ) > 0,
    }
    for name, passed in criteria.items():
        mark = 'PASS' if passed else 'FAIL'
        print(f"  [{mark}] {name}")

    # Save results
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results = {
        'experiment': 'E-MA-3',
        'timestamp': timestamp,
        'before_metrics': before_metrics,
        'after_metrics': after_metrics,
        'n_errors': n_errors,
        'n_corrected': n_corrected,
        'n_extracted': len(all_extracted),
        'memory_growth': {'before': n_initial, 'after': n_final},
        'verdict_flips': flips,
        'criteria': {k: v for k, v in criteria.items()},
    }
    with open(os.path.join(output_dir, 'feedback_extraction_report.json'), 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Save updated memory
    judge_mem.save(os.path.join(output_dir, 'judge_memory_after_feedback.json'))

    print(f"\nResults saved to {output_dir}/")
    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='E-MA-3: Feedback Extraction')
    parser.add_argument('--eval-tasks',
                        default='experiments/reasoningbank/tasks/judge_eval_tasks.json')
    parser.add_argument('--principles',
                        default='experiments/reasoningbank/seed/judge_principles.json')
    parser.add_argument('--episodes',
                        default='experiments/reasoningbank/seed/judge_episodes.json')
    parser.add_argument('--output-dir',
                        default='experiments/reasoningbank/results/e_ma_3')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4-5-20250929')

    args = parser.parse_args()

    lm = dspy.LM(args.model, temperature=0.0)
    dspy.configure(lm=lm)

    run_e_ma_3(
        eval_tasks_path=args.eval_tasks,
        principles_path=args.principles,
        episodes_path=args.episodes,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )
