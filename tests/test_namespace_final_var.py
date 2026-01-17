"""Targeted tests for namespace handling and FINAL_VAR lookup."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm._rlmpaper_compat import find_final_answer

print("="*80)
print("TEST 1: Basic FINAL_VAR pattern matching")
print("="*80)

# Test basic pattern recognition
response = "I have the answer.\n\nFINAL_VAR(my_answer)"
ns = {'my_answer': 'The answer is 42'}

result = find_final_answer(response, ns=ns)
print(f"Response: {response}")
print(f"Namespace: {ns}")
print(f"Result: {result}")
print(f"Expected: 'The answer is 42'")
print(f"PASS: {result == 'The answer is 42'}")
print()

print("="*80)
print("TEST 2: FINAL_VAR with variable not in namespace")
print("="*80)

response = "I have the answer.\n\nFINAL_VAR(missing_var)"
ns = {'my_answer': 'The answer is 42'}

result = find_final_answer(response, ns=ns)
print(f"Response: {response}")
print(f"Namespace: {ns}")
print(f"Result: {result}")
print(f"Expected: None (variable doesn't exist)")
print(f"PASS: {result is None}")
print()

print("="*80)
print("TEST 3: FINAL_VAR with whitespace variations")
print("="*80)

test_cases = [
    ("FINAL_VAR(my_var)", "should work"),
    ("FINAL_VAR( my_var )", "should work with spaces"),
    ("FINAL_VAR(my_var) ", "should work with trailing space"),
    (" FINAL_VAR(my_var)", "should work with leading space"),
    ("  FINAL_VAR(my_var)", "should work with multiple leading spaces"),
]

for pattern, description in test_cases:
    response = f"Here's the answer.\n\n{pattern}"
    ns = {'my_var': 'Success!'}
    result = find_final_answer(response, ns=ns)
    print(f"{description:40} | Pattern: '{pattern:20}' | Result: {result}")
print()

print("="*80)
print("TEST 4: FINAL_VAR with quotes (common mistake)")
print("="*80)

# Model might add quotes around variable name
response = "FINAL_VAR('my_answer')"
ns = {'my_answer': 'The answer is 42'}

result = find_final_answer(response, ns=ns)
print(f"Response with single quotes: {response}")
print(f"Result: {result}")
print(f"Expected: 'The answer is 42' (quotes should be stripped)")
print(f"PASS: {result == 'The answer is 42'}")
print()

response = 'FINAL_VAR("my_answer")'
result = find_final_answer(response, ns=ns)
print(f"Response with double quotes: {response}")
print(f"Result: {result}")
print(f"Expected: 'The answer is 42' (quotes should be stripped)")
print(f"PASS: {result == 'The answer is 42'}")
print()

print("="*80)
print("TEST 5: FINAL() pattern (direct answer)")
print("="*80)

response = "FINAL(This is the direct answer)"
result = find_final_answer(response, ns={})
print(f"Response: {response}")
print(f"Result: {result}")
print(f"Expected: 'This is the direct answer'")
print(f"PASS: {result == 'This is the direct answer'}")
print()

print("="*80)
print("TEST 6: Check if FINAL must be at start of line")
print("="*80)

test_cases = [
    ("FINAL_VAR(x)", "at start of line", True),
    ("Some text FINAL_VAR(x)", "not at start of line", False),
    ("  FINAL_VAR(x)", "indented", True),
    ("\n\nFINAL_VAR(x)", "after newlines", True),
]

ns = {'x': 'found'}
for pattern, description, should_find in test_cases:
    result = find_final_answer(pattern, ns=ns)
    found = result is not None
    status = "✓" if found == should_find else "✗"
    print(f"{status} {description:25} | Found: {found:5} | Expected: {should_find}")
print()

print("="*80)
print("TEST 7: Complex multiline response like actual RLM iteration")
print("="*80)

response = """Perfect! I have successfully gathered all the information about the influence-related classes in the PROV ontology and analyzed their relationships. The analysis is comprehensive and answers the original query completely.

FINAL_VAR(final_answer)"""

ns = {
    'final_answer': 'This is a long comprehensive answer about influence classes...',
    'llm_res': 'Some other content',
    'analysis_prompt': 'The prompt used'
}

result = find_final_answer(response, ns=ns)
print(f"Response:\n{response}\n")
print(f"Namespace keys: {list(ns.keys())}")
print(f"Result: {result}")
print(f"Expected: 'This is a long comprehensive answer...'")
print(f"PASS: {result == ns['final_answer']}")
print()
