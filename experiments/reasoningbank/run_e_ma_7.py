#!/usr/bin/env python
"""E-MA-7: ALHF Routing Fixes (Paired Episodes, Specificity, Dual-Routing).

Fixes three failure modes identified in E-MA-6:
    1. Context dilution — Principles without grounding episodes caused regression
       Fix: Paired principle+episode in route_and_store
    2. Specificity conflict — Exception principles outvoted by general ones
       Fix: scope metadata + [EXCEPTION] annotation + specificity rule in judge
    3. Under-routing — FeedbackRouter only routed 4/10 to judge (40%)
       Fix: Dual-routing bias in FeedbackRouter signature

Protocol:
    1. Start from E-MA-2 state (5 principles + 6 episodes) — same as E-MA-6
    2. Run aligned judge BEFORE routing (baseline for this run)
    3. Route ALL 10 tasks via updated FeedbackRouter + paired episode generation
    4. Run aligned judge AFTER routing
    5. Compare with E-MA-6 baseline results

Success Criteria:
    - Routing accuracy >= 70% (E-MA-6 was 40%)
    - No regressions from before to after (E-MA-6 had 1)
    - Feedback reaches both components >= 5/10 (E-MA-6 was 4/10)
    - Memory bounded (judge < 30, agent < 20)

Usage:
    python experiments/reasoningbank/run_e_ma_7.py -v
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import os
from datetime import datetime

import dspy

from experiments.reasoningbank.prototype.core.mem import MemStore, Item
from experiments.reasoningbank.prototype.run.memalign import (
    evaluate_judge, judge_aligned, load_judge_mem, route_and_store,
    print_metrics,
)
from experiments.reasoningbank.run_e_ma_6 import ROUTING_TASKS


# E-MA-6 baseline results for comparison
E_MA_6_BASELINE = {
    'before_accuracy': 0.60,
    'after_accuracy': 0.50,
    'routing_accuracy': 0.40,
    'routed_judge': 4,
    'routed_agent': 8,
    'routed_both': 4,
    'regressions': 1,
    'fixes': 0,
}


def run_e_ma_7(
    principles_path: str,
    episodes_path: str,
    output_dir: str,
    verbose: bool = False,
):
    """Run E-MA-7: ALHF routing fixes experiment."""

    # Load initial judge memory (E-MA-2 state)
    judge_mem = load_judge_mem(
        principles_path=principles_path,
        episodes_path=episodes_path,
    )
    n_judge_initial = len(judge_mem.all())

    # Create fresh agent memory
    agent_mem = MemStore()
    n_agent_initial = 0

    print(f"Initial judge memory: {n_judge_initial} items")
    print(f"Initial agent memory: {n_agent_initial} items")
    print(f"Routing tasks: {len(ROUTING_TASKS)}")

    # Step 1: Run aligned judge on all tasks (before routing)
    print("\n" + "=" * 60)
    print("Step 1: Judge Evaluation BEFORE Routing")
    print("=" * 60)

    before_fn = lambda task, answer, sparql: judge_aligned(
        task, answer, sparql, judge_mem, verbose=verbose
    )
    before_metrics = evaluate_judge(before_fn, ROUTING_TASKS, verbose=verbose)
    print_metrics(before_metrics, "Before ALHF Routing")

    # Step 2: Route feedback for all tasks
    print("\n" + "=" * 60)
    print("Step 2: Routing Expert Feedback via Updated FeedbackRouter")
    print("=" * 60)

    routing_results = []
    n_routed_judge = 0
    n_routed_agent = 0
    n_routed_both = 0
    n_correct_routing = 0

    for detail, task_data in zip(before_metrics['details'], ROUTING_TASKS):
        task_id = task_data['id']
        feedback = task_data['expert_feedback']
        expected_routing = task_data['expected_routing']

        print(f"\n  Task: {task_id}")
        print(f"    Verdict: {detail['verdict']} "
              f"(predicted={detail['predicted']}, expected={detail['expected']})")

        # Route ALL feedback (to test routing quality)
        result = route_and_store(
            feedback=feedback,
            task_context={
                'task': task_data['query'],
                'agent_sparql': task_data.get('agent_sparql', ''),
            },
            judge_mem=judge_mem,
            agent_mem=agent_mem,
            verbose=verbose,
        )

        # Check routing accuracy
        judge_routed = len(result['judge_items']) > 0
        agent_routed = len(result['agent_items']) > 0

        if judge_routed:
            n_routed_judge += 1
        if agent_routed:
            n_routed_agent += 1
        if judge_routed and agent_routed:
            n_routed_both += 1

        # Check if routing matches expectations
        judge_correct = judge_routed == expected_routing['judge']
        agent_correct = agent_routed == expected_routing['agent']
        both_correct = judge_correct and agent_correct
        if both_correct:
            n_correct_routing += 1

        routing_mark = 'OK' if both_correct else 'MISMATCH'
        print(f"    [{routing_mark}] Routing: judge={judge_routed} "
              f"(expect={expected_routing['judge']}), "
              f"agent={agent_routed} "
              f"(expect={expected_routing['agent']})")

        # Show scope detection for judge principles
        if result['judge_items']:
            for item in result['judge_items']:
                scope_info = f" [scope={item.scope}]" if item.scope else ""
                print(f"    -> [{item.src}]{scope_info} {item.title}")

        if result['routing'].get('judge_principle'):
            jp = result['routing']['judge_principle']
            print(f"    Judge principle: {jp[:80]}...")
        if result['routing'].get('agent_constraint'):
            ac = result['routing']['agent_constraint']
            print(f"    Agent constraint: {ac[:80]}...")
        if result['routing'].get('agent_seed'):
            aseed = result['routing']['agent_seed']
            print(f"    Agent seed: {aseed[:80]}...")

        routing_results.append({
            'task_id': task_id,
            'verdict': detail['verdict'],
            'judge_routed': judge_routed,
            'agent_routed': agent_routed,
            'expected_judge': expected_routing['judge'],
            'expected_agent': expected_routing['agent'],
            'routing_correct': both_correct,
            'routing': result['routing'],
            'n_judge_items': len(result['judge_items']),
            'n_agent_items': len(result['agent_items']),
        })

    # Memory growth report
    n_judge_final = len(judge_mem.all())
    n_agent_final = len(agent_mem.all())

    # Count exception-scoped items
    n_exceptions = sum(1 for item in judge_mem.all()
                       if getattr(item, 'scope', '') == 'exception')
    n_grounding = sum(1 for item in judge_mem.all()
                      if 'grounding' in item.tags)

    print(f"\n  Routing summary:")
    print(f"    Routed to judge: {n_routed_judge}/{len(ROUTING_TASKS)}")
    print(f"    Routed to agent: {n_routed_agent}/{len(ROUTING_TASKS)}")
    print(f"    Routed to both:  {n_routed_both}/{len(ROUTING_TASKS)}")
    print(f"    Correct routing: {n_correct_routing}/{len(ROUTING_TASKS)} "
          f"({n_correct_routing/len(ROUTING_TASKS):.0%})")
    print(f"    Judge memory: {n_judge_initial} -> {n_judge_final} "
          f"(+{n_judge_final - n_judge_initial})")
    print(f"    Agent memory: {n_agent_initial} -> {n_agent_final} "
          f"(+{n_agent_final - n_agent_initial})")
    print(f"    Exception-scoped principles: {n_exceptions}")
    print(f"    Grounding episodes: {n_grounding}")

    # Step 3: Re-evaluate with updated judge memory
    print("\n" + "=" * 60)
    print("Step 3: Judge Evaluation AFTER Routing")
    print("=" * 60)

    after_fn = lambda task, answer, sparql: judge_aligned(
        task, answer, sparql, judge_mem, verbose=verbose
    )
    after_metrics = evaluate_judge(after_fn, ROUTING_TASKS, verbose=verbose)
    print_metrics(after_metrics, "After ALHF Routing")

    # Step 4: Comparison and compound effect
    print("\n" + "=" * 60)
    print("COMPARISON: Before vs After ALHF Routing")
    print("=" * 60)
    print(f"  {'Metric':<12} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-'*40}")
    for metric in ['accuracy', 'precision', 'recall', 'f1']:
        before_val = before_metrics[metric]
        after_val = after_metrics[metric]
        delta = after_val - before_val
        sign = '+' if delta >= 0 else ''
        print(f"  {metric:<12} {before_val:>7.1%} {after_val:>7.1%} {sign}{delta:>6.1%}")

    # Show verdict flips
    flips = []
    n_fixes = 0
    n_regressions = 0
    for b, a in zip(before_metrics['details'], after_metrics['details']):
        if b['predicted'] != a['predicted']:
            direction = 'fixed' if a['predicted'] == a['expected'] else 'regressed'
            if direction == 'fixed':
                n_fixes += 1
            else:
                n_regressions += 1
            flips.append({
                'task_id': b['task_id'],
                'before': b['verdict'],
                'after': a['verdict'],
                'direction': direction,
            })

    if flips:
        print(f"\n  Verdict flips ({n_fixes} fixes, {n_regressions} regressions):")
        for f in flips:
            mark = 'OK' if f['direction'] == 'fixed' else 'WRONG'
            print(f"    [{mark}] {f['task_id']}: "
                  f"{f['before']} -> {f['after']} ({f['direction']})")
    else:
        print(f"\n  No verdict flips.")

    # Agent memory contents
    print("\n" + "=" * 60)
    print("AGENT MEMORY (routed items)")
    print("=" * 60)
    for item in agent_mem.all():
        print(f"  [{item.src}] {item.title}")
        print(f"    {item.content[:100]}...")

    # Step 5: E-MA-6 vs E-MA-7 comparison
    print("\n" + "=" * 60)
    print("E-MA-6 vs E-MA-7 COMPARISON")
    print("=" * 60)

    routing_accuracy = n_correct_routing / len(ROUTING_TASKS)
    print(f"  {'Metric':<35} {'E-MA-6':>8} {'E-MA-7':>8} {'Delta':>8}")
    print(f"  {'-'*60}")

    comparisons = [
        ('Before accuracy',
         E_MA_6_BASELINE['before_accuracy'], before_metrics['accuracy']),
        ('After accuracy',
         E_MA_6_BASELINE['after_accuracy'], after_metrics['accuracy']),
        ('Routing accuracy',
         E_MA_6_BASELINE['routing_accuracy'], routing_accuracy),
        ('Routed to judge',
         E_MA_6_BASELINE['routed_judge'], n_routed_judge),
        ('Routed to both',
         E_MA_6_BASELINE['routed_both'], n_routed_both),
        ('Regressions',
         E_MA_6_BASELINE['regressions'], n_regressions),
        ('Fixes',
         E_MA_6_BASELINE['fixes'], n_fixes),
    ]

    for label, ema6_val, ema7_val in comparisons:
        if isinstance(ema6_val, float):
            delta = ema7_val - ema6_val
            sign = '+' if delta >= 0 else ''
            print(f"  {label:<35} {ema6_val:>7.0%} {ema7_val:>7.0%} {sign}{delta:>6.0%}")
        else:
            delta = ema7_val - ema6_val
            sign = '+' if delta >= 0 else ''
            print(f"  {label:<35} {ema6_val:>8} {ema7_val:>8} {sign}{delta:>7}")

    # Success criteria
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    criteria = {
        'Routing accuracy >= 70%': routing_accuracy >= 0.70,
        'No regressions (before->after)': n_regressions == 0,
        'Judge accuracy improved or maintained': (
            after_metrics['accuracy'] >= before_metrics['accuracy']
        ),
        'Feedback reaches both >= 5/10': n_routed_both >= 5,
        'Memory bounded (judge < 30, agent < 20)': (
            n_judge_final < 30 and n_agent_final < 20
        ),
        'Grounding episodes generated': n_grounding > 0,
        'Exception scoping applied': n_exceptions > 0,
    }
    for name, passed in criteria.items():
        mark = 'PASS' if passed else 'FAIL'
        print(f"  [{mark}] {name}")

    n_passed = sum(1 for v in criteria.values() if v)
    print(f"\n  {n_passed}/{len(criteria)} criteria passed")

    # Save results
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    report = {
        'experiment': 'E-MA-7',
        'timestamp': timestamp,
        'fixes_applied': [
            'Fix 1: Paired principle+episode in route_and_store',
            'Fix 2: Scope metadata + [EXCEPTION] annotation + specificity rule',
            'Fix 3: Dual-routing bias in FeedbackRouter',
        ],
        'before_metrics': before_metrics,
        'after_metrics': after_metrics,
        'routing_summary': {
            'total_tasks': len(ROUTING_TASKS),
            'routed_judge': n_routed_judge,
            'routed_agent': n_routed_agent,
            'routed_both': n_routed_both,
            'routing_accuracy': routing_accuracy,
        },
        'memory_growth': {
            'judge_before': n_judge_initial,
            'judge_after': n_judge_final,
            'agent_before': n_agent_initial,
            'agent_after': n_agent_final,
            'exception_scoped': n_exceptions,
            'grounding_episodes': n_grounding,
        },
        'verdict_flips': flips,
        'n_fixes': n_fixes,
        'n_regressions': n_regressions,
        'per_task_routing': routing_results,
        'criteria': {k: v for k, v in criteria.items()},
        'ema6_comparison': {
            label: {'ema6': ema6_val, 'ema7': ema7_val}
            for label, ema6_val, ema7_val in comparisons
        },
    }

    with open(os.path.join(output_dir, 'alhf_routing_fixes_report.json'), 'w') as f:
        json.dump(report, f, indent=2, default=str)

    # Save final memories
    judge_mem.save(os.path.join(output_dir, 'judge_memory_after_alhf_v7.json'))
    agent_mem.save(os.path.join(output_dir, 'agent_memory_after_alhf_v7.json'))

    print(f"\nResults saved to {output_dir}/")
    return report


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='E-MA-7: ALHF Routing Fixes (Paired Episodes, Specificity, Dual-Routing)')
    parser.add_argument('--principles',
                        default='experiments/reasoningbank/seed/judge_principles.json')
    parser.add_argument('--episodes',
                        default='experiments/reasoningbank/seed/judge_episodes.json')
    parser.add_argument('--output-dir',
                        default='experiments/reasoningbank/results/e_ma_7')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4-5-20250929')

    args = parser.parse_args()

    lm = dspy.LM(args.model, temperature=0.0)
    dspy.configure(lm=lm)

    run_e_ma_7(
        principles_path=args.principles,
        episodes_path=args.episodes,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )
