#!/usr/bin/env python3
"""
Comprehensive tool failure analysis across S3 experiment trajectories.
Extracts all tool errors, categorizes them, and analyzes agent expectations vs reality.
"""

import json
import os
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple

# Base directory for logs
LOGS_BASE = Path("/Users/cvardema/dev/git/LA3D/rlm/experiments/reasoningbank/experiments_archive/2026-02-03_s3_prompt_perturbation/results/logs")

class ToolFailureAnalyzer:
    def __init__(self):
        self.failures = []  # List of all failures
        self.tool_failures = defaultdict(list)  # Failures by tool
        self.error_types = defaultdict(list)  # Failures by error type
        self.task_failures = defaultdict(list)  # Failures by task
        self.strategy_failures = defaultdict(list)  # Failures by strategy
        self.recovery_patterns = []  # Recovery attempts after failures

    def load_trajectory(self, filepath: Path) -> List[Dict]:
        """Load a JSONL trajectory file."""
        events = []
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def extract_context_from_iteration(self, iteration_data: Dict) -> Tuple[str, str]:
        """Extract reasoning and code from iteration event."""
        reasoning = iteration_data.get('reasoning', '')
        code = iteration_data.get('code', '')
        return reasoning, code

    def extract_tool_call_from_code(self, code: str, tool_name: str) -> str:
        """Extract the specific tool call line(s) from code."""
        lines = code.split('\n')
        relevant_lines = []

        for i, line in enumerate(lines):
            if tool_name in line and '(' in line:
                # Get surrounding context (line before and after if available)
                if i > 0:
                    relevant_lines.append(lines[i-1])
                relevant_lines.append(line)
                if i < len(lines) - 1:
                    relevant_lines.append(lines[i+1])
                break

        return '\n'.join(relevant_lines) if relevant_lines else None

    def categorize_error(self, error_msg: str) -> str:
        """Categorize error type based on message."""
        error_lower = error_msg.lower()

        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif 'missing' in error_lower or 'not found' in error_lower or 'no attribute' in error_lower:
            return 'missing_tool_or_attribute'
        elif 'argument' in error_lower or 'parameter' in error_lower or 'takes' in error_lower:
            return 'argument_mismatch'
        elif 'empty' in error_lower or 'no results' in error_lower or 'zero' in error_lower:
            return 'empty_result'
        elif 'type' in error_lower or 'expected' in error_lower:
            return 'type_error'
        elif 'syntax' in error_lower or 'parse' in error_lower:
            return 'syntax_error'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network_error'
        else:
            return 'other'

    def analyze_trajectory(self, filepath: Path):
        """Analyze a single trajectory for tool failures."""
        events = self.load_trajectory(filepath)

        # Extract metadata from path
        parts = filepath.parts
        task_name = parts[-3]
        strategy = parts[-2]
        rollout = filepath.stem.split('_rollout')[-1]

        # Track iteration context for understanding agent intent
        current_iteration = None
        current_reasoning = ""
        current_code = ""
        iteration_history = []  # Track all iterations for context

        for i, event in enumerate(events):
            event_type = event.get('event_type', '')

            # Track iteration context
            if event_type == 'iteration':
                current_iteration = event['data'].get('iteration', 0)
                current_reasoning, current_code = self.extract_context_from_iteration(event['data'])
                iteration_history.append({
                    'iteration': current_iteration,
                    'reasoning': current_reasoning,
                    'code': current_code
                })

            # Look for tool failures
            if event_type == 'tool_result':
                data = event.get('data', {})
                error = data.get('error')

                if error:
                    tool_name = data.get('tool', 'unknown')

                    # Try to find the corresponding tool_call
                    tool_args = None
                    tool_call_code = None
                    if i > 0 and events[i-1].get('event_type') == 'tool_call':
                        tool_call_data = events[i-1].get('data', {})
                        tool_args = {
                            'args_type': tool_call_data.get('args_type'),
                            'kwargs_keys': tool_call_data.get('kwargs_keys', [])
                        }
                        # Extract the actual tool call from code
                        if current_code:
                            tool_call_code = self.extract_tool_call_from_code(current_code, tool_name)

                    # Extract full exception info if available
                    exception_type = data.get('exception_type', 'Unknown')
                    result_preview = data.get('result_preview', '')

                    error_category = self.categorize_error(error)

                    failure_record = {
                        'task': task_name,
                        'strategy': strategy,
                        'rollout': rollout,
                        'iteration': current_iteration,
                        'tool': tool_name,
                        'error_message': error,
                        'error_category': error_category,
                        'exception_type': exception_type,
                        'result_preview': result_preview,
                        'tool_args': tool_args,
                        'tool_call_code': tool_call_code,
                        'agent_reasoning': current_reasoning,
                        'agent_code': current_code,
                        'timestamp': event.get('timestamp', ''),
                        'iteration_history': iteration_history[-3:] if len(iteration_history) > 0 else []  # Last 3 iterations
                    }

                    self.failures.append(failure_record)
                    self.tool_failures[tool_name].append(failure_record)
                    self.error_types[error_category].append(failure_record)
                    self.task_failures[task_name].append(failure_record)
                    self.strategy_failures[strategy].append(failure_record)

                    # Check for recovery in next iteration
                    if i < len(events) - 1:
                        next_events = events[i+1:min(i+10, len(events))]
                        recovery_info = self.analyze_recovery(next_events, tool_name, current_iteration)
                        if recovery_info:
                            failure_record['recovery'] = recovery_info
                            self.recovery_patterns.append({
                                'failure': failure_record,
                                'recovery': recovery_info
                            })

    def analyze_recovery(self, next_events: List[Dict], failed_tool: str, failed_iteration: int) -> Dict:
        """Analyze how agent recovered from failure."""
        recovery = {
            'success': False,
            'iterations_to_recovery': 0,
            'alternative_tool_used': None,
            'retry_same_tool': False,
            'changed_approach': False
        }

        for event in next_events:
            if event.get('event_type') == 'tool_call':
                tool = event['data'].get('tool')
                if tool == failed_tool:
                    recovery['retry_same_tool'] = True
                else:
                    recovery['alternative_tool_used'] = tool
                    recovery['changed_approach'] = True
                break

            if event.get('event_type') == 'iteration':
                iter_num = event['data'].get('iteration', 0)
                if iter_num > failed_iteration:
                    recovery['iterations_to_recovery'] = iter_num - failed_iteration

            if event.get('event_type') == 'run_complete':
                recovery['success'] = event['data'].get('converged', False)
                break

        return recovery

    def generate_report(self) -> str:
        """Generate comprehensive markdown report."""
        report = []

        # Header
        report.append("# S3 Experiment Tool Failure Analysis\n")
        report.append(f"**Analysis Date**: {Path(__file__).stat().st_mtime}\n")
        report.append(f"**Total Trajectories Analyzed**: {len(list(LOGS_BASE.rglob('*.jsonl')))}\n")
        report.append(f"**Total Tool Failures**: {len(self.failures)}\n")
        report.append(f"**Unique Tools with Failures**: {len(self.tool_failures)}\n\n")

        # Executive Summary
        report.append("## Executive Summary\n\n")
        report.append("### Key Findings\n\n")

        # Most problematic tools
        tool_failure_counts = {tool: len(failures) for tool, failures in self.tool_failures.items()}
        top_tools = sorted(tool_failure_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        report.append("**Most Problematic Tools**:\n")
        for tool, count in top_tools:
            pct = (count / len(self.failures) * 100) if self.failures else 0
            report.append(f"- `{tool}`: {count} failures ({pct:.1f}% of all failures)\n")

        # Error type distribution
        report.append("\n**Error Type Distribution**:\n")
        error_counts = {err: len(failures) for err, failures in self.error_types.items()}
        for err_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(self.failures) * 100) if self.failures else 0
            report.append(f"- {err_type.replace('_', ' ').title()}: {count} ({pct:.1f}%)\n")

        # Recovery success rate
        recovery_successes = sum(1 for rp in self.recovery_patterns if rp['recovery'].get('success'))
        recovery_rate = (recovery_successes / len(self.recovery_patterns) * 100) if self.recovery_patterns else 0
        report.append(f"\n**Recovery Success Rate**: {recovery_rate:.1f}% ({recovery_successes}/{len(self.recovery_patterns)} failures recovered)\n\n")

        # Detailed Analysis by Tool
        report.append("## Detailed Tool Failure Analysis\n\n")

        for tool in sorted(self.tool_failures.keys(), key=lambda t: len(self.tool_failures[t]), reverse=True):
            failures = self.tool_failures[tool]
            report.append(f"### Tool: `{tool}` ({len(failures)} failures)\n\n")

            # Error breakdown for this tool
            tool_errors = Counter(f['error_category'] for f in failures)
            report.append("**Error Categories**:\n")
            for err_cat, count in tool_errors.most_common():
                report.append(f"- {err_cat.replace('_', ' ').title()}: {count}\n")

            # Unique error messages
            unique_errors = {}
            for f in failures:
                err_msg = f['error_message']
                if err_msg not in unique_errors:
                    unique_errors[err_msg] = {
                        'count': 0,
                        'examples': []
                    }
                unique_errors[err_msg]['count'] += 1
                if len(unique_errors[err_msg]['examples']) < 2:
                    unique_errors[err_msg]['examples'].append(f)

            report.append("\n**Unique Error Messages**:\n")
            for err_msg, info in sorted(unique_errors.items(), key=lambda x: x[1]['count'], reverse=True):
                report.append(f"\n#### Error: `{err_msg}` ({info['count']} occurrences)\n\n")

                # Show example with context
                if info['examples']:
                    example = info['examples'][0]
                    report.append(f"**Example Context** (Task: {example['task']}, Strategy: {example['strategy']}, Iteration: {example['iteration']}):\n\n")

                    # Agent's intent
                    if example['agent_reasoning']:
                        reasoning_snippet = example['agent_reasoning'][:400]
                        if len(example['agent_reasoning']) > 400:
                            reasoning_snippet += "..."
                        report.append(f"**Agent's Reasoning**:\n```\n{reasoning_snippet}\n```\n\n")

                    # Agent's code attempt - use extracted tool call if available
                    if example.get('tool_call_code'):
                        report.append(f"**Agent's Tool Call**:\n```python\n{example['tool_call_code']}\n```\n\n")
                    elif example['agent_code']:
                        # Find the line with this tool call
                        code_lines = example['agent_code'].split('\n')
                        relevant_lines = [line for line in code_lines if tool in line]
                        if relevant_lines:
                            report.append(f"**Agent's Code Attempt**:\n```python\n")
                            for line in relevant_lines[:5]:  # Show up to 5 lines
                                report.append(f"{line}\n")
                            report.append(f"```\n\n")

                    # Tool arguments attempted
                    if example.get('tool_args'):
                        args_info = example['tool_args']
                        if args_info.get('kwargs_keys'):
                            report.append(f"**Arguments Attempted**: kwargs = {args_info['kwargs_keys']}\n\n")

                    # Exception details
                    if example['exception_type'] != 'Unknown':
                        report.append(f"**Exception Type**: `{example['exception_type']}`\n\n")

                    # Recovery
                    if 'recovery' in example:
                        rec = example['recovery']
                        report.append(f"**Recovery**: ")
                        if rec['success']:
                            report.append(f"✅ Succeeded after {rec['iterations_to_recovery']} iterations")
                        else:
                            report.append(f"❌ Failed to recover")
                        if rec['alternative_tool_used']:
                            report.append(f" (switched to `{rec['alternative_tool_used']}`)")
                        elif rec['retry_same_tool']:
                            report.append(f" (retried same tool)")
                        report.append("\n\n")

            report.append("\n---\n\n")

        # Agent Expectation Analysis
        report.append("## Agent Expectation vs Reality Analysis\n\n")
        report.append("### Common Misconceptions\n\n")

        # Analyze patterns in reasoning/code
        misconceptions = self.identify_misconceptions()
        for i, misconception in enumerate(misconceptions, 1):
            report.append(f"#### Misconception {i}: {misconception['title']}\n\n")
            report.append(f"{misconception['description']}\n\n")
            report.append(f"**Frequency**: {misconception['frequency']} occurrences\n\n")
            report.append(f"**Example**:\n```python\n{misconception['example']}\n```\n\n")
            if 'correction' in misconception:
                report.append(f"**Correct Usage**:\n```python\n{misconception['correction']}\n```\n\n")
            report.append("\n")

        # Recovery Pattern Analysis
        report.append("## Recovery Pattern Analysis\n\n")

        if self.recovery_patterns:
            # Analyze recovery strategies
            retry_same = sum(1 for rp in self.recovery_patterns if rp['recovery'].get('retry_same_tool'))
            switch_tool = sum(1 for rp in self.recovery_patterns if rp['recovery'].get('alternative_tool_used'))

            report.append(f"**Total Failures with Recovery Attempt**: {len(self.recovery_patterns)}\n")
            report.append(f"**Retried Same Tool**: {retry_same} ({retry_same/len(self.recovery_patterns)*100:.1f}%)\n")
            report.append(f"**Switched to Alternative Tool**: {switch_tool} ({switch_tool/len(self.recovery_patterns)*100:.1f}%)\n\n")

            # Average iterations to recovery
            recovery_times = [rp['recovery']['iterations_to_recovery'] for rp in self.recovery_patterns if rp['recovery']['iterations_to_recovery'] > 0]
            if recovery_times:
                avg_recovery = sum(recovery_times) / len(recovery_times)
                report.append(f"**Average Iterations to Recovery**: {avg_recovery:.2f}\n\n")

            # Most effective recovery tools
            alternative_tools = [rp['recovery']['alternative_tool_used'] for rp in self.recovery_patterns if rp['recovery'].get('alternative_tool_used')]
            if alternative_tools:
                tool_counts = Counter(alternative_tools)
                report.append("**Most Common Alternative Tools Used**:\n")
                for tool, count in tool_counts.most_common(5):
                    report.append(f"- `{tool}`: {count} times\n")
                report.append("\n")

        # Recommendations
        report.append("## Recommendations for Tool Improvements\n\n")
        recommendations = self.generate_recommendations()
        for i, rec in enumerate(recommendations, 1):
            report.append(f"### {i}. {rec['title']}\n\n")
            report.append(f"**Problem**: {rec['problem']}\n\n")
            report.append(f"**Impact**: {rec['impact']}\n\n")
            report.append(f"**Proposed Solution**:\n{rec['solution']}\n\n")
            if 'example' in rec:
                report.append(f"**Example**:\n{rec['example']}\n\n")
            report.append("---\n\n")

        # Task and Strategy Breakdown
        report.append("## Failure Distribution by Task and Strategy\n\n")

        report.append("### By Task\n\n")
        for task, failures in sorted(self.task_failures.items(), key=lambda x: len(x[1]), reverse=True):
            report.append(f"- **{task}**: {len(failures)} failures\n")

        report.append("\n### By Strategy\n\n")
        for strategy, failures in sorted(self.strategy_failures.items(), key=lambda x: len(x[1]), reverse=True):
            report.append(f"- **{strategy}**: {len(failures)} failures\n")

        report.append("\n")

        return ''.join(report)

    def identify_misconceptions(self) -> List[Dict]:
        """Identify common agent misconceptions from failure patterns."""
        misconceptions = []

        # Check for llm_query attempts
        llm_query_attempts = [f for f in self.failures if 'llm_query' in f.get('agent_code', '').lower()]
        if llm_query_attempts:
            example = llm_query_attempts[0]
            code_lines = [line for line in example['agent_code'].split('\n') if 'llm_query' in line.lower()]
            misconceptions.append({
                'title': 'Expecting llm_query tool to be available',
                'description': 'Agents frequently attempt to call a non-existent `llm_query()` function to ask questions about the schema or data structure.',
                'frequency': len(llm_query_attempts),
                'example': code_lines[0] if code_lines else 'llm_query(prompt)',
                'correction': '# llm_query is not available. Use sparql_peek, sparql_describe, or exploratory queries instead.\n# Example:\ninfo = sparql_peek(\'up:Protein\')  # Inspect class structure\ndesc = sparql_describe(\'up:Protein\')  # Get RDF description'
            })

        # Check for argument mismatches - extract specific patterns
        arg_errors = self.error_types.get('argument_mismatch', [])
        if arg_errors:
            # Group by specific argument errors
            limit_errors = [f for f in arg_errors if 'limit' in f['error_message'].lower()]
            pattern_errors = [f for f in arg_errors if 'pattern' in f['error_message'].lower()]
            positional_errors = [f for f in arg_errors if 'positional' in f['error_message'].lower()]

            if limit_errors:
                example = limit_errors[0]
                misconceptions.append({
                    'title': 'Passing limit as keyword argument',
                    'description': 'Agents try to pass `limit=N` to tools that do not accept this parameter.',
                    'frequency': len(limit_errors),
                    'example': example.get('tool_call_code', 'tool_call(resource, limit=10)') or f"{example['tool']}(..., limit=10)",
                    'correction': f"# {example['tool']} does not accept limit parameter\n# Use positional argument or check tool signature\n{example['tool']}(resource)  # Correct usage"
                })

            if pattern_errors:
                example = pattern_errors[0]
                misconceptions.append({
                    'title': 'Passing pattern as keyword argument',
                    'description': 'Agents try to use `pattern=` parameter that does not exist.',
                    'frequency': len(pattern_errors),
                    'example': example.get('tool_call_code', 'tool_call(pattern="...")') or f"{example['tool']}(pattern='...')",
                    'correction': f"# Check tool signature for correct parameter names"
                })

            if positional_errors:
                example = positional_errors[0]
                misconceptions.append({
                    'title': 'Incorrect number of positional arguments',
                    'description': 'Agents pass wrong number of positional arguments to tools.',
                    'frequency': len(positional_errors),
                    'example': example.get('tool_call_code', 'tool_call(arg1, arg2, arg3)') or f"{example['tool']}(too, many, args)"
                })

        # Check for timeout patterns
        timeout_errors = self.error_types.get('timeout', [])
        if timeout_errors:
            # Look for patterns in queries that timeout
            long_query_attempts = []
            for f in timeout_errors:
                if 'SELECT' in f.get('agent_code', '') and 'LIMIT' not in f.get('agent_code', '').upper():
                    long_query_attempts.append(f)

            if long_query_attempts:
                example = long_query_attempts[0]
                code_lines = example['agent_code'].split('\n')
                query_lines = []
                in_query = False
                for line in code_lines:
                    if 'SELECT' in line.upper() or in_query:
                        in_query = True
                        query_lines.append(line)
                        if line.strip().endswith('"""') or line.strip().endswith("'''"):
                            break

                misconceptions.append({
                    'title': 'Running unbounded queries without LIMIT',
                    'description': 'Agents construct queries that scan large datasets without LIMIT clauses, causing timeouts.',
                    'frequency': len(long_query_attempts),
                    'example': '\n'.join(query_lines[:10]) if query_lines else 'N/A',
                    'correction': '# Always use LIMIT for exploratory queries\nquery = """\nSELECT ?s ?p ?o\nWHERE { ?s ?p ?o }\nLIMIT 100  # Add LIMIT to prevent timeouts\n"""'
                })

        return misconceptions

    def generate_recommendations(self) -> List[Dict]:
        """Generate concrete recommendations for each problematic tool."""
        recommendations = []

        # Analyze each tool's failures
        for tool, failures in sorted(self.tool_failures.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
            # Aggregate error types for this tool
            error_cats = Counter(f['error_category'] for f in failures)
            top_error = error_cats.most_common(1)[0] if error_cats else (None, 0)

            rec = {
                'title': f'Improve `{tool}` Tool',
                'problem': f'{len(failures)} failures recorded. Most common issue: {top_error[0].replace("_", " ") if top_error[0] else "various errors"}.',
                'impact': f'{len(failures)} failed trajectories affected.',
                'solution': ''
            }

            # Tool-specific recommendations
            if tool == 'sparql_query':
                if 'timeout' in error_cats:
                    rec['solution'] = """
1. **Add query validation**: Check for unbounded queries (no LIMIT) and warn/reject them
2. **Add timeout hints in docstring**: Make it clear that queries should include LIMIT clauses
3. **Provide query templates**: Include examples of safe query patterns
4. **Add automatic LIMIT injection**: Option to auto-add LIMIT if not present

**Improved Docstring**:
```python
def sparql_query(query: str, limit: int = None) -> Dict:
    '''Execute SPARQL query against the endpoint.

    IMPORTANT: Always include a LIMIT clause to prevent timeouts!
    The endpoint will timeout after 30 seconds on unbounded queries.

    Args:
        query: SPARQL query string (should include LIMIT clause)
        limit: If provided, automatically adds LIMIT clause

    Returns:
        Result handle dict with 'key', 'rows', 'preview' fields

    Example:
        # Good - includes LIMIT
        result = sparql_query(\"\"\"
            SELECT ?s ?p ?o
            WHERE { ?s ?p ?o }
            LIMIT 100
        \"\"\")

        # Also good - use limit parameter
        result = sparql_query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }", limit=100)
    '''
    ...
```
"""

            elif tool == 'sparql_peek':
                rec['solution'] = """
1. **Clarify URI vs prefix usage**: Examples showing both URI and prefix formats
2. **Add error messages**: Better error messages when resource not found
3. **Provide discovery help**: Suggest using sparql_describe or endpoint_info first

**Improved Docstring**:
```python
def sparql_peek(resource: str, limit: int = 5) -> List[Dict]:
    '''Peek at instances and properties of a class or resource.

    Args:
        resource: Can be:
            - Full URI: 'http://purl.uniprot.org/core/Protein'
            - Prefixed: 'up:Protein'
            - Local name: 'Protein' (will search in default namespaces)
        limit: Max instances to return (default: 5)

    Returns:
        List of instance dicts with their properties

    Example:
        # Peek at Protein class
        proteins = sparql_peek('up:Protein')

        # Use full URI
        proteins = sparql_peek('http://purl.uniprot.org/core/Protein')

    Tip: If resource not found, try sparql_describe() first to explore structure.
    '''
    ...
```
"""

            elif 'llm' in tool.lower() or tool == 'llm_query':
                rec['solution'] = """
1. **Document missing tools**: Clearly state that llm_query is NOT available
2. **Provide alternatives**: Show how to achieve similar goals with available tools
3. **Update system prompt**: Explicitly list available tools

**Add to Tool Documentation**:
```markdown
## ⚠️ Tool NOT Available: llm_query

Agents often try to call `llm_query(prompt)` to ask questions about schema.
This tool does NOT exist.

### Alternatives:

1. **For schema exploration**: Use `sparql_peek(class_name)` or `sparql_describe(uri)`
2. **For data inspection**: Use `sparql_slice(result_handle)` to view query results
3. **For endpoint info**: Use `endpoint_info()` to get namespace prefixes and docs
4. **For discovery**: Run small exploratory SPARQL queries with LIMIT 10

### Example:
```python
# ❌ WRONG - llm_query does not exist
schema_info = llm_query("What classes are available?")

# ✅ CORRECT - use actual tools
info = endpoint_info()
print(info['prefixes'])  # See available namespaces

# Explore a class
instances = sparql_peek('up:Protein')  # Get sample instances

# Or run exploratory query
result = sparql_query(\"\"\"
    SELECT DISTINCT ?type
    WHERE { ?s a ?type }
    LIMIT 20
\"\"\")
```
"""

            else:
                # Generic recommendation
                rec['solution'] = f"""
1. **Improve docstring**: Add clear parameter descriptions and examples
2. **Add error handling**: Provide helpful error messages
3. **Add validation**: Check arguments before execution
4. **Document common mistakes**: Add troubleshooting section
"""

            recommendations.append(rec)

        # Add general recommendations
        recommendations.append({
            'title': 'Add Tool Usage Dashboard',
            'problem': 'Agents lack visibility into which tools are available and how to use them.',
            'impact': f'{len([f for f in self.failures if "missing" in f["error_category"]])} failures due to missing tools/attributes.',
            'solution': """
Create a `list_tools()` function that returns:
- Available tool names
- Tool signatures
- Example usage
- Related tools

**Example Implementation**:
```python
def list_tools() -> Dict[str, Dict]:
    '''List all available tools with signatures and examples.'''
    return {
        'sparql_query': {
            'signature': 'sparql_query(query: str) -> Dict',
            'description': 'Execute SPARQL query',
            'example': 'result = sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")'
        },
        'sparql_peek': {
            'signature': 'sparql_peek(resource: str, limit: int = 5) -> List[Dict]',
            'description': 'Peek at class instances',
            'example': 'instances = sparql_peek("up:Protein")'
        },
        # ... more tools
    }
```
"""
        })

        return recommendations

    def run_analysis(self):
        """Run full analysis on all trajectory files."""
        print("🔍 Finding trajectory files...")
        trajectory_files = list(LOGS_BASE.rglob("*.jsonl"))
        print(f"Found {len(trajectory_files)} trajectory files")

        print("\n📊 Analyzing trajectories...")
        for i, filepath in enumerate(trajectory_files, 1):
            if i % 10 == 0:
                print(f"  Processed {i}/{len(trajectory_files)}...")
            self.analyze_trajectory(filepath)

        print(f"\n✅ Analysis complete!")
        print(f"   Total failures found: {len(self.failures)}")
        print(f"   Tools with failures: {len(self.tool_failures)}")
        print(f"   Error categories: {len(self.error_types)}")

        print("\n📝 Generating report...")
        report = self.generate_report()

        return report


def main():
    analyzer = ToolFailureAnalyzer()
    report = analyzer.run_analysis()

    # Save report
    output_path = LOGS_BASE.parent / "TOOL_FAILURE_ANALYSIS.md"
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"\n✅ Report saved to: {output_path}")
    print(f"   Report size: {len(report)} characters")


if __name__ == "__main__":
    main()
