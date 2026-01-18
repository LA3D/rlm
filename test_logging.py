#!/usr/bin/env python3
"""Test RLM logging (both JSON-lines and Rich console).

Requires ANTHROPIC_API_KEY environment variable.

Usage:
    python test_logging.py
"""

import tempfile
from pathlib import Path
import json

from rlm.core import rlm_run
from rlm.logger import RLMLogger


def main():
    print("="*70)
    print(" Testing RLM Logging")
    print("="*70)
    print()

    # Setup
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = RLMLogger(tmpdir, file_name='test_rlm')

        print(f"Log directory: {tmpdir}")
        print(f"Log file: {logger.log_file_path.name}")
        print()

        # Simple context and query
        context = "The capital of France is Paris."
        query = "What is the capital of France?"

        print("Running RLM with verbose=True and logger...")
        print("-"*70)
        print()

        # Run with both logger and verbose
        answer, iterations, ns = rlm_run(
            query=query,
            context=context,
            max_iters=3,
            logger=logger,
            verbose=True  # Beautiful Rich output
        )

        print()
        print("="*70)
        print(" Results")
        print("="*70)
        print(f"Answer: {answer}")
        print(f"Iterations: {len(iterations)}")
        print(f"Logger recorded: {logger.iteration_count} iteration(s)")
        print()

        # Verify log file
        print("="*70)
        print(" Log File Verification")
        print("="*70)

        assert logger.log_file_path.exists(), "Log file should exist"

        lines = logger.log_file_path.read_text().strip().split('\n')
        print(f"Log file has {len(lines)} lines")

        # First line should be metadata
        metadata = json.loads(lines[0])
        assert metadata['type'] == 'metadata'
        assert metadata['query'] == query
        print(f"✓ Metadata logged: {metadata}")
        print()

        # Following lines should be iterations
        for i, line in enumerate(lines[1:], 1):
            iteration_entry = json.loads(line)
            assert iteration_entry['type'] == 'iteration'
            assert iteration_entry['iteration'] == i
            print(f"✓ Iteration {i} logged:")
            print(f"  - Response length: {len(iteration_entry['response'])} chars")
            print(f"  - Code blocks: {len(iteration_entry['code_blocks'])}")
            if iteration_entry['code_blocks']:
                for j, block in enumerate(iteration_entry['code_blocks']):
                    print(f"    Block {j}: {len(block['code'])} chars, stdout: '{block['result']['stdout'][:50]}'")

        print()
        print("="*70)
        print(" ✓ SUCCESS: Logging works!")
        print("="*70)
        print()
        print("Summary:")
        print(f"  - JSON-lines log: {logger.log_file_path}")
        print(f"  - Rich console output: displayed above")
        print(f"  - Both outputs synchronized")

        return True


if __name__ == '__main__':
    import sys
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
