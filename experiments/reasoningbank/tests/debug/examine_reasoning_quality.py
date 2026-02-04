#!/usr/bin/env python
"""
Examine reasoning quality in S3 trajectories.

Extract and analyze the reasoning text from iteration events to assess:
- Agent competence
- Reasoning coherence
- Tool usage strategy
- Problem-solving approach
"""

import json
import sys

def examine_trajectory(log_path: str):
    """Print detailed reasoning from a trajectory."""

    with open(log_path, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]

    # Get run info
    run_start = next((e for e in events if e['event_type'] == 'run_start'), None)
    run_complete = next((e for e in events if e['event_type'] == 'run_complete'), None)
    run_error = next((e for e in events if e['event_type'] == 'run_error'), None)

    print("=" * 80)
    print(f"TRAJECTORY: {log_path.split('/')[-1]}")
    print("=" * 80)

    if run_start:
        print(f"\nTask: {run_start['data']['task']}")
        print(f"Context size: {run_start['data']['context_size']} chars")

    if run_error:
        print(f"\n⚠ RUN ERROR:")
        print(f"  Type: {run_error['data']['type']}")
        print(f"  Error: {run_error['data']['error']}")
        return

    # Get iteration events
    iterations = [e for e in events if e['event_type'] == 'iteration']

    print(f"\nIterations: {len(iterations)}")

    for iter_event in iterations:
        data = iter_event['data']
        iter_num = data.get('iteration', '?')
        total = data.get('total', '?')
        reasoning = data.get('reasoning', '')
        code = data.get('code', '')

        print(f"\n{'─' * 80}")
        print(f"Iteration {iter_num}/{total}")
        print(f"{'─' * 80}")

        print(f"\nReasoning:")
        # Truncate long reasoning
        if len(reasoning) > 500:
            print(reasoning[:500] + "...")
        else:
            print(reasoning)

        print(f"\nCode:")
        # Truncate long code
        if len(code) > 400:
            print(code[:400] + "...")
        else:
            print(code)

    if run_complete:
        data = run_complete['data']
        print(f"\n{'=' * 80}")
        print("RUN COMPLETE")
        print(f"{'=' * 80}")
        print(f"Converged: {data.get('converged')}")
        print(f"Iterations: {data.get('iterations')}")
        print(f"Answer: {data.get('answer_preview', '')}")
        if data.get('sparql'):
            print(f"\nSPARQL Query:")
            print(data['sparql'])

if __name__ == '__main__':
    # Examine a few representative trajectories

    trajectories = [
        # Successful simple task
        ('experiments/reasoningbank/results/s3_prompt_perturbation/logs/'
         '4_uniprot_mnemonic_id/none/4_uniprot_mnemonic_id_rollout1.jsonl',
         'Simple task - baseline'),

        # Successful with prefix perturbation
        ('experiments/reasoningbank/results/s3_prompt_perturbation/logs/'
         '4_uniprot_mnemonic_id/prefix/4_uniprot_mnemonic_id_rollout1.jsonl',
         'Simple task - prefix perturbation'),

        # Successful moderate task
        ('experiments/reasoningbank/results/s3_prompt_perturbation/logs/'
         '121_proteins_and_diseases_linked/none/121_proteins_and_diseases_linked_rollout1.jsonl',
         'Moderate task - baseline'),

        # Failed task
        ('experiments/reasoningbank/results/s3_prompt_perturbation/logs/'
         '30_merged_loci/none/30_merged_loci_rollout1.jsonl',
         'Failed task - code error'),
    ]

    for path, description in trajectories:
        print(f"\n\n{'#' * 80}")
        print(f"# {description}")
        print(f"{'#' * 80}")
        examine_trajectory(path)
        print("\n" + "=" * 80)
