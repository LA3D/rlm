#!/usr/bin/env python3
"""
Surgical test of v2 tool fixes against actual failure patterns from S3 experiment.

This script:
1. Extracts actual tool call patterns that caused failures from trajectories
2. Simulates those calling patterns against v1 and v2 tools
3. Reports which failures are fixed by v2

Run before re-running the full S3 experiment to validate fixes.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple

# Add project root to path
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.tools.sparql import SPARQLTools, create_tools as create_tools_v1
from experiments.reasoningbank.prototype.tools.sparql_v2 import SPARQLToolsV2, create_tools as create_tools_v2

# Base directory for logs
LOGS_BASE = Path(__file__).parent / "results/logs"


class ToolCallExtractor:
    """Extract actual tool calls that caused failures from trajectories."""

    def __init__(self):
        self.failures = []

    def extract_from_trajectory(self, filepath: Path) -> List[Dict]:
        """Extract failed tool calls from a trajectory file."""
        events = []
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

        failures = []
        for i, event in enumerate(events):
            if event.get('event_type') == 'tool_result':
                data = event.get('data', {})
                if data.get('error'):
                    # Get the tool_call event that preceded this
                    tool_call = None
                    if i > 0 and events[i-1].get('event_type') == 'tool_call':
                        tool_call = events[i-1].get('data', {})

                    failures.append({
                        'tool': data.get('tool', 'unknown'),
                        'error': data.get('error', ''),
                        'error_type': self._categorize_error(data.get('error', '')),
                        'tool_call': tool_call,
                        'trajectory': str(filepath),
                    })

        return failures

    def _categorize_error(self, error: str) -> str:
        """Categorize error type."""
        error_lower = error.lower()
        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif 'argument' in error_lower or 'takes' in error_lower:
            return 'argument_mismatch'
        elif 'unhashable' in error_lower or 'type' in error_lower:
            return 'type_error'
        elif 'attribute' in error_lower:
            return 'attribute_error'
        else:
            return 'other'

    def extract_all(self) -> List[Dict]:
        """Extract failures from all trajectories."""
        all_failures = []
        for filepath in LOGS_BASE.rglob("*.jsonl"):
            failures = self.extract_from_trajectory(filepath)
            all_failures.extend(failures)
        return all_failures


class ToolFixTester:
    """Test tool fixes by simulating failure patterns."""

    def __init__(self):
        # Create tools (will hit actual endpoint)
        self.v1_tools = create_tools_v1('uniprot')
        self.v2_tools = create_tools_v2('uniprot')

        # Get DSPy wrappers (what agents actually call)
        self.v1_dspy = self.v1_tools.as_dspy_tools()
        self.v2_dspy = self.v2_tools.as_dspy_tools()

        self.results = []

    def test_calling_pattern(self, tool: str, args: List, kwargs: Dict, description: str) -> Dict:
        """Test a specific calling pattern against both v1 and v2.

        IMPORTANT: We test DIRECT calling (how LocalPythonInterpreter calls tools),
        not the DSPy (args, kwargs) pattern. The agent writes:
            sparql_peek('resource', limit=5)
        which gets called as:
            fn('resource', limit=5)
        NOT:
            fn(['resource'], {'limit': 5})
        """
        result = {
            'description': description,
            'tool': tool,
            'args': str(args),
            'kwargs': str(kwargs),
            'v1_success': False,
            'v1_error': None,
            'v2_success': False,
            'v2_error': None,
        }

        # Test v1 - DIRECT calling pattern (how LocalPythonInterpreter calls)
        try:
            if tool in self.v1_dspy:
                self.v1_dspy[tool](*args, **kwargs)  # Direct call!
                result['v1_success'] = True
        except Exception as e:
            result['v1_error'] = str(e)[:100]

        # Test v2 - DIRECT calling pattern
        try:
            if tool in self.v2_dspy:
                self.v2_dspy[tool](*args, **kwargs)  # Direct call!
                result['v2_success'] = True
        except Exception as e:
            result['v2_error'] = str(e)[:100]

        self.results.append(result)
        return result

    def run_tests(self) -> List[Dict]:
        """Run all failure pattern tests."""

        print("=" * 60)
        print("Testing Tool Fixes Against S3 Failure Patterns")
        print("=" * 60)
        print()

        # First, run a query to get a result handle
        print("Setting up test data...")
        v1_result = self.v1_tools.sparql_query(
            "SELECT ?t WHERE { ?t a <http://purl.uniprot.org/core/Taxon> } LIMIT 5"
        )
        v2_result = self.v2_tools.sparql_query(
            "SELECT ?t WHERE { ?t a <http://purl.uniprot.org/core/Taxon> } LIMIT 5"
        )
        print(f"  v1 result: {v1_result.get('key')}")
        print(f"  v2 result: {v2_result.get('key')}")
        print()

        # === Test patterns from S3 failures ===

        print("Testing failure patterns...")
        print("-" * 60)

        # Pattern 1: sparql_peek with limit= kwarg (18 failures in S3)
        print("\n1. sparql_peek with limit= kwarg (18 S3 failures)")
        self.test_calling_pattern(
            'sparql_peek',
            ['up:Taxon'],
            {'limit': 5},
            "Agent calls sparql_peek with limit= keyword argument"
        )

        # Pattern 2: sparql_slice with dict handle (4 failures in S3)
        print("\n2. sparql_slice with dict handle (type errors)")
        self.test_calling_pattern(
            'sparql_slice',
            [v2_result],  # Pass the full dict, not just key
            {'limit': 3},
            "Agent passes full result dict to sparql_slice"
        )

        # Pattern 3: sparql_slice with limit kwarg (part of arg mismatch)
        print("\n3. sparql_slice with limit= kwarg")
        self.test_calling_pattern(
            'sparql_slice',
            [v2_result['key']],
            {'limit': 5},
            "Agent calls sparql_slice with limit= keyword"
        )

        # Pattern 4: sparql_slice with only 2 positional args (5 failures)
        print("\n4. sparql_slice with offset and limit")
        self.test_calling_pattern(
            'sparql_slice',
            [v2_result['key'], 0],  # No third arg
            {'limit': 5},
            "Agent calls sparql_slice(key, offset) with limit as kwarg"
        )

        # Pattern 5: sparql_peek with output_mode (new feature)
        print("\n5. sparql_peek with output_mode")
        self.test_calling_pattern(
            'sparql_peek',
            ['up:Taxon'],
            {'output_mode': 'count'},
            "Agent uses output_mode for progressive disclosure"
        )

        # Pattern 6: sparql_describe with limit (2 failures)
        print("\n6. sparql_describe with limit= kwarg")
        self.test_calling_pattern(
            'sparql_describe',
            ['http://purl.uniprot.org/taxonomy/9606'],
            {'limit': 10},
            "Agent calls sparql_describe with limit="
        )

        # Pattern 7: sparql_schema (new tool)
        print("\n7. sparql_schema (new discovery tool)")
        self.test_calling_pattern(
            'sparql_schema',
            ['overview'],
            {},
            "Agent uses new schema discovery tool"
        )

        # Pattern 8: sparql_slice with 3 positional args (5 failures in S3)
        print("\n8. sparql_slice with 3 positional args")
        self.test_calling_pattern(
            'sparql_slice',
            [v2_result['key'], 0, 10],
            {},
            "Agent calls sparql_slice(key, start, end)"
        )

        # Pattern 9: sparql_peek with just resource (common pattern)
        print("\n9. sparql_peek with just resource")
        self.test_calling_pattern(
            'sparql_peek',
            ['up:Protein'],
            {},
            "Agent calls sparql_peek(resource) with no limit"
        )

        # Pattern 10: sparql_count (5 failures in S3)
        print("\n10. sparql_count direct call")
        self.test_calling_pattern(
            'sparql_count',
            ["SELECT ?s WHERE { ?s a up:Taxon }"],
            {},
            "Agent calls sparql_count with query string"
        )

        # Pattern 11: endpoint_info (should work)
        print("\n11. endpoint_info()")
        self.test_calling_pattern(
            'endpoint_info',
            [],
            {},
            "Agent calls endpoint_info() for metadata"
        )

        # Pattern 12: sparql_query with limit kwarg
        print("\n12. sparql_query with limit kwarg")
        self.test_calling_pattern(
            'sparql_query',
            ["SELECT ?s WHERE { ?s a up:Taxon }"],
            {'limit': 10},
            "Agent calls sparql_query(q, limit=N)"
        )

        return self.results

    def print_summary(self):
        """Print test summary."""
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        v1_pass = sum(1 for r in self.results if r['v1_success'])
        v2_pass = sum(1 for r in self.results if r['v2_success'])
        total = len(self.results)

        print(f"\nV1 Tools: {v1_pass}/{total} patterns work")
        print(f"V2 Tools: {v2_pass}/{total} patterns work")
        print(f"Improvement: +{v2_pass - v1_pass} patterns fixed")
        print()

        # Detailed results
        print("-" * 60)
        print("DETAILED RESULTS:")
        print("-" * 60)

        for i, r in enumerate(self.results, 1):
            v1_status = "✓" if r['v1_success'] else "✗"
            v2_status = "✓" if r['v2_success'] else "✗"
            fixed = "FIXED" if not r['v1_success'] and r['v2_success'] else ""

            print(f"\n{i}. {r['description']}")
            print(f"   Tool: {r['tool']}")
            print(f"   V1: {v1_status}  V2: {v2_status}  {fixed}")
            if r['v1_error']:
                print(f"   V1 Error: {r['v1_error'][:60]}...")
            if r['v2_error']:
                print(f"   V2 Error: {r['v2_error'][:60]}...")

        print()
        print("=" * 60)

        # Recommendation
        if v2_pass > v1_pass:
            improvement_pct = ((v2_pass - v1_pass) / (total - v1_pass)) * 100 if total > v1_pass else 0
            print(f"\n✅ V2 fixes {v2_pass - v1_pass} failure patterns ({improvement_pct:.0f}% of v1 failures)")
            print("   Recommend: Re-run S3 with use_v2_tools=True")
        else:
            print("\n⚠️  V2 doesn't show improvement on tested patterns")
            print("   Review: Check if failure patterns match v2 design")


def extract_failure_stats():
    """Extract and summarize failure statistics from trajectories."""
    print("Extracting failure patterns from S3 trajectories...")
    print("-" * 60)

    extractor = ToolCallExtractor()
    failures = extractor.extract_all()

    # Group by error type and tool
    by_tool = defaultdict(list)
    by_type = defaultdict(list)

    for f in failures:
        by_tool[f['tool']].append(f)
        by_type[f['error_type']].append(f)

    print(f"\nTotal failures extracted: {len(failures)}")
    print("\nBy Tool:")
    for tool, fails in sorted(by_tool.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {tool}: {len(fails)}")

    print("\nBy Error Type:")
    for err_type, fails in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {err_type}: {len(fails)}")

    return failures


def main():
    # First, show what we're testing against
    failures = extract_failure_stats()

    print()
    print("=" * 60)
    print("RUNNING V1 vs V2 COMPARISON TESTS")
    print("=" * 60)
    print()

    # Run the tests
    tester = ToolFixTester()
    results = tester.run_tests()
    tester.print_summary()

    # Save results
    output_path = Path(__file__).parent / "TOOL_FIX_TEST_RESULTS.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
