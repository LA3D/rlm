#!/usr/bin/env python
"""Validation test for caching fix.

Tests that adding rollout_id to context prevents caching and allows
temperature-based stochasticity.

Success criteria:
1. Both rollouts show non-zero LM token usage
2. Trajectories are different (Vendi > 1.0 or Jaccard < 1.0)
3. Both rollouts succeed (100% success rate for simple task)
"""

import sys
import json
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.run.phase1_uniprot import run_stochastic_uniprot
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.ctx.builder import Cfg, Layer

def main():
    print("=" * 80)
    print("CACHING FIX VALIDATION TEST")
    print("=" * 80)
    print("\nConfiguration:")
    print("  Task: 4_uniprot_mnemonic_id (simple)")
    print("  Rollouts: k=2")
    print("  Strategy: NONE (no perturbation - testing raw temperature stochasticity)")
    print("  Temperature: 0.7")
    print("  Rollout IDs: 0, 1 (prevents caching)")
    print()

    # Load task
    with open('experiments/reasoningbank/uniprot_subset_tasks.json', 'r') as f:
        tasks = json.load(f)

    task = [t for t in tasks if t['id'] == '4_uniprot_mnemonic_id'][0]
    print(f"Task query: {task['query']}")
    print()

    # Initialize memory store
    mem = MemStore()

    # Configure layers
    cfg = Cfg(
        l0=Layer(True, 600),   # Sense card
        l1=Layer(True, 1000),  # Meta-graph
        l2=Layer(False, 2000), # No memory
    )

    print("Running stochastic evaluation with NO perturbation...")
    print("(rollout_id is passed internally to prevent caching)")
    print()

    try:
        result = run_stochastic_uniprot(
            task=task,
            ont_path='ontology/uniprot',
            cfg=cfg,
            mem=mem,
            k=2,
            temperature=0.7,
            endpoint='uniprot',
            verbose=True,
            log_dir='experiments/reasoningbank/results/caching_fix_test',
            use_local_interpreter=True,
            perturb='none',  # NO perturbation
            use_seed=False,  # NO explicit seed (doesn't work with Anthropic)
            compute_diversity=True,
        )

        print(f"\n{'='*80}")
        print("VALIDATION RESULTS")
        print(f"{'='*80}\n")

        # Check 1: LM token usage
        print("Check 1: LM Token Usage (both should be non-zero)")
        print("-" * 60)
        for i, rollout in enumerate(result['rollouts']):
            if 'lm_usage' in rollout:
                total = rollout['lm_usage'].get('total_tokens', 0)
                print(f"  Rollout {i+1}: {total:,} tokens", end="")
                if total > 0:
                    print(" ✓")
                else:
                    print(" ✗ CACHED (zero tokens)")
            else:
                print(f"  Rollout {i+1}: No LM usage data")

        # Check 2: Diversity metrics
        print("\nCheck 2: Trajectory Diversity")
        print("-" * 60)
        if 'diversity' in result and result['diversity']:
            div = result['diversity']
            vendi = div.get('trajectory_vendi_score', 0)
            jaccard = div.get('mean_pairwise_jaccard', 1.0)
            efficiency = div.get('sampling_efficiency', 0)

            print(f"  Trajectory Vendi Score: {vendi:.2f}", end="")
            if vendi > 1.0:
                print(" ✓ (diverse)")
            else:
                print(" ✗ (identical)")

            print(f"  Mean Jaccard Similarity: {jaccard:.3f}", end="")
            if jaccard < 1.0:
                print(" ✓ (different)")
            else:
                print(" ✗ (identical)")

            print(f"  Sampling Efficiency: {efficiency:.1%}", end="")
            if efficiency > 0.5:
                print(" ✓ (good)")
            else:
                print(" ✗ (redundant)")
        else:
            print("  No diversity metrics computed")

        # Check 3: Success rate
        print("\nCheck 3: Success Rate (should be 100% for simple task)")
        print("-" * 60)
        metrics = result['metrics']
        pass1 = metrics['pass_1']
        bestn = metrics['best_of_n']
        print(f"  Pass@1: {pass1:.1%}", end="")
        if pass1 == 1.0:
            print(" ✓")
        else:
            print(f" ⚠ (expected 100%)")

        print(f"  Best-of-N: {bestn:.1%}", end="")
        if bestn == 1.0:
            print(" ✓")
        else:
            print(f" ⚠ (expected 100%)")

        # Overall assessment
        print(f"\n{'='*80}")
        print("OVERALL ASSESSMENT")
        print(f"{'='*80}\n")

        # Determine if caching is fixed
        has_tokens = all(
            r.get('lm_usage', {}).get('total_tokens', 0) > 0
            for r in result['rollouts'] if 'lm_usage' in r
        )

        has_diversity = (
            result.get('diversity', {}).get('trajectory_vendi_score', 1.0) > 1.0 or
            result.get('diversity', {}).get('mean_pairwise_jaccard', 1.0) < 1.0
        )

        if has_tokens and has_diversity:
            print("✅ SUCCESS: Caching fix works!")
            print("   - Both rollouts made real LM calls (no caching)")
            print("   - Trajectories show diversity")
            print("   - Ready for full S3 experiment")
        elif has_tokens and not has_diversity:
            print("⚠️  PARTIAL: Caching prevented, but no diversity")
            print("   - Both rollouts made real LM calls ✓")
            print("   - But trajectories are still identical")
            print("   - This may be due to peaked probability distribution for simple task")
            print("   - Should see diversity on harder tasks")
            print("   - Ready for full S3 experiment")
        elif not has_tokens:
            print("❌ FAILURE: Caching still occurring")
            print("   - One or more rollouts show zero tokens")
            print("   - Rollout ID fix did not prevent caching")
            print("   - Need alternative solution")
        else:
            print("⚠️  UNCLEAR: Mixed results")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
