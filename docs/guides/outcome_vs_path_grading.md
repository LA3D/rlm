# Outcome vs Path Grading: Following Anthropic Best Practices

Following Anthropic's guidance: **"Grade outcomes, not paths. It's often better to grade what the agent produced, not the path it took."**

## The Problem: Brittle Path-Based Grading

### ❌ Bad Example: `evidence_pattern` grader

```yaml
graders:
  - type: evidence_pattern
    required:
      - function: "rdfs:subClassOf taxon:2"  # ← Too specific!
```

**What happens:**
- Agent uses `rdfs:subClassOf+ taxon:2` (transitive closure)
- Gets correct results: Cellvibrio, Ancylobacter aquaticus (real bacteria) ✓
- But fails grading because pattern doesn't match exactly ✗

**Why this is bad:**
> "Avoid the instinct to check that agents followed very specific steps... This creates overly brittle tests." - Anthropic

## The Solution: Outcome-Based Grading

### ✅ Good Example: `outcome_verification` grader

```yaml
graders:
  - type: outcome_verification
    result_type: "present"
    min_results: 5
    required_fields: ["taxon", "scientificName"]
    verification_patterns:
      - field: "taxon"
        pattern: "taxonomy/"
        matches: "all"  # All results must be taxonomy URIs
```

**What happens:**
- Agent uses `rdfs:subClassOf+` OR `rdfs:subClassOf` OR any valid approach
- Grader checks: "Are these actually bacterial taxonomy URIs?" ✓
- Pass/fail based on actual outcomes, not execution path

## Real-World Example: UniProt Bacterial Taxa

### Before (Path-Based):

```yaml
task:
  id: "uniprot_bacteria_taxa_001"
  query: "Select all bacterial taxa and their scientific name from UniProt taxonomy."

  graders:
    - type: evidence_pattern
      required:
        - function: "PREFIX taxon:"
        - function: "PREFIX up:"
        - function: "up:scientificName"
        - function: "rdfs:subClassOf taxon:2"  # ← FAILS on rdfs:subClassOf+
```

**Problem:** Agent got correct bacteria but used transitive closure (`rdfs:subClassOf+`), which is actually MORE robust!

### After (Outcome-Based):

```yaml
task:
  id: "uniprot_bacteria_taxa_001"
  query: "Select all bacterial taxa and their scientific name from UniProt taxonomy."

  graders:
    - type: convergence
      max_iterations: 8

    - type: outcome_verification
      result_type: "present"
      min_results: 5
      required_fields: ["taxon", "scientificName"]
      verification_patterns:
        # Verify results ARE bacteria (taxonomy URIs)
        - field: "taxon"
          pattern: "purl.uniprot.org/taxonomy/"
          matches: "all"
        # Verify they have scientific names
        - field: "scientificName"
          pattern: ".+"
          matches: "all"

    - type: tool_called
      required: ["sparql_query"]
```

**Benefits:**
- ✅ Accepts `rdfs:subClassOf`, `rdfs:subClassOf+`, or any valid SPARQL
- ✅ Verifies actual results are taxonomy URIs
- ✅ Checks required fields present
- ✅ Allows agent creativity in approach

## When to Use Each Grader Type

### Use Code-Based Graders (`outcome_verification`):
- ✅ Verify results contain expected data types
- ✅ Check required fields present
- ✅ Validate URI patterns, counts, ranges
- ✅ Test state changes (database records, file existence)

```yaml
# Example: Verify protein results
- type: outcome_verification
  required_fields: ["proteinId", "sequence"]
  verification_patterns:
    - field: "proteinId"
      pattern: "uniprot.org/uniprot/[A-Z0-9]+"
      matches: "all"
```

### Use Pattern Graders (`evidence_pattern`) ONLY for:
- ⚠️ Required tool usage (already covered by `tool_called`)
- ⚠️ Security validation (specific queries forbidden)
- ⚠️ Debugging/development (temporary checks)

**Not for:** Verifying correctness of agent's approach!

### Use LLM-as-Judge ONLY for:
- 🤖 Semantic correctness too complex for rules
- 🤖 Natural language quality evaluation
- 🤖 Subjective criteria (clarity, completeness)
- 🤖 After code-based graders, as secondary check

**Not for:** Things you can verify programmatically!

## Best Practices Summary

1. **Grade what was produced, not how it was produced**
   - Check: "Are these bacterial taxa?" not "Did you use rdfs:subClassOf?"

2. **Use deterministic graders where possible**
   - Code-based > LLM-based for objective criteria

3. **Allow multiple valid solutions**
   - Don't enforce specific tool sequences
   - Accept alternative approaches that achieve same outcome

4. **Verify actual outcomes**
   - Database state changed?
   - Results have correct structure?
   - URIs follow expected patterns?

5. **Read transcripts to validate graders**
   - Are failures genuine or grader bugs?
   - Is grader too strict/loose?

## Migration Guide

To migrate from `evidence_pattern` to `outcome_verification`:

1. **Identify what you're really testing**
   - Not: "Did they use this exact SPARQL pattern?"
   - But: "Did they get bacterial taxonomy results?"

2. **Extract verifiable outcomes**
   - Look at successful runs' evidence dicts
   - What fields are present? What patterns do values follow?

3. **Write outcome rules**
   ```yaml
   - type: outcome_verification
     required_fields: [...]  # From evidence dict structure
     verification_patterns:  # From successful result patterns
       - field: "..."
         pattern: "..."
   ```

4. **Test with multiple approaches**
   - Run task multiple times
   - Verify both transitive (`+`) and non-transitive approaches pass
   - Check that invalid results fail

## Examples for Common Scenarios

### Scenario: Finding entities of a specific type

```yaml
# ❌ Don't check SPARQL patterns
- type: evidence_pattern
  required: ["?x a up:Protein"]

# ✅ Check results are actually that type
- type: outcome_verification
  result_type: "present"
  verification_patterns:
    - field: "@type"  # or "type" or whatever field indicates type
      pattern: "Protein"
      matches: "all"
```

### Scenario: Counting results

```yaml
# ❌ Don't check for COUNT() in SPARQL
- type: evidence_pattern
  required: ["COUNT("]

# ✅ Check actual result count
- type: outcome_verification
  result_type: "count"
  min_results: 10
  max_results: 100
```

### Scenario: Federation queries

```yaml
# ❌ Don't require specific SERVICE patterns
- type: evidence_pattern
  required: ["SERVICE <https://sparql.rhea-db.org"]

# ✅ Check results contain data from external source
- type: outcome_verification
  verification_patterns:
    - field: "reactionId"
      pattern: "rhea-db.org"  # Results contain Rhea URIs
      matches: "any"
```

## References

- [Anthropic: Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Outcome Verification Grader: `evals/graders/outcome_verification.py`
- Example Tasks: `evals/tasks/uniprot/`
