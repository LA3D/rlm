#!/usr/bin/env python
"""Quick test of S3 experiment setup with 1 task, k=2."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.run_experiment_s3 import run_experiment_s3

if __name__ == '__main__':
    print("Running quick test of S3 experiment...")
    print("Configuration: 1 task, k=2, 2 strategies (none, prefix)")
    print()

    # Override to run only baseline comparison
    run_experiment_s3(
        output_dir='experiments/reasoningbank/results/s3_test',
        k=2,  # Only 2 rollouts per strategy
        temperature=0.7,
        use_seed=False,
    )
