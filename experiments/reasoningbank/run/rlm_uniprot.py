"""DSPy RLM runner for remote SPARQL endpoints (UniProt).

Similar to rlm.py but uses SPARQLTools instead of local graph tools.
Context layers (L0, L1) are still built from local ontology file.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import dspy
from dataclasses import dataclass
from rdflib import Graph
from pathlib import Path
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.core.instrument import Metrics, Instrumented
from experiments.reasoningbank.ctx.builder import Cfg
from experiments.reasoningbank.tools.sparql import SPARQLTools, create_tools
from experiments.reasoningbank.packers import l0_sense, l1_schema, l2_mem, l3_guide

# Configure DSPy with Anthropic model if not already configured
if not hasattr(dspy.settings, 'lm') or dspy.settings.lm is None:
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ValueError("Set ANTHROPIC_API_KEY environment variable")
    lm = dspy.LM('anthropic/claude-sonnet-4-20250514', api_key=os.environ['ANTHROPIC_API_KEY'])
    dspy.configure(lm=lm)

@dataclass
class Result:
    "Result from RLM execution with remote SPARQL endpoint."
    answer: str
    sparql: str|None
    converged: bool
    iters: int
    leakage: Metrics
    trace: list[dict]

def build_context_uniprot(cfg: Cfg, ont_path: str, task: str, mem: MemStore|None = None) -> str:
    """Build context from layers using local ontology metadata.

    L0 and L1 are built from local ontology file (core.owl or core.ttl).
    L2 retrieves from memory store.
    L3 uses guide text if provided.

    Args:
        cfg: Context configuration with layer toggles
        ont_path: Path to UniProt ontology directory (contains core.owl/core.ttl)
        task: Query string (for L2 retrieval)
        mem: Memory store (for L2)

    Returns:
        Assembled context string
    """
    parts = []

    # Find ontology file
    ont_dir = Path(ont_path)
    ont_file = None
    for ext in ['core.ttl', 'core.owl']:
        candidate = ont_dir / ext
        if candidate.exists():
            ont_file = candidate
            break

    if not ont_file:
        print(f"Warning: No core ontology found in {ont_path}")
        return ""

    # Load ontology for L0/L1
    g = Graph().parse(str(ont_file))

    # L0: Sense card
    if cfg.l0.on:
        sense_card = l0_sense.pack(g, cfg.l0.budget)
        if sense_card:
            parts.append(sense_card)

    # L1: Schema constraints
    if cfg.l1.on:
        constraints = l1_schema.pack(g, cfg.l1.budget)
        if constraints:
            parts.append(constraints)

    # L2: Procedural memory
    if cfg.l2.on and mem:
        k_success, k_failure = 2, 1
        success_hits = mem.search(task, k=k_success, polarity='success')
        failure_hits = mem.search(task, k=k_failure, polarity='failure')
        seed_hits = mem.search(task, k=1, polarity='seed')
        all_ids = [h['id'] for h in success_hits + failure_hits + seed_hits]
        if all_ids:
            items = mem.get(all_ids, max_n=len(all_ids))
            mem_text = l2_mem.pack(items, cfg.l2.budget)
            if mem_text:
                parts.append(mem_text)

    # L3: Guide summary
    if cfg.l3.on and cfg.guide_text:
        guide_summary = l3_guide.pack(cfg.guide_text, cfg.l3.budget)
        if guide_summary:
            parts.append(guide_summary)

    return '\n\n'.join(parts)


def run_uniprot(
    task: str,
    ont_path: str,
    cfg: Cfg,
    mem: MemStore|None = None,
    endpoint: str = 'uniprot',
    max_iters: int = 12,
    max_calls: int = 25,
    verbose: bool = True,
    log_path: str|None = None,
) -> Result:
    """Run task using DSPy RLM with remote UniProt SPARQL endpoint.

    Args:
        task: Natural language query
        ont_path: Path to UniProt ontology directory (for L0/L1 metadata)
        cfg: Context configuration (layer toggles)
        mem: Memory store (for L2)
        endpoint: Endpoint name ('uniprot', 'wikidata', etc.)
        max_iters: Maximum RLM iterations
        max_calls: Maximum LLM calls
        verbose: Print progress
        log_path: Path to trajectory log file

    Returns:
        Result with answer, SPARQL, convergence status, and metrics
    """
    import json
    from datetime import datetime

    # Build context from local ontology metadata
    ctx = build_context_uniprot(cfg, ont_path, task, mem)

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

    # Create SPARQL tools for remote endpoint
    sparql_tools = create_tools(endpoint)
    tools = sparql_tools.as_dspy_tools()

    # Instrument tools for leakage tracking AND tool call logging
    inst = Instrumented(tools, log_callback=log_event)

    log_event('run_start', {
        'task': task,
        'endpoint': sparql_tools.endpoint,
        'context_size': len(ctx),
        'max_iters': max_iters
    })

    # Run RLM with remote endpoint tools
    rlm = dspy.RLM(
        "context, question -> sparql, answer",
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        tools=inst.wrap(),
    )

    try:
        if verbose: print(f"  Executing RLM with {endpoint} endpoint...")

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

            # Log iteration details from history
            for i, hist_entry in enumerate(history, 1):
                # Try to extract reasoning and code from history entry
                try:
                    # DSPy RLM history entries are complex - try to extract useful parts
                    hist_str = str(hist_entry)

                    # Log iteration event
                    log_event('iteration', {
                        'iteration': i,
                        'total': len(history),
                        'entry_size': len(hist_str)
                    })
                except Exception as e:
                    if verbose:
                        print(f"    Warning: Could not parse history entry {i}: {e}")

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

        # Get answer and SPARQL
        answer = getattr(res, 'answer', str(res))
        sparql = getattr(res, 'sparql', None)

        log_event('run_complete', {
            'converged': True,
            'answer_length': len(str(answer)),
            'answer_preview': str(answer)[:500],
            'has_sparql': sparql is not None,
            'sparql': sparql if sparql else None,
            'iterations': len(history),
            'lm_usage': lm_usage,
        })

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
        if verbose:
            import traceback
            print(f"  Error: {e}")
            print(traceback.format_exc())
        return Result(
            answer=f"Error: {e}",
            sparql=None,
            converged=False,
            iters=0,
            leakage=inst.metrics,
            trace=trajectory,
        )
