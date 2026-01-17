"""Test demonstrating the value of FINAL_VAR as an executable function."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*80)
print("DEMONSTRATION: FINAL_VAR as executable function vs text pattern")
print("="*80)
print()

print("Current behavior (FINAL_VAR is only a text pattern):")
print("-" * 80)
print("""
The model must:
1. Create the variable
2. Hope it exists when they write FINAL_VAR(x) outside code blocks
3. No way to test/verify before committing

Example hallucination scenario:
- Iteration 1: Model says "I'll create math_answer" but forgets to put it in code
- Iteration 2: Model writes FINAL_VAR(math_answer) but variable doesn't exist
- Iteration 3: Still confused, tries again
- Iteration 4: Finally creates the variable
- Iteration 5: FINAL_VAR works

This happened in test_llm_query_final_var.py (took 6 iterations)
""")
print()

print("Proposed behavior (FINAL_VAR as executable function):")
print("-" * 80)
print("""
The model can:
1. Call FINAL_VAR(x) inside code blocks to test if variable exists
2. Get deterministic error: "Error: Variable 'x' not found"
3. Preview the answer before committing
4. More explicit debugging flow

Example with function:
```repl
# Check if answer is ready
preview = FINAL_VAR(math_answer)
if "Error" in preview:
    print("Variable doesn't exist, creating it...")
    math_answer = llm_query("What is 2+2?")
else:
    print(f"Answer ready: {preview}")
```

Then outside code block:
FINAL_VAR(math_answer)

This is more deterministic and less prone to hallucination!
""")
print()

print("="*80)
print("DECISION POINT")
print("="*80)
print("""
Should we add FINAL_VAR as an executable function to our namespace?

Pros:
+ Model can test/verify variables exist
+ Deterministic errors instead of silent failures
+ Can preview answers before committing
+ Matches rlmpaper's design

Cons:
- Adds another function to the namespace
- Model might get confused about when to call vs when to signal
- Currently works (test_progressive_disclosure_minimal.py passed)

Your call!
""")
