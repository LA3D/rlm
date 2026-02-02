# Known Issues and Fixes

This document tracks known issues, their causes, and fixes/workarounds for the RLM experiment framework.

## DSPy Sandbox Tool Corruption (2026-02)

### Symptom
After a few successful iterations, tool functions (e.g., `sparql_query`, `endpoint_info`) become undefined with `NameError: name 'X' is not defined`. The agent then wastes iterations debugging why tools disappeared.

### Observed Pattern
1. Iterations 1-2: Tools work correctly
2. Iteration 3-4: Agent prints large context or encounters query errors
3. Iteration 5+: Tools become undefined, sandbox state corrupted

### Root Cause
DSPy's Deno/Pyodide sandbox loses namespace bindings under certain conditions. This appears related to:
- Large stdout output (printing full context)
- Error handling during tool calls
- Memory pressure in the WASM sandbox

### Impact
- Tasks take 13+ iterations instead of 5-6
- Agents waste iterations debugging tool scope
- Intermittent - doesn't happen every run

### Workaround
None currently. Issue needs to be reported to DSPy maintainers.

### Status
**Open** - DSPy upstream issue

---

## SUBMIT Syntax Confusion (2026-02)

### Symptom
Agent struggles with SUBMIT function syntax, trying keyword arguments, dictionaries, and positional arguments before succeeding.

### Root Cause
DSPy's RLM template shows `SUBMIT(sparql, answer)` which looks like positional args, but we added instructions saying "use keyword arguments". The actual DSPy SUBMIT accepts positional args.

### Fix Applied
Updated `exec_note` in `rlm_uniprot.py` to clarify syntax:
```
SUBMIT SYNTAX: Use keyword arguments: SUBMIT(sparql='...', answer='...')
NOT positional: SUBMIT(sparql_var, answer_var)
```

However, DSPy actually expects positional args, so agents eventually figure it out.

### Status
**Mitigated** - Agent eventually succeeds, but wastes iterations

---

## sparql_slice Default Limit Too Low (2026-02)

### Symptom
Agent calls `sparql_slice(result)` expecting all rows, but only gets 10 rows. Has to call repeatedly with offset.

### Root Cause
Default `end` parameter was hardcoded to 10 instead of using endpoint's default_limit (100).

### Fix Applied
Changed in `sparql.py`:
```python
# Before
'sparql_slice': lambda: self.sparql_slice(..., end=10)

# After
'sparql_slice': lambda: self.sparql_slice(..., end=self.default_limit)
```

### Status
**Fixed** - agents now get full results by default

---

## Guardrail Memory Not Retrieved (2026-02)

### Symptom
Anti-pattern guardrail memory exists but agent still tries the anti-pattern (e.g., `FILTER(CONTAINS)` instead of `rdfs:subClassOf+`).

### Root Cause
Memory search uses word overlap between query and memory title/desc/tags. Guardrail memory had technical terms but not the query terms ("annotations", "types", etc.).

### Fix Applied
Updated guardrail memory tags and desc to include retrieval trigger words:
```json
{
  "desc": "Guardrail: Avoid string matching when finding types, subtypes, or annotations",
  "tags": ["sparql", "anti-pattern", "types", "subtypes", "annotations", "hierarchy", "subclasses"]
}
```

### Status
**Fixed** - guardrail now retrieved for relevant queries. However, agent still tries anti-pattern first before reading context (separate behavioral issue).

---

## Agent Doesn't Read Context First (2026-02)

### Symptom
Procedural memories are injected into context, but agent explores with queries first, only reading context after failures.

### Root Cause
Default LLM behavior pattern:
1. Read question → form hypothesis based on training
2. Try initial approach
3. Only read context carefully after encountering problems

### Impact
- Guardrails don't prevent initial mistakes
- Agent wastes iterations on patterns it should avoid
- Memories help with recovery but not prevention

### Potential Fixes
1. Add instruction: "Review provided strategies BEFORE querying"
2. Move guardrails to top of context (more prominent)
3. Use L1 schema constraints for structural prevention (not behavioral)

### Status
**Open** - needs investigation into prompt engineering or context restructuring
