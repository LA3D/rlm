"""Test how context impacts tool usage in RLM.

Compare E1 (empty) vs E2 (L0 sense card) to see when tools are used.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import dspy
from rdflib import Graph
from experiments.reasoningbank.prototype.ctx.builder import Builder, Cfg, Layer
from experiments.reasoningbank.prototype.core.blob import Store
from experiments.reasoningbank.prototype.core import graph as G

# Configure DSPy
if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.configure(lm=lm)

# Graph path
ont_path = 'ontology/prov.ttl'

# Task
task = "What is Activity?"

# Track tool calls
tool_calls = []

def track_calls(name, original_fn):
    """Wrap a tool to track when it's called."""
    def wrapper(*args, **kwargs):
        call_info = f"{name}({args}, {kwargs})"
        print(f"    [TOOL CALL] {call_info}")
        tool_calls.append(call_info)
        return original_fn(*args, **kwargs)
    wrapper.__name__ = original_fn.__name__
    wrapper.__doc__ = original_fn.__doc__
    wrapper.__annotations__ = getattr(original_fn, '__annotations__', {})
    return wrapper

def run_experiment(exp_name, cfg, show_trajectory=False):
    """Run single experiment and report tool usage."""
    global tool_calls
    tool_calls = []

    print(f"\n{'='*70}")
    print(f"{exp_name}")
    print(f"{'='*70}")

    # Build context
    g = Graph().parse(ont_path)
    builder = Builder(cfg)
    ctx = builder.build(g, task, None)

    print(f"\nContext size: {len(ctx)} chars")
    if ctx:
        print(f"Context preview:\n{ctx[:300]}...")
    else:
        print("Context: (empty)")

    # Build tools with tracking
    store = Store()
    tools_raw = builder.tools(store, ont_path)
    tools = {name: track_calls(name, fn) for name, fn in tools_raw.items()}

    print(f"\nTools available: {', '.join(tools.keys())}")

    # Run RLM
    print(f"\nRunning RLM...")
    rlm = dspy.RLM(
        "context, question -> answer",
        max_iterations=5,
        max_llm_calls=10,
        tools=tools,
    )

    res = rlm(context=ctx, question=task)

    # Report results
    print(f"\n{'='*70}")
    print(f"RESULTS: {exp_name}")
    print(f"{'='*70}")
    print(f"Iterations: {len(res.trajectory)}")
    print(f"Tool calls: {len(tool_calls)}")
    if tool_calls:
        print("Tools used:")
        for call in tool_calls:
            print(f"  - {call}")
    else:
        print("No tools called!")

    print(f"\nAnswer: {res.answer[:200]}...")

    if show_trajectory and res.trajectory:
        print(f"\nTrajectory (first 2 iterations):")
        for i, step in enumerate(res.trajectory[:2]):
            print(f"\n  Iteration {i+1}:")
            print(f"    Reasoning: {step.get('reasoning', '')[:150]}...")
            print(f"    Code: {step.get('code', '')[:150]}...")
            print(f"    Output: {step.get('output', '')[:150]}...")

    return {
        'iterations': len(res.trajectory),
        'tool_calls': len(tool_calls),
        'tools_used': list(set([c.split('(')[0] for c in tool_calls])),
        'answer': res.answer,
    }

# E1: Baseline (empty context)
e1_cfg = Cfg()  # All layers off by default

# E2: L0 only (sense card)
e2_cfg = Cfg(
    l0=Layer(on=True, budget=600)
)

print("Starting context impact experiment...")
print(f"Task: {task}")
print(f"Ontology: {ont_path}")

e1_result = run_experiment("E1: Baseline (empty context)", e1_cfg, show_trajectory=True)
e2_result = run_experiment("E2: L0 Sense Card", e2_cfg, show_trajectory=True)

print(f"\n{'='*70}")
print("COMPARISON")
print(f"{'='*70}")
print(f"\nE1 (empty):        {e1_result['tool_calls']} tool calls, {e1_result['iterations']} iters")
print(f"E2 (L0 sense):     {e2_result['tool_calls']} tool calls, {e2_result['iterations']} iters")
print(f"\nTools used in E1: {e1_result['tools_used'] or 'None'}")
print(f"Tools used in E2: {e2_result['tools_used'] or 'None'}")
