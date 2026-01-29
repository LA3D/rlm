#!/usr/bin/env python3
"""Simple test to encourage llm_query delegation.

Uses a task where semantic analysis is clearly beneficial:
- Disambiguating similar items
- Validating choices
- Filtering by relevance

This should trigger llm_query usage if the model understands delegation.

Usage:
    source ~/uvws/.venv/bin/activate
    python test_delegation_simple.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_delegation_encouraged():
    """Test designed to encourage llm_query usage."""

    print("=" * 70)
    print("DELEGATION TEST: Simple Semantic Task")
    print("=" * 70)

    # Check environment
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set")
        return 1

    import dspy
    from dspy import RLM

    # Simple task: Find the most relevant programming language for a task
    # This SHOULD trigger llm_query usage because:
    # 1. Requires semantic judgment (which is "best"?)
    # 2. Explicit suggestion to use llm_query
    # 3. Data is small (no need for complex queries)

    task_description = """
You have a list of programming languages and need to find the BEST one for building a web API.

Languages available:
- Python: "General-purpose language, great for scripting, data science, web development"
- JavaScript: "Web-focused language, runs in browsers and Node.js, async-first"
- Rust: "Systems programming language, memory-safe, high performance"
- SQL: "Database query language, not general-purpose"
- Bash: "Shell scripting language, system automation"

IMPORTANT: Use llm_query() to help analyze which language is most suitable.

Example approach:
1. Print the list of languages
2. Use llm_query("Which of these languages is BEST for building web APIs?", context=languages)
3. Return your final choice with reasoning

Remember: llm_query() is available for semantic analysis!
"""

    languages = {
        "Python": "General-purpose language, great for scripting, data science, web development",
        "JavaScript": "Web-focused language, runs in browsers and Node.js, async-first",
        "Rust": "Systems programming language, memory-safe, high performance",
        "SQL": "Database query language, not general-purpose",
        "Bash": "Shell scripting language, system automation"
    }

    print("\nTask: Find best language for web API")
    print("Context includes explicit llm_query guidance")
    print("\n" + "─" * 70)
    print("EXECUTING...")
    print("─" * 70 + "\n")

    # Configure DSPy
    dspy.configure(
        lm=dspy.LM("anthropic/claude-sonnet-4-5-20250929", temperature=0.2, max_tokens=2048),
    )
    sub_lm = dspy.LM("anthropic/claude-3-5-haiku-20241022", temperature=0.2, max_tokens=1024)

    # Define signature
    class LanguageSelection(dspy.Signature):
        """Select best programming language for a task."""
        task_description: str = dspy.InputField()
        languages: dict = dspy.InputField()
        choice: str = dspy.OutputField(desc="Selected language name")
        reasoning: str = dspy.OutputField(desc="Why this language is best")
        used_llm_query: bool = dspy.OutputField(desc="Did you use llm_query for analysis?")

    # Create RLM
    rlm = RLM(
        LanguageSelection,
        max_iterations=5,
        max_llm_calls=10,
        verbose=True,
        sub_lm=sub_lm,
    )

    # Execute
    try:
        import time
        start = time.time()

        result = rlm(
            task_description=task_description,
            languages=languages
        )

        elapsed = time.time() - start

        print("\n" + "─" * 70)
        print("RESULTS")
        print("─" * 70)
        print(f"Time: {elapsed:.1f}s")
        print(f"Choice: {result.choice}")
        print(f"Used llm_query: {result.used_llm_query}")
        print(f"\nReasoning:")
        print(f"  {result.reasoning}")

        # Check trajectory
        trajectory = getattr(result, "trajectory", [])
        llm_query_count = 0

        print(f"\n" + "─" * 70)
        print("TRAJECTORY ANALYSIS")
        print("─" * 70)
        print(f"Total iterations: {len(trajectory)}")

        for i, step in enumerate(trajectory, 1):
            code = getattr(step, "code", "")
            if "llm_query" in code:
                llm_query_count += 1
                print(f"\n✅ Iteration {i}: Found llm_query call!")
                # Show the line
                for line in code.split("\n"):
                    if "llm_query" in line:
                        print(f"   → {line.strip()}")

        print(f"\n{'─' * 70}")
        if llm_query_count > 0:
            print(f"✅ SUCCESS: llm_query used {llm_query_count} times!")
            print("   → Strategic delegation is working!")
        else:
            print(f"⚪ llm_query NOT used")
            print("   → Model solved directly without delegation")
            print("   → This task may be too simple, or model prefers direct solution")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def test_delegation_with_validation():
    """Another test: explicit validation task (should definitely use llm_query)."""

    print("\n\n" + "=" * 70)
    print("DELEGATION TEST: Validation Task")
    print("=" * 70)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set")
        return 1

    import dspy
    from dspy import RLM

    task = """
You need to validate if a given email address looks legitimate or suspicious.

Email to check: "admin@paypal-security-verify.com"

IMPORTANT: Use llm_query() to help analyze if this email domain is suspicious.

Approach:
1. Look at the email domain: "paypal-security-verify.com"
2. Use llm_query("Is the domain 'paypal-security-verify.com' a legitimate PayPal domain or likely phishing?")
3. Return your verdict

Remember: llm_query() is available for semantic analysis!
"""

    print("\nTask: Validate email address")
    print("This REQUIRES semantic judgment (phishing detection)")
    print("\n" + "─" * 70)
    print("EXECUTING...")
    print("─" * 70 + "\n")

    dspy.configure(
        lm=dspy.LM("anthropic/claude-sonnet-4-5-20250929", temperature=0.2, max_tokens=2048),
    )
    sub_lm = dspy.LM("anthropic/claude-3-5-haiku-20241022", temperature=0.2, max_tokens=1024)

    class EmailValidation(dspy.Signature):
        """Validate if email is legitimate or suspicious."""
        task: str = dspy.InputField()
        verdict: str = dspy.OutputField(desc="'legitimate' or 'suspicious'")
        reasoning: str = dspy.OutputField(desc="Why")
        used_delegation: bool = dspy.OutputField(desc="Used llm_query?")

    rlm = RLM(
        EmailValidation,
        max_iterations=4,
        max_llm_calls=8,
        verbose=True,
        sub_lm=sub_lm,
    )

    try:
        import time
        start = time.time()

        result = rlm(task=task)

        elapsed = time.time() - start

        print("\n" + "─" * 70)
        print("RESULTS")
        print("─" * 70)
        print(f"Time: {elapsed:.1f}s")
        print(f"Verdict: {result.verdict}")
        print(f"Used delegation: {result.used_delegation}")
        print(f"\nReasoning:")
        print(f"  {result.reasoning}")

        # Check trajectory
        trajectory = getattr(result, "trajectory", [])
        llm_query_count = 0

        for step in trajectory:
            code = getattr(step, "code", "")
            if "llm_query" in code:
                llm_query_count += 1

        print(f"\n{'─' * 70}")
        if llm_query_count > 0:
            print(f"✅ SUCCESS: llm_query used {llm_query_count} times!")
        else:
            print(f"⚪ llm_query NOT used")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Run delegation tests."""
    print("\n" + "=" * 70)
    print("TESTING llm_query DELEGATION WITH SIMPLE TASKS")
    print("=" * 70)
    print("\nThese tasks are designed to ENCOURAGE delegation:")
    print("  1. Explicit instructions to use llm_query")
    print("  2. Tasks requiring semantic judgment")
    print("  3. Small data (no complex queries needed)")
    print("\nIf llm_query is still not used, it confirms model needs")
    print("more than just prompting (e.g., training, exemplars).")

    # Test 1: Language selection
    result1 = test_delegation_encouraged()

    # Test 2: Validation task
    result2 = test_delegation_with_validation()

    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    if result1 == 0 and result2 == 0:
        print("\n✅ Both tests completed successfully")
        print("\nCheck above to see if llm_query was actually used.")
        print("If not used, this confirms delegation needs:")
        print("  - Training (RL)")
        print("  - Exemplars (memory with delegation patterns)")
        print("  - Task complexity (may emerge on harder tasks)")
    else:
        print("\n⚠️ Some tests had errors")

    return max(result1, result2)


if __name__ == "__main__":
    sys.exit(main())
