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
    thinking: Optional[str] = None,
    verification: Optional[str] = None,
    reflection: Optional[str] = None,
    model: str = "anthropic/claude-3-5-haiku-20241022",
) -> dict:
    """Judge DSPy RLM trajectory for success/failure.

    Uses LLM to assess whether the trajectory successfully answered the query
    with proper grounding in evidence. Incorporates Think-Act-Verify-Reflect
    reasoning fields when available.

    Args:
        task: Original task query
        answer: Final answer from run_dspy_rlm
        trajectory: List of execution steps (code + output)
        evidence: Grounding evidence dict
        thinking: Agent's stated reasoning and discoveries (from THINK phase)
        verification: Agent's verification checks (from VERIFY phase)
        reflection: Agent's self-critique before submission (from REFLECT phase)
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
            result.evidence,
            thinking=result.thinking,
            verification=result.verification,
            reflection=result.reflection
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

    # Format reasoning fields (Think-Act-Verify-Reflect)
    reasoning_text = ""
    if thinking or verification or reflection:
        reasoning_text = "\nAgent's Explicit Reasoning:\n"
        if thinking:
            reasoning_text += f"  THINKING: {thinking[:300]}\n"
        if verification:
            reasoning_text += f"  VERIFICATION: {verification[:300]}\n"
        if reflection:
            reasoning_text += f"  REFLECTION: {reflection[:300]}\n"

    # Judgment prompt - enhanced with reasoning fields
    prompt = f"""Judge this RLM trajectory for success.

Task: {task}

Final Answer: {answer}

Execution Steps:
{steps_text}

Evidence Retrieved:
{evidence_text}
{reasoning_text}
Assess:
1. Does the answer directly address the task?
2. Is the answer grounded in retrieved evidence (URIs, query results)?
3. Did the trajectory explore the ontology meaningfully?
4. If reasoning fields are present, do they show proper verification and reflection?

IMPORTANT: If the agent provides explicit verification showing results match expectations
and reflection confirming evidence quality, weight this heavily toward success.

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


def extract_meta_patterns(
    trajectories: list[dict],
    *,
    min_trajectories: int = 3,
    model: str = "anthropic/claude-3-5-haiku-20241022",
) -> list[MemoryItem]:
    """Extract meta-patterns by analyzing multiple trajectories.

    Identifies cross-trajectory patterns that single-trajectory extraction misses:
    - Common inefficiencies across runs
    - Repeated mistakes (trying same wrong approach)
    - Phase transition patterns (when to stop exploring)
    - Aggregate metrics (iteration counts, tool usage)

    Args:
        trajectories: List of trajectory dicts with structure:
            {
                "task": str,
                "answer": str,
                "trajectory": list[dict],
                "judgment": dict,
                "iterations": int,
                "evidence": dict (optional),
                "ontology_name": str (optional),
            }
        min_trajectories: Minimum trajectories needed for meta-analysis (default: 3)
        model: Model to use for analysis (default: Haiku)

    Returns:
        List of MemoryItem objects with source_type='meta-analysis'

    Example:
        # Collect trajectories
        results = []
        for i in range(5):
            result = run_dspy_rlm("What is Activity?", "prov.ttl")
            judgment = judge_trajectory_dspy(task, result.answer, result.trajectory, result.evidence)
            results.append({
                "task": task,
                "answer": result.answer,
                "trajectory": result.trajectory,
                "judgment": judgment,
                "iterations": len(result.trajectory),
                "evidence": result.evidence,
            })

        # Extract meta-patterns
        meta_patterns = extract_meta_patterns(results)
        for pattern in meta_patterns:
            backend.add_memory(pattern)
    """
    if len(trajectories) < min_trajectories:
        raise ValueError(f"Need at least {min_trajectories} trajectories for meta-analysis, got {len(trajectories)}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY required for meta-analysis")

    import dspy
    import json
    import re

    # Configure model for meta-analysis
    meta_lm = dspy.LM(model, temperature=0.3, max_tokens=1500, cache=False)

    # Get common task (assume all trajectories are same task)
    task = trajectories[0]["task"]

    # Compute aggregate statistics
    iterations = [t["iterations"] for t in trajectories]
    avg_iterations = sum(iterations) / len(iterations)
    min_iterations = min(iterations)
    max_iterations = max(iterations)

    successes = sum(1 for t in trajectories if t["judgment"]["is_success"])
    pass_rate = successes / len(trajectories)

    # Format trajectory summaries (keep concise for context window)
    trajectory_summaries = []
    for i, t in enumerate(trajectories):
        outcome = "PASS" if t["judgment"]["is_success"] else "FAIL"
        reason = t["judgment"].get("reason", "")[:100]

        # Extract key tool usage patterns
        tools_used = {}
        for step in t["trajectory"]:
            code = step.get("code", "")
            # Extract function calls (simple regex)
            calls = re.findall(r'(\w+)\s*\(', code)
            for call in calls:
                tools_used[call] = tools_used.get(call, 0) + 1

        tool_summary = ", ".join([f"{k}:{v}" for k, v in sorted(tools_used.items(), key=lambda x: -x[1])[:5]])

        trajectory_summaries.append(
            f"Trial {i}: {t['iterations']} iters, {outcome}, tools=[{tool_summary}], reason=\"{reason}\""
        )

    trajectory_summaries_text = "\n".join(trajectory_summaries)

    # Tool usage analysis across all trajectories
    all_tools = {}
    for t in trajectories:
        for step in t["trajectory"]:
            code = step.get("code", "")
            calls = re.findall(r'(\w+)\s*\(', code)
            for call in calls:
                all_tools[call] = all_tools.get(call, 0) + 1

    tool_usage_summary = "\n".join([
        f"  - {tool}: {count} calls across {len(trajectories)} trials"
        for tool, count in sorted(all_tools.items(), key=lambda x: -x[1])[:10]
    ])

    # Meta-analysis prompt
    prompt = f"""Analyze these {len(trajectories)} trajectories for the same task and extract meta-patterns.

Task: {task}

Trajectory Summaries:
{trajectory_summaries_text}

Iteration Statistics:
- Average: {avg_iterations:.1f}
- Range: {min_iterations}-{max_iterations}
- Pass rate: {pass_rate:.1%}

Tool Usage Patterns:
{tool_usage_summary}

Identify cross-trajectory patterns (1-3 meta-patterns):

1. **Common Inefficiencies:** What wastes iterations across multiple runs?
   - Example: "All trials make 5-8 exploratory queries after remote connection works"

2. **Repeated Mistakes:** What wrong approaches are tried multiple times?
   - Example: "All trials try property X 2-3 times despite returning 0 results"

3. **Phase Transitions:** When should agent stop exploring and start executing?
   - Example: "First remote query happens at iteration 6; should happen by iteration 3-4"

4. **Meta-Strategies:** High-level guidance not captured in single-run analysis
   - Example: "Stop using describe_entity after remote connectivity validated"

Focus on patterns visible only when comparing multiple runs.
DO NOT just describe what worked - identify what could be IMPROVED across all runs.

Format as JSON array (1-3 meta-patterns):
[
  {{
    "title": "Concise Pattern Name (≤10 words)",
    "description": "Cross-trajectory pattern identified (1 sentence)",
    "content": "1. Pattern description\\n2. When it occurs\\n3. How to avoid/optimize",
    "tags": ["meta-pattern", "efficiency", ...]
  }}
]
"""

    # Get meta-analysis
    with dspy.context(lm=meta_lm):
        response = meta_lm(prompt)

    # Parse JSON response
    if isinstance(response, list):
        response = response[0] if response else ""

    # Extract JSON array from response
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if not json_match:
        return []  # No meta-patterns extracted

    try:
        raw_patterns = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return []

    # Convert to MemoryItem objects
    meta_patterns = []
    created_at = datetime.now(timezone.utc).isoformat()

    for raw in raw_patterns[:3]:  # Limit to 3
        # Validate required fields
        if not raw.get("title") or not raw.get("content"):
            continue

        # Compute stable ID
        memory_id = MemoryItem.compute_id(raw["title"], raw["content"])

        # Build scope (meta-patterns are highly transferable)
        scope = {
            "transferable": True,
            "task_types": ["sparql", "ontology-exploration", "query-construction"]
        }

        # Build provenance
        provenance = {
            "source": "meta-analysis",
            "trajectories_analyzed": len(trajectories),
            "iteration_range": f"{min_iterations}-{max_iterations}",
            "pass_rate": f"{pass_rate:.1%}"
        }

        memory = MemoryItem(
            memory_id=memory_id,
            title=raw["title"],
            description=raw.get("description", ""),
            content=raw["content"],
            source_type="meta-analysis",
            task_query=task,
            created_at=created_at,
            tags=raw.get("tags", []) + ["meta-pattern"],  # Always add meta-pattern tag
            scope=scope,
            provenance=provenance,
            access_count=0,
            success_count=0,
            failure_count=0,
        )

        meta_patterns.append(memory)

    return meta_patterns
