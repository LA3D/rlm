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
from experiments.reasoningbank.ctx.cache import build_with_cache
from experiments.reasoningbank.tools.local_interpreter import LocalPythonInterpreter

# Apply DSPy bug patches
from experiments.reasoningbank.tools import dspy_patches

# Configure DSPy with Anthropic model if not already configured
if not hasattr(dspy.settings, 'lm') or dspy.settings.lm is None:
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ValueError("Set ANTHROPIC_API_KEY environment variable")
    lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
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
    trajectory: list[dict] = None  # List of {code, output} execution steps
    thinking: str|None = None      # Extended thinking content (if available)

    def __post_init__(self):
        if self.trajectory is None:
            self.trajectory = []

def build_context_uniprot(cfg: Cfg, ont_path: str, task: str, mem: MemStore|None = None, rollout_id: int|None = None) -> str:
    """Build context from layers using local ontology metadata.

    L0 and L1 are built from local ontology file (core.owl or core.ttl).
    L2 retrieves from memory store.
    L3 uses guide text if provided.

    Args:
        cfg: Context configuration with layer toggles
        ont_path: Path to UniProt ontology directory (contains core.owl/core.ttl)
        task: Query string (for L2 retrieval)
        mem: Memory store (for L2)
        rollout_id: Optional rollout identifier (prevents caching by making prompts unique)

    Returns:
        Assembled context string
    """
    parts = []

    # Add unique rollout marker to prevent prompt caching
    # This is invisible to the agent (HTML comment) but makes each prompt unique
    if rollout_id is not None:
        parts.append(f"<!-- Rollout ID: {rollout_id} -->")
        parts.append("")  # Blank line for readability

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

    # L0: Sense card (cached)
    if cfg.l0.on:
        sense_card = build_with_cache(str(ont_file), 'l0', cfg.l0.budget, l0_sense.pack)
        if sense_card:
            parts.append(sense_card)

    # L1: Schema constraints (cached)
    if cfg.l1.on:
        constraints = build_with_cache(str(ont_file), 'l1', cfg.l1.budget, l1_schema.pack)
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
    temperature: float = 0.0,
    seed: int|None = None,
    verbose: bool = True,
    log_path: str|None = None,
    use_local_interpreter: bool = False,
    rollout_id: int|None = None,
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
        temperature: LLM temperature (0.0=deterministic, 0.7=stochastic)
        seed: Explicit seed for reproducibility/diversity (Anthropic doesn't support this)
        verbose: Print progress
        log_path: Path to trajectory log file
        use_local_interpreter: If True, use LocalPythonInterpreter instead of Deno sandbox.
                               Avoids sandbox corruption issues but has no security isolation.
        rollout_id: Unique identifier for this rollout (prevents prompt caching)

    Returns:
        Result with answer, SPARQL, convergence status, and metrics
    """
    import json
    from datetime import datetime

    # Build context from local ontology metadata
    ctx = build_context_uniprot(cfg, ont_path, task, mem, rollout_id=rollout_id)
    exec_note = (
        "EXECUTION NOTE: In [[ ## code ## ]] output raw Python only. "
        "Do NOT include markdown fences (```), language tags, or prose.\n\n"
        "SUBMIT SYNTAX: Use keyword arguments: SUBMIT(sparql='...', answer='...') "
        "NOT positional: SUBMIT(sparql_var, answer_var)"
    )
    ctx = f"{exec_note}\n\n{ctx}" if ctx else exec_note

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

    # Create SPARQL tools for remote endpoint
    sparql_tools = create_tools(endpoint)
    tools = sparql_tools.as_dspy_tools()

    # Instrument tools for leakage tracking AND tool call logging
    inst = Instrumented(tools, log_callback=log_event)

    log_event('run_start', {
        'task': task,
        'endpoint': sparql_tools.endpoint,
        'context_size': len(ctx),
        'max_iters': max_iters,
        'temperature': temperature,
        'seed': seed
    })

    # Configure main LLM with temperature and optional seed (for stochastic evaluation)
    if temperature > 0.0 or seed is not None:
        lm_kwargs = {
            'api_key': os.environ['ANTHROPIC_API_KEY'],
            'temperature': temperature,
        }
        if seed is not None:
            lm_kwargs['seed'] = seed  # Anthropic beta support, "best effort" only
        lm = dspy.LM(
            'anthropic/claude-sonnet-4-5-20250929',
            **lm_kwargs
        )
        dspy.configure(lm=lm)

    # Configure sub-LLM (cheaper model for llm_query)
    sub_lm = dspy.LM('anthropic/claude-haiku-4-5-20251001', api_key=os.environ['ANTHROPIC_API_KEY'])

    # Create interpreter (local or Deno sandbox)
    interpreter = None
    if use_local_interpreter:
        if verbose:
            print("  Using LocalPythonInterpreter (no Deno sandbox)")
        interpreter = LocalPythonInterpreter(
            tools=inst.wrap(),
            output_fields=[{'name': 'sparql'}, {'name': 'answer'}],
            sub_lm=sub_lm  # Enable llm_query in LocalPythonInterpreter
        )

    # Run RLM with remote endpoint tools
    rlm = dspy.RLM(
        "context, question -> sparql, answer",
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        tools=inst.wrap(),
        sub_lm=sub_lm,  # Enables llm_query and llm_query_batched
        interpreter=interpreter,  # Use local interpreter if specified
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

            # Log iteration details from history with reasoning/code extraction
            import re
            for i, hist_entry in enumerate(history, 1):
                try:
                    # Extract response text from history entry
                    response_text = None
                    if 'outputs' in hist_entry and isinstance(hist_entry.get('outputs'), list):
                        outputs_list = hist_entry['outputs']
                        if outputs_list and len(outputs_list) > 0:
                            response_text = str(outputs_list[0])
                    elif 'response' in hist_entry and hist_entry.get('response'):
                        response = hist_entry['response']
                        if hasattr(response, 'choices') and response.choices:
                            if len(response.choices) > 0:
                                choice = response.choices[0]
                                if hasattr(choice, 'message') and choice.message:
                                    response_text = str(choice.message.content)

                    # Extract reasoning and code sections
                    reasoning = None
                    code = None
                    if response_text:
                        # Extract reasoning section
                        reasoning_match = re.search(
                            r'\[\[\s*##\s*reasoning\s*##\s*\]\]\s*(.*?)(?:\[\[\s*##|$)',
                            response_text, re.DOTALL | re.IGNORECASE
                        )
                        if reasoning_match:
                            reasoning = reasoning_match.group(1).strip()[:500]  # Limit to 500 chars

                        # Extract code section
                        code_match = re.search(
                            r'\[\[\s*##\s*code\s*##\s*\]\]\s*```python\s*(.*?)\s*```',
                            response_text, re.DOTALL | re.IGNORECASE
                        )
                        if not code_match:
                            code_match = re.search(
                                r'\[\[\s*##\s*code\s*##\s*\]\]\s*\n(.*?)(?:\[\[\s*##|$)',
                                response_text, re.DOTALL
                            )
                        if code_match:
                            code = code_match.group(1).strip()[:1000]  # Limit to 1000 chars
                            if code.endswith('```'):
                                code = code[:-3].strip()

                    # Try to get output from next iteration's REPL history
                    output = None
                    if i < len(history) and 'messages' in history[i]:
                        next_messages = history[i].get('messages', [])
                        if next_messages and len(next_messages) >= 2:
                            user_content = next_messages[1].get('content', '') if next_messages[1].get('role') == 'user' else ''
                            output_match = re.search(
                                r'Output[^:]*:\s*(.*?)(?=\n===\s*Step|\[\[\s*##|$)',
                                user_content, re.DOTALL
                            )
                            if output_match:
                                output = output_match.group(1).strip()[:500]  # Limit to 500 chars

                    # Log iteration event with full content
                    log_event('iteration', {
                        'iteration': i,
                        'total': len(history),
                        'reasoning': reasoning,
                        'code': code,
                        'output': output,
                    })
                except Exception as e:
                    if verbose:
                        print(f"    Warning: Could not parse history entry {i}: {e}")
                    # Still log basic info on error
                    log_event('iteration', {
                        'iteration': i,
                        'total': len(history),
                        'parse_error': str(e)
                    })

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

        # Detect LLM refusal: check if all LM calls were refused
        refusal_detected = False
        try:
            from dspy.clients.base_lm import GLOBAL_HISTORY
            if GLOBAL_HISTORY:
                relevant_calls = list(GLOBAL_HISTORY)[history_before:history_after]
                refusals = sum(
                    1 for entry in relevant_calls
                    if "finish_reason='refusal'" in str(entry.get('response', ''))
                )
                if refusals > 0 and refusals == len(relevant_calls):
                    refusal_detected = True
                    answer = f"LLM refused ({refusals}/{len(relevant_calls)} calls refused by safety filter)"
                    sparql = None
                    if verbose:
                        print(f"  WARNING: LLM refused all {refusals} calls (safety filter false positive)")
        except Exception:
            pass

        converged = not refusal_detected

        log_event('run_complete', {
            'converged': converged,
            'refusal_detected': refusal_detected,
            'answer_length': len(str(answer)),
            'answer_preview': str(answer)[:500],
            'has_sparql': sparql is not None,
            'sparql': sparql if sparql else None,
            'iterations': len(history),
            'lm_usage': lm_usage,
        })
        # Update leakage metrics from run
        inst.metrics.subcalls = lm_usage.get('total_calls', 0)
        inst.metrics.vars_n = len(getattr(sparql_tools.store, '_results', {}))

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
            answer=answer,
            sparql=sparql,
            converged=converged,
            iters=len(history),
            leakage=inst.metrics,
            trace=trajectory,
            trajectory=exec_trajectory,
        )
    except Exception as e:
        import traceback
        import sys

        # Capture full traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        full_traceback = ''.join(tb_lines)

        # Find the specific line with .strip() if it exists
        strip_location = None
        for frame_summary in traceback.extract_tb(exc_traceback):
            if '.strip()' in frame_summary.line:
                strip_location = {
                    'filename': frame_summary.filename,
                    'line': frame_summary.lineno,
                    'code': frame_summary.line,
                    'function': frame_summary.name,
                }
                break

        # Check for LLM refusal in GLOBAL_HISTORY
        refusal_detected = False
        try:
            from dspy.clients.base_lm import GLOBAL_HISTORY
            if GLOBAL_HISTORY:
                last_entry = GLOBAL_HISTORY[-1]
                response_str = str(last_entry.get('response', ''))
                if "finish_reason='refusal'" in response_str:
                    refusal_detected = True
        except Exception:
            pass

        # Log detailed error information
        error_data = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': full_traceback,
            'task_length': len(task),
            'task_preview': task[:200] if task else None,
            'context_length': len(ctx),
            'context_preview': ctx[:200] if ctx else None,
            'refusal_detected': refusal_detected,
        }

        if strip_location:
            error_data['strip_location'] = strip_location

        log_event('run_error', error_data)

        if verbose:
            print(f"  Error: {e}")
            print(f"  Type: {type(e).__name__}")
            print(f"\n  Full traceback:")
            print(full_traceback)
            if strip_location:
                print(f"\n  .strip() called at:")
                print(f"    {strip_location['filename']}:{strip_location['line']}")
                print(f"    {strip_location['code']}")

        return Result(
            answer=f"Error: {e}",
            sparql=None,
            converged=False,
            iters=0,
            leakage=inst.metrics,
            trace=trajectory,
            trajectory=[],
        )
