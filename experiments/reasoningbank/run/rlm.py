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

    # Build context
    builder = Builder(cfg)
    ctx = builder.build(g, task, mem)

    # Build tools
    store = Store()
    tools = builder.tools(store, graph_path)
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
            print(f"  [{event_type}] {str(data)[:100]}")
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
        res = rlm(context=ctx, question=task)

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

        # Get token usage
        lm_usage = {}
        if hasattr(res, 'get_lm_usage'):
            lm_usage = res.get_lm_usage() or {}

        log_event('run_complete', {
            'converged': True,
            'answer_length': len(str(getattr(res, 'answer', ''))),
            'has_sparql': getattr(res, 'sparql', None) is not None,
            'iterations': len(history),
            'lm_usage': lm_usage,
        })

        # Save full history to log file
        if log_path and history:
            log_event('history', {'entries': [str(h)[:500] for h in history]})

        return Result(
            answer=getattr(res, 'answer', str(res)),
            sparql=getattr(res, 'sparql', None),
            converged=True,
            iters=len(history),
            leakage=inst.metrics,
            trace=trajectory,
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
        )
