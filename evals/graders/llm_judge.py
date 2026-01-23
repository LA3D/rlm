"""LLM-as-judge grader - uses LLM to evaluate semantic correctness.

Following Anthropic guidance: Use LLM judge for semantic evaluation where
code-based grading is insufficient, but provide structured rubrics.
"""

import json
from typing import Optional
from .base import BaseGrader, GradeResult


class LLMJudgeGrader(BaseGrader):
    """Use LLM to judge semantic correctness of agent's answer and approach.

    This grader handles cases where:
    - Multiple valid approaches exist (e.g., rdfs:subClassOf vs rdfs:subClassOf+)
    - Semantic equivalence is complex to verify programmatically
    - Answer quality/completeness needs evaluation

    Uses Haiku by default for cost efficiency.
    """

    grader_type: str = "llm_judge"

    def __init__(
        self,
        model: str = "anthropic/claude-3-5-haiku-20241022",
        use_exemplar_patterns: bool = True,
        rubric: Optional[str] = None,
        strict: bool = False
    ):
        """Initialize LLM judge grader.

        Args:
            model: LLM model to use (default: Haiku for cost efficiency)
            use_exemplar_patterns: Whether to include exemplar patterns in judgment
            rubric: Optional custom rubric for evaluation
            strict: If True, requires exact match to exemplar approach
        """
        self.model = model
        self.use_exemplar_patterns = use_exemplar_patterns
        self.rubric = rubric
        self.strict = strict

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade using LLM judgment.

        Args:
            transcript: Execution transcript with SPARQL and results
            answer: Final answer from agent
            task: Task definition with query and optional exemplar_patterns

        Returns:
            GradeResult with LLM's judgment
        """
        if not answer or not isinstance(answer, str) or answer.strip() == "":
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No answer provided",
                details={"llm_judgment": None}
            )

        # Extract SPARQL and evidence
        sparql = self._extract_sparql(transcript)
        evidence = self._extract_evidence(transcript)

        if not sparql:
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No SPARQL query found to evaluate",
                details={"llm_judgment": None}
            )

        # Build judgment prompt
        task_query = task.get("query", "") if task else ""
        exemplar_patterns = task.get("exemplar_patterns", []) if task and self.use_exemplar_patterns else []

        prompt = self._build_judgment_prompt(
            task_query=task_query,
            agent_sparql=sparql,
            agent_answer=answer,
            evidence=evidence,
            exemplar_patterns=exemplar_patterns
        )

        # Call LLM for judgment
        try:
            judgment = self._call_llm(prompt)

            # Parse judgment
            passed = judgment.get("correct", False)
            confidence = judgment.get("confidence", 0.0)
            reasoning = judgment.get("reasoning", "No reasoning provided")

            return GradeResult(
                passed=passed,
                score=confidence,
                reason=f"LLM Judge: {reasoning}",
                details={
                    "llm_judgment": judgment,
                    "model": self.model
                }
            )

        except Exception as e:
            # If LLM call fails, don't block the eval
            return GradeResult(
                passed=True,  # Default to pass on LLM error
                score=0.5,
                reason=f"LLM judge failed: {str(e)}",
                details={"error": str(e)}
            )

    def _build_judgment_prompt(
        self,
        task_query: str,
        agent_sparql: str,
        agent_answer: str,
        evidence: dict,
        exemplar_patterns: list[str]
    ) -> str:
        """Build structured prompt for LLM judgment."""

        prompt_parts = [
            "You are evaluating whether an agent correctly solved a SPARQL query task.",
            "",
            "## Task",
            f"Query: {task_query}",
            ""
        ]

        # Include exemplar patterns if available
        if exemplar_patterns:
            prompt_parts.extend([
                "## Expected Patterns (from exemplar)",
                "These show what a reference query typically uses, but alternative approaches may be valid:",
                ""
            ])
            for pattern in exemplar_patterns:
                prompt_parts.append(f"- {pattern}")
            prompt_parts.append("")

        # Agent's approach
        prompt_parts.extend([
            "## Agent's SPARQL Query",
            "```sparql",
            agent_sparql,
            "```",
            "",
            "## Agent's Answer",
            agent_answer,
            ""
        ])

        # Evidence (sample results)
        if evidence:
            prompt_parts.extend([
                "## Evidence (Agent's Results)",
                "```json",
                json.dumps(evidence, indent=2)[:1000],  # Truncate to avoid token limits
                "```",
                ""
            ])

        # Judgment rubric
        if self.rubric:
            prompt_parts.extend([
                "## Evaluation Rubric",
                self.rubric,
                ""
            ])
        else:
            if self.strict:
                rubric_text = """
## Evaluation Rubric

Evaluate whether the agent's approach matches the expected patterns:
1. Does the SPARQL query use the expected patterns?
2. Are there any deviations from the exemplar approach?
3. If there are deviations, are they acceptable variations?

Return a JSON object with:
{
  "correct": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of judgment"
}
"""
            else:
                rubric_text = """
## Evaluation Rubric

Evaluate whether the agent correctly solved the task:

1. **Semantic Correctness**: Does the SPARQL query correctly address the task?
2. **Result Quality**: Do the results match what was asked for?
3. **Approach Validity**: Is the approach valid, even if different from exemplar?

Consider:
- Multiple valid approaches may exist (e.g., rdfs:subClassOf vs rdfs:subClassOf+)
- The query should return correct results, not necessarily use exact patterns
- Variations are acceptable if they achieve the same outcome

Return a JSON object with:
{
  "correct": true/false,
  "confidence": 0.0-1.0 (how confident are you?),
  "reasoning": "Brief explanation (1-2 sentences)"
}

IMPORTANT: Be lenient with alternative valid approaches. Focus on whether results are correct, not whether the exact exemplar pattern was followed.
"""
            prompt_parts.extend([rubric_text, ""])

        prompt_parts.append("Provide your judgment as JSON only (no markdown, no explanation):")

        return "\n".join(prompt_parts)

    def _call_llm(self, prompt: str) -> dict:
        """Call LLM to get judgment.

        Returns:
            dict with keys: correct (bool), confidence (float), reasoning (str)
        """
        import os
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)

        # Extract model name (remove 'anthropic/' prefix if present)
        model_name = self.model.replace("anthropic/", "")

        response = client.messages.create(
            model=model_name,
            max_tokens=500,
            temperature=0.0,  # Deterministic for eval consistency
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = response.content[0].text.strip()

        # Try to parse as JSON
        try:
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first and last lines (```json and ```)
                response_text = "\n".join(lines[1:-1])

            judgment = json.loads(response_text)

            # Validate structure
            if "correct" not in judgment or "confidence" not in judgment or "reasoning" not in judgment:
                raise ValueError("Invalid judgment structure")

            return judgment

        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: try to extract from text
            if "correct" in response_text.lower() and "true" in response_text.lower():
                return {
                    "correct": True,
                    "confidence": 0.7,
                    "reasoning": response_text[:200]
                }
            elif "correct" in response_text.lower() and "false" in response_text.lower():
                return {
                    "correct": False,
                    "confidence": 0.7,
                    "reasoning": response_text[:200]
                }
            else:
                raise ValueError(f"Could not parse LLM response: {response_text[:100]}")

    def _extract_sparql(self, transcript: list) -> str:
        """Extract SPARQL query from transcript.

        IMPORTANT: Prioritizes final SPARQL from SUBMIT over exploratory queries.
        DSPy RLM stores final SPARQL in a dedicated item with 'sparql' field,
        while exploratory code may contain embedded SPARQL strings.
        """
        # FIRST: Check ALL items for direct sparql field (final SUBMIT result)
        # This ensures we get the final query, not exploratory ones
        for item in transcript:
            if isinstance(item, dict):
                if "sparql" in item and item["sparql"]:
                    return item["sparql"]

        # SECOND: If no direct sparql field, check for top-level code fields
        for item in transcript:
            if isinstance(item, dict):
                if "code" in item and item["code"]:
                    code = item["code"]
                    if any(kw in code.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                        return code

        # THIRD: Fall back to code_blocks (may contain exploratory queries)
        for item in transcript:
            if isinstance(item, dict):
                if "code_blocks" in item:
                    for block in item["code_blocks"]:
                        if isinstance(block, dict) and "code" in block:
                            code = block["code"]
                            if any(kw in code.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                                return code

        # FOURTH: Final fallback using helper
        code_blocks = self._extract_code_blocks(transcript)
        for code in code_blocks:
            if any(kw in code.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                return code
        return ""

    def _extract_evidence(self, transcript: list) -> dict:
        """Extract evidence dict from transcript.

        Checks both direct evidence field and nested in items.
        """
        # Check if transcript items have evidence directly
        for item in transcript:
            if isinstance(item, dict):
                if "evidence" in item and item["evidence"]:
                    return item["evidence"]
        return {}

    @classmethod
    def from_config(cls, config: dict) -> 'LLMJudgeGrader':
        """Create from YAML config."""
        return cls(
            model=config.get("model", "anthropic/claude-3-5-haiku-20241022"),
            use_exemplar_patterns=config.get("use_exemplar_patterns", True),
            rubric=config.get("rubric"),
            strict=config.get("strict", False)
        )
