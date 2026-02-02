"""Direct DSPy RLM runner - no rlm_runtime dependencies.

Uses dspy.RLM with configured context and tools. Returns structured
result with leakage metrics for prompt bloat analysis.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import dspy
from dataclasses import dataclass
from rdflib import Graph
from experiments.reasoningbank.core.blob import Store
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.core.instrument import Metrics, Instrumented
from experiments.reasoningbank.ctx.builder import Builder, Cfg

# Configure DSPy with Anthropic model if not already configured
if not hasattr(dspy.settings, 'lm') or dspy.settings.lm is None:
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ValueError("Set ANTHROPIC_API_KEY environment variable")
    lm = dspy.LM('anthropic/claude-sonnet-4-20250514', api_key=os.environ['ANTHROPIC_API_KEY'])
    dspy.configure(lm=lm)

@dataclass
class Result:
    "Result from RLM execution."
    answer: str
    sparql: str|None
    converged: bool
    iters: int
    leakage: Metrics
    trace: list[dict]
    trajectory: list[dict] = None  # List of {code, output} execution steps
    thinking: str|None = None      # Extended thinking content (if available)

    def __post_init__(self):
        if self.trajectory is None:
            self.trajectory = []

def run(
    task: str,
    graph_path: str,
    cfg: Cfg,
    mem: MemStore|None = None,
    max_iters: int = 12,
    max_calls: int = 25,
    verbose: bool = True,
    log_path: str|None = None,
) -> Result:
    "Run `task` using dspy.RLM with configured context."
    import json
    from datetime import datetime

    # Load graph
    g = Graph().parse(graph_path)

    # Build context (with caching for L0/L1)
    builder = Builder(cfg)
    ctx = builder.build(g, task, mem, g_path=graph_path)
    exec_note = (
        "EXECUTION NOTE: In [[ ## code ## ]] output raw Python only. "
        "Do NOT include markdown fences (```), language tags, or prose."
    )
    ctx = f"{exec_note}\n\n{ctx}" if ctx else exec_note

    # Build tools
    store = Store()
    tools = builder.tools(store, graph_path, mem=mem)
    inst = Instrumented(tools)

    # Prepare trajectory logging
    trajectory = []
    start_time = datetime.now()

    def log_event(event_type: str, data: dict):
        "Log trajectory event."
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        trajectory.append(event)
        if verbose:
            msg = f"  [{event_type}] {str(data)[:100]}"
            print(msg)
            inst.metrics.stdout_chars += len(msg) + 1
        if log_path:
            with open(log_path, 'a') as f:
                f.write(json.dumps(event) + '\n')

    log_event('run_start', {'task': task, 'context_size': len(ctx), 'max_iters': max_iters})

    # Run RLM
    rlm = dspy.RLM(
        "context, question -> sparql, answer",
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        tools=inst.wrap(),
    )

    try:
        if verbose: print(f"  Executing RLM...")

        # Capture history length before call
        history_before = len(dspy.settings.lm.history) if hasattr(dspy.settings, 'lm') and hasattr(dspy.settings.lm, 'history') else 0

        res = rlm(context=ctx, question=task)

        # Capture history length after call
        history_after = len(dspy.settings.lm.history) if hasattr(dspy.settings, 'lm') and hasattr(dspy.settings.lm, 'history') else 0

        # Extract history and token usage
        history = []
        if hasattr(rlm, 'history') and rlm.history:
            history = rlm.history
            if verbose:
                print(f"  History entries: {len(history)}")
                if hasattr(rlm, 'inspect_history'):
                    inspection = rlm.inspect_history(n=3)
                    if inspection:
                        print(f"  Last 3 history entries:")
                        for entry in inspection[-3:]:
                            print(f"    {str(entry)[:200]}")

        # Get token usage from DSPy LM history (only calls from this run)
        lm_usage = {
            'total_calls': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'cache_read_tokens': 0,
            'cache_creation_tokens': 0,
            'total_cost': 0.0
        }
        try:
            if hasattr(dspy.settings, 'lm') and hasattr(dspy.settings.lm, 'history'):
                # Only extract usage from calls made during this RLM run
                relevant_calls = dspy.settings.lm.history[history_before:history_after]

                for call in relevant_calls:
                    lm_usage['total_calls'] += 1

                    # Extract usage from call dict
                    usage = call.get('usage', {})
                    lm_usage['prompt_tokens'] += usage.get('prompt_tokens', 0)
                    lm_usage['completion_tokens'] += usage.get('completion_tokens', 0)
                    lm_usage['total_tokens'] += usage.get('total_tokens', 0)
                    lm_usage['cache_read_tokens'] += usage.get('cache_read_input_tokens', 0)
                    lm_usage['cache_creation_tokens'] += usage.get('cache_creation_input_tokens', 0)
                    lm_usage['total_cost'] += call.get('cost', 0.0)
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not extract token usage: {e}")
            lm_usage['error'] = str(e)

        log_event('run_complete', {
            'converged': True,
            'answer_length': len(str(getattr(res, 'answer', ''))),
            'has_sparql': getattr(res, 'sparql', None) is not None,
            'iterations': len(history),
            'lm_usage': lm_usage,
        })
        # Update leakage metrics from run
        inst.metrics.subcalls = lm_usage.get('total_calls', 0)
        inst.metrics.vars_n = len(getattr(store, '_blobs', {}))

        # Save full history to log file
        if log_path and history:
            log_event('history', {'entries': [str(h)[:500] for h in history]})

        # Extract execution trajectory from RLM history
        exec_trajectory = []
        if history:
            try:
                import re

                # Extract code blocks and outputs from RLM history
                for i, entry in enumerate(history):
                    try:
                        # Get response text
                        response_text = None
                        if 'outputs' in entry and isinstance(entry.get('outputs'), list):
                            outputs_list = entry['outputs']
                            if outputs_list and len(outputs_list) > 0:
                                response_text = outputs_list[0]
                        elif 'response' in entry and entry.get('response'):
                            response = entry['response']
                            if hasattr(response, 'choices') and response.choices:
                                if len(response.choices) > 0:
                                    choice = response.choices[0]
                                    if hasattr(choice, 'message') and choice.message:
                                        response_text = choice.message.content

                        if response_text:
                            # Extract code block from this iteration
                            # Try with backticks first (preferred format)
                            code_pattern = r'\[\[\s*##\s*code\s*##\s*\]\]\s*```python\s+(.*?)\s*```'
                            code_match = re.search(code_pattern, str(response_text), re.DOTALL | re.IGNORECASE)

                            # Fallback: code directly after marker (no backticks)
                            if not code_match:
                                code_pattern_alt = r'\[\[\s*##\s*code\s*##\s*\]\]\s*\n(.*?)(?:\[\[\s*##|\Z)'
                                code_match = re.search(code_pattern_alt, str(response_text), re.DOTALL)

                            if code_match:
                                code = code_match.group(1).strip()
                                # Remove trailing ``` if present from alt pattern
                                if code.endswith('```'):
                                    code = code[:-3].strip()

                                # Try to get output from next iteration's user message (REPL history)
                                output = "(output not captured)"
                                try:
                                    if i + 1 < len(history) and 'messages' in history[i + 1]:
                                        next_messages = history[i + 1].get('messages', [])
                                        if next_messages and len(next_messages) >= 2:
                                            if next_messages[1].get('role') == 'user':
                                                user_content = next_messages[1].get('content', '')
                                                # Extract REPL history section
                                                repl_section_match = re.search(
                                                    r'\[\[\s*##\s*repl_history\s*##\s*\]\](.*?)\[\[\s*##',
                                                    user_content,
                                                    re.DOTALL
                                                )
                                                if repl_section_match:
                                                    repl_history = repl_section_match.group(1)
                                                    # Find all outputs in REPL history
                                                    # Format: "Output (XXX chars):\n<content>"
                                                    output_pattern = r'Output[^:]*:\s*(.*?)(?=\n===\s*Step|\Z)'
                                                    output_matches = re.findall(output_pattern, repl_history, re.DOTALL)
                                                    if output_matches:
                                                        # Get the last output (most recent step)
                                                        output = output_matches[-1].strip()[:1000]  # Limit to 1000 chars
                                except Exception:
                                    # If output extraction fails, use default
                                    pass

                                exec_trajectory.append({
                                    'code': code,
                                    'output': output
                                })
                    except Exception:
                        # Skip this entry if parsing fails
                        continue
            except Exception as e:
                if verbose:
                    print(f"  Warning: Trajectory extraction failed: {e}")
                # Continue with empty trajectory

        return Result(
            answer=getattr(res, 'answer', str(res)),
            sparql=getattr(res, 'sparql', None),
            converged=True,
            iters=len(history),
            leakage=inst.metrics,
            trace=trajectory,
            trajectory=exec_trajectory,
        )
    except Exception as e:
        log_event('run_error', {'error': str(e), 'type': type(e).__name__})
        return Result(
            answer=f"Error: {e}",
            sparql=None,
            converged=False,
            iters=0,
            leakage=inst.metrics,
            trace=trajectory,
            trajectory=[],
        )
