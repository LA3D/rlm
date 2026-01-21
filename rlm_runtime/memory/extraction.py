"""Memory extraction from DSPy RLM trajectories.

Provides judgment and memory extraction for DSPy RLM results,
compatible with the new MemoryItem schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import os

from .backend import MemoryItem


def format_memories_for_context(memories: list[MemoryItem]) -> str:
    """Format retrieved memories for injection into RLM context.

    Args:
        memories: List of MemoryItem objects

    Returns:
        Formatted markdown string for context injection

    Example:
        memories = backend.retrieve("how to find entities", k=3)
        context = format_memories_for_context(memories)
        # Inject into RLM context
    """
    if not memories:
        return ""

    lines = ["## Retrieved Procedural Memories\n"]
    lines.append("The following strategies have been successful in similar tasks:\n")

    for i, mem in enumerate(memories, 1):
        lines.append(f"\n### {i}. {mem.title}")
        lines.append(f"*{mem.description}*")
        lines.append(f"\n{mem.content}\n")

        # Add tags if present
        if mem.tags:
            tags_str = ", ".join(mem.tags)
            lines.append(f"*Tags: {tags_str}*\n")

    return "\n".join(lines)


def judge_trajectory_dspy(
    task: str,
    answer: str,
    trajectory: list[dict],
    evidence: dict,
    *,
    model: str = "anthropic/claude-3-5-haiku-20241022",
) -> dict:
    """Judge DSPy RLM trajectory for success/failure.

    Uses LLM to assess whether the trajectory successfully answered the query
    with proper grounding in evidence.

    Args:
        task: Original task query
        answer: Final answer from run_dspy_rlm
        trajectory: List of execution steps (code + output)
        evidence: Grounding evidence dict
        model: Model to use for judgment (default: Haiku)

    Returns:
        Dict with keys:
            - is_success: bool - Whether trajectory succeeded
            - reason: str - Explanation of judgment
            - confidence: str - 'high', 'medium', or 'low'
            - missing: list[str] - Missing evidence/requirements if failure

    Example:
        result = run_dspy_rlm("What is Activity?", "prov.ttl")
        judgment = judge_trajectory_dspy(
            "What is Activity?",
            result.answer,
            result.trajectory,
            result.evidence
        )
        if judgment["is_success"]:
            print("Success!")
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY required for judgment")

    import dspy

    # Configure model for judgment
    judge_lm = dspy.LM(model, temperature=0.0, max_tokens=800, cache=False)

    # Format trajectory for prompt
    steps_text = ""
    for i, step in enumerate(trajectory, 1):
        code = step.get("code", "")
        output = str(step.get("output", ""))[:200]  # Limit output length
        if code:
            steps_text += f"{i}. Code: {code[:100]}... → Output: {output}\n"

    # Format evidence
    evidence_text = ""
    if evidence:
        for key, value in evidence.items():
            evidence_text += f"  - {key}: {str(value)[:100]}\n"

    # Judgment prompt
    prompt = f"""Judge this RLM trajectory for success.

Task: {task}

Final Answer: {answer}

Execution Steps:
{steps_text}

Evidence Retrieved:
{evidence_text}

Assess:
1. Does the answer directly address the task?
2. Is the answer grounded in retrieved evidence (URIs, query results)?
3. Did the trajectory explore the ontology meaningfully?

Respond in JSON:
{{
    "is_success": true/false,
    "reason": "brief explanation",
    "confidence": "high/medium/low",
    "missing": ["what was missing if failure"]
}}
"""

    # Get judgment
    with dspy.context(lm=judge_lm):
        response = judge_lm(prompt)

    # Parse JSON response
    import json
    import re

    # DSPy LM returns a list of completions, take the first one
    if isinstance(response, list):
        response = response[0] if response else ""

    # Extract JSON from response (may have markdown code blocks)
    json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
    if json_match:
        try:
            judgment = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            # Fallback: conservative failure
            judgment = {
                "is_success": False,
                "reason": "Could not parse judgment",
                "confidence": "low",
                "missing": ["valid judgment"]
            }
    else:
        judgment = {
            "is_success": False,
            "reason": "No JSON in response",
            "confidence": "low",
            "missing": ["structured response"]
        }

    # Ensure required keys
    judgment.setdefault("is_success", False)
    judgment.setdefault("reason", "Unknown")
    judgment.setdefault("confidence", "low")
    judgment.setdefault("missing", [])

    return judgment


def extract_memories_dspy(
    task: str,
    answer: str,
    trajectory: list[dict],
    judgment: dict,
    *,
    ontology_name: Optional[str] = None,
    run_id: Optional[str] = None,
    trajectory_id: Optional[str] = None,
    model: str = "anthropic/claude-3-5-haiku-20241022",
) -> list[MemoryItem]:
    """Extract procedural memories from DSPy RLM trajectory.

    Uses LLM to extract 1-3 reusable procedural memories from the trajectory.

    Args:
        task: Original task query
        answer: Final answer
        trajectory: List of execution steps
        judgment: Judgment dict from judge_trajectory_dspy
        ontology_name: Name of ontology (for scope metadata)
        run_id: Run ID for provenance
        trajectory_id: Trajectory ID for provenance
        model: Model to use for extraction (default: Haiku)

    Returns:
        List of MemoryItem objects (0-3 items)

    Example:
        result = run_dspy_rlm("What is Activity?", "prov.ttl")
        judgment = judge_trajectory_dspy(task, result.answer, result.trajectory, result.evidence)
        memories = extract_memories_dspy(
            task, result.answer, result.trajectory, judgment,
            ontology_name="prov", run_id="r-001", trajectory_id="t-001"
        )
        for mem in memories:
            backend.add_memory(mem)
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY required for extraction")

    import dspy

    source_type = "success" if judgment["is_success"] else "failure"

    # Configure model for extraction
    extract_lm = dspy.LM(model, temperature=0.3, max_tokens=1200, cache=False)

    # Format trajectory
    steps_text = ""
    for i, step in enumerate(trajectory, 1):
        code = step.get("code", "")
        output = str(step.get("output", ""))[:150]
        if code:
            steps_text += f"{i}. {code[:80]}... → {output}\n"

    # Extraction prompt
    prompt = f"""Extract 1-3 reusable procedural memories from this RLM trajectory.

Task: {task}
Answer: {answer}
Outcome: {"Success" if judgment['is_success'] else "Failure"}
Reason: {judgment['reason']}

Execution Steps:
{steps_text}

Extract procedures as:
1. **Title** (≤10 words): Concise identifier
2. **Description** (1 sentence): What this strategy does
3. **Content** (Markdown checklist): Reusable steps
4. **Tags** (3-5 keywords): For retrieval

Format as JSON array (1-3 items):
[
  {{
    "title": "...",
    "description": "...",
    "content": "1. Step one\\n2. Step two\\n...",
    "tags": ["tag1", "tag2", ...]
  }}
]

Focus on:
- Generalizable patterns (not task-specific details)
- Tool usage strategies
- Error handling if failure
"""

    # Get extraction
    with dspy.context(lm=extract_lm):
        response = extract_lm(prompt)

    # Parse JSON response
    import json
    import re

    # DSPy LM returns a list of completions, take the first one
    if isinstance(response, list):
        response = response[0] if response else ""

    # Extract JSON array from response
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if not json_match:
        return []  # No memories extracted

    try:
        raw_memories = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return []

    # Convert to MemoryItem objects
    memories = []
    created_at = datetime.now(timezone.utc).isoformat()

    for raw in raw_memories[:3]:  # Limit to 3
        # Validate required fields
        if not raw.get("title") or not raw.get("content"):
            continue

        # Compute stable ID
        memory_id = MemoryItem.compute_id(raw["title"], raw["content"])

        # Build scope
        scope = {}
        if ontology_name:
            scope["ontology"] = ontology_name

        # Build provenance
        provenance = {}
        if run_id:
            provenance["run_id"] = run_id
        if trajectory_id:
            provenance["trajectory_id"] = trajectory_id

        memory = MemoryItem(
            memory_id=memory_id,
            title=raw["title"],
            description=raw.get("description", ""),
            content=raw["content"],
            source_type=source_type,
            task_query=task,
            created_at=created_at,
            tags=raw.get("tags", []),
            scope=scope,
            provenance=provenance,
            access_count=0,
            success_count=0,
            failure_count=0,
        )

        memories.append(memory)

    return memories
