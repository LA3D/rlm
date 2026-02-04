"""Monkey patches for DSPy bugs.

Patches critical bugs in DSPy that affect our usage.
Import this module early to apply patches.
"""

import logging

logger = logging.getLogger(__name__)


def patch_strip_code_fences():
    """Patch DSPy's _strip_code_fences to handle None.

    Bug: DSPy RLM's _strip_code_fences assumes code is always a string,
    but when LLM refuses (finish_reason='refusal'), action.code is None.

    This causes: AttributeError: 'NoneType' object has no attribute 'strip'

    Fix: Check for None before calling .strip()
    """
    try:
        import dspy.predict.rlm as rlm_module

        original_strip = rlm_module._strip_code_fences

        def patched_strip_code_fences(code: str | None) -> str:
            """Strip code fences, handling None gracefully."""
            if code is None:
                return ""
            return original_strip(code)

        rlm_module._strip_code_fences = patched_strip_code_fences
        return True
    except Exception as e:
        print(f"Warning: Could not patch DSPy _strip_code_fences: {e}")
        return False


def patch_process_execution_result():
    """Patch DSPy RLM._process_execution_result to handle None reasoning/code.

    Bug: When LLM refuses (finish_reason='refusal'), the predictor returns
    reasoning=None and code=None. REPLEntry requires strings, causing
    Pydantic ValidationError.

    Root cause: Anthropic API returns finish_reason='refusal' with content=None
    for queries that trigger safety filters (e.g., biological organism names
    that resemble biosafety concerns).

    Fix: Convert None to descriptive defaults and log the refusal.
    """
    try:
        import dspy.predict.rlm as rlm_module

        original_process = rlm_module.RLM._process_execution_result

        def patched_process(self, action, result, history, output_field_names):
            """Handle None reasoning/code from LLM refusals."""
            reasoning = action.reasoning
            code = action.code

            if reasoning is None and code is None:
                # LLM refused - check if it's a refusal via GLOBAL_HISTORY
                refusal_msg = _detect_refusal()
                if refusal_msg:
                    logger.warning(f"LLM refused query: {refusal_msg}")
                    action._store['reasoning'] = f"LLM REFUSED: {refusal_msg}"
                    action._store['code'] = 'SUBMIT(sparql="", answer="LLM refused to process this query")'
                else:
                    logger.warning("LLM returned None for reasoning and code (possible parsing failure)")
                    action._store['reasoning'] = "LLM returned empty response (parsing failure or refusal)"
                    action._store['code'] = 'SUBMIT(sparql="", answer="LLM returned empty response")'

            elif reasoning is None:
                action._store['reasoning'] = "(no reasoning provided)"

            elif code is None:
                action._store['code'] = 'print("No code generated")'

            return original_process(self, action, result, history, output_field_names)

        rlm_module.RLM._process_execution_result = patched_process
        return True
    except Exception as e:
        print(f"Warning: Could not patch DSPy _process_execution_result: {e}")
        return False


def _detect_refusal() -> str | None:
    """Check GLOBAL_HISTORY for a refusal response."""
    try:
        from dspy.clients.base_lm import GLOBAL_HISTORY
        if not GLOBAL_HISTORY:
            return None

        last_entry = GLOBAL_HISTORY[-1]
        response_str = str(last_entry.get('response', ''))

        if "finish_reason='refusal'" in response_str:
            return "API returned finish_reason='refusal' (safety filter triggered)"

        # Also check for None outputs
        outputs = last_entry.get('outputs', [])
        if outputs and all(o is None for o in outputs):
            if 'refusal' in response_str.lower():
                return "API response contains refusal indicator"
            return "API returned None outputs (possible refusal or parsing failure)"

        return None
    except Exception:
        return None


def apply_all_patches():
    """Apply all DSPy patches."""
    patches_applied = []

    if patch_strip_code_fences():
        patches_applied.append("_strip_code_fences")

    if patch_process_execution_result():
        patches_applied.append("_process_execution_result")

    return patches_applied


# Auto-apply patches on import
_patches = apply_all_patches()
if _patches:
    print(f"Applied DSPy patches: {', '.join(_patches)}")
