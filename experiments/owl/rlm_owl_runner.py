"""Minimal DSPy RLM runner with strict symbolic prompt + Owlready2 memory."""

from __future__ import annotations

import os
from dataclasses import dataclass

import dspy

from experiments.owl.tools import OwlRLMToolset


@dataclass
class OwlRLMResult:
    answer: str
    prompt_ref: dict
    memory_stats: dict


def _ensure_lm(model: str = "anthropic/claude-sonnet-4-5-20250929") -> None:
    if hasattr(dspy.settings, "lm") and dspy.settings.lm is not None:
        return
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")
    dspy.configure(lm=dspy.LM(model, api_key=api_key, temperature=0.0))


def build_symbolic_context(prompt_ref: dict) -> str:
    return (
        "You are operating in strict symbolic mode.\n"
        "Rules:\n"
        "1) The user prompt P is an environment object. Do not assume full prompt text in context.\n"
        "2) Use prompt_* tools to inspect P with bounded windows only.\n"
        "3) Use recursive code and llm_query/llm_query_batched in loops when needed.\n"
        "4) Keep tool/subcall outputs in variables; avoid printing large payloads.\n"
        "5) You must call SUBMIT(answer=...) at the end.\n"
        f"Prompt handle metadata: {prompt_ref}\n"
    )


def run_symbolic_owl_rlm(user_prompt: str, task: str) -> OwlRLMResult:
    _ensure_lm()
    toolset = OwlRLMToolset(prompt_text=user_prompt)
    ctx = build_symbolic_context(toolset.prompt_ref.to_dict())

    # Optional seed memory, stored symbolically.
    toolset.memory_add(
        kind="principle",
        title="Bounded Prompt Reads",
        summary="Read prompt in small windows; never dump full prompt",
        content=(
            "Inspect prompt via prompt_stats + prompt_read_window. "
            "Do not attempt broad prompt extraction."
        ),
        tags=["rlm", "symbolic", "safety"],
    )

    rlm = dspy.RLM(
        "context, task -> answer",
        max_iterations=12,
        max_llm_calls=40,
        max_output_chars=10000,
        tools=toolset.as_tools(),
    )

    out = rlm(context=ctx, task=task)
    return OwlRLMResult(
        answer=str(getattr(out, "answer", "")),
        prompt_ref=toolset.prompt_ref.to_dict(),
        memory_stats=toolset.memory_stats(),
    )


if __name__ == "__main__":
    demo_prompt = (
        "User asks for structured extraction of entities and constraints from a long biological prompt. "
        "The response must include a compact plan and a final summary."
    )
    demo_task = "Produce a concise answer plan from P while following strict symbolic rules."
    result = run_symbolic_owl_rlm(demo_prompt, demo_task)
    print("Prompt ref:", result.prompt_ref)
    print("Memory stats:", result.memory_stats)
    print("Answer:", result.answer[:500])
