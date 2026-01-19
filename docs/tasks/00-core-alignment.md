# Task: Align `00_core.ipynb` with rlmpaper Protocol

This document describes the work needed to align `nbs/00_core.ipynb` with the `rlmpaper` reference implementation while using `claudette` as the LLM backend.

## Background

The trajectory document (`rlm-ontology-solveit-trajectory.md`) specifies that `00_core.ipynb` should be:

> **Thin glue over `rlmpaper`**
> - Goal: expose a stable interface for Solveit usage without re-implementing the RLM algorithm.
> - Focus: configuration, prompt selection, environment selection, logging/trace visibility, and "how to run".

However, we deliberately use **claudette** (Answer.AI's Claude wrapper) instead of rlmpaper's built-in LLM clients (raw anthropic/openai). This means we:

- **Follow rlmpaper's protocol** (prompts, types, parsing, iteration semantics)
- **Replace rlmpaper's LLM clients** with claudette `Chat`
- **Simplify environment execution** for Solveit compatibility (local exec)

## What to Copy/Align from rlmpaper

These are protocol artifacts—prompts, types, and parsing logic—not LLM client code.

### 1. System Prompt (`rlmpaper/rlm/utils/prompts.py`)

Copy `RLM_SYSTEM_PROMPT` verbatim. This is the ~80-line prompt that includes:
- REPL environment description
- `context`, `llm_query`, `llm_query_batched` variable descriptions
- Detailed examples of chunking strategies
- `FINAL(...)` and `FINAL_VAR(...)` instructions

**Current state**: `rlm_system_prompt()` in notebook is simplified (~20 lines).

**Action**: Replace with full rlmpaper prompt.

### 2. First-Iteration Safeguard (`build_user_prompt()`)

rlmpaper includes a critical safeguard for iteration 0:

```python
if iteration == 0:
    safeguard = "You have not interacted with the REPL environment or seen your prompt / context yet. Your next action should be to look through and figure out how to answer the prompt, so don't just provide a final answer yet.\n\n"
```

**Current state**: Partial safeguard exists but differs from rlmpaper.

**Action**: Match `build_user_prompt()` logic exactly, including:
- First-iteration safeguard
- Multi-context support (`context_0` through `context_n`)
- History support for persistent environments

### 3. QueryMetadata (`rlmpaper/rlm/core/types.py`)

rlmpaper's `QueryMetadata` auto-computes from the prompt:

```python
@dataclass
class QueryMetadata:
    context_lengths: list[int]
    context_total_length: int
    context_type: str  # 'str', 'list', 'dict'

    def __init__(self, prompt: str | list | dict):
        # Auto-compute lengths and type from prompt
```

**Current state**: Notebook's `QueryMetadata` requires manual construction.

**Action**: Align constructor to auto-compute from prompt.

### 4. Type Schemas

Align field names for compatibility:

| Type | Current Notebook | rlmpaper | Change |
|------|------------------|----------|--------|
| `REPLResult` | `error: str` | `stderr: str` | Rename field |
| `REPLResult` | (missing) | `llm_calls: list` | Add field |
| `CodeBlock` | `start_line`, `end_line` | (not present) | Keep (useful for debugging) |

### 5. Parsing Patterns

Verify these match rlmpaper:
- Code block extraction: ` ```repl ... ``` `
- `FINAL(...)` extraction
- `FINAL_VAR(...)` extraction with namespace lookup

**Current state**: `find_final()` and `find_code_blocks()` appear correct but should be verified against rlmpaper's `parsing.py`.

## What to Keep (claudette-based)

These implementations are correct and should remain:

### `llm_query()`
```python
def llm_query(prompt: str, model: str = 'claude-sonnet-4-5', name: str = 'llm_res', ns: dict = None) -> str:
    "Query sub-LLM using claudette Chat"
    # Uses claudette Chat, stores result in namespace
```

### `llm_query_batched()`
```python
def llm_query_batched(prompts: list, model: str = 'claude-sonnet-4-5', ...) -> str:
    "Batch query using async claudette"
    # Uses asyncio.gather with claudette
```

### Solveit Inspection Utilities
- `rlm_inspect()` - inspect namespace variables
- `rlm_history()` - format iteration history
- `rlm_context_summary()` - display context metadata
- `rlm_tool_info()` - inject tool info into Solveit

### Local Execution
- `exec_code()` - execute code blocks in local namespace
- This is appropriate for Solveit; rlmpaper's Docker/Modal environments are not needed

## Specific Changes Required

### Change 1: Replace System Prompt

In `rlm_system_prompt()`, replace the simplified prompt with rlmpaper's `RLM_SYSTEM_PROMPT`.

**File**: `nbs/00_core.ipynb`, cell containing `rlm_system_prompt`

**Source**: `rlmpaper/rlm/utils/prompts.py`, lines 6-81

### Change 2: Implement `build_user_prompt()` Logic

Add or update the user prompt builder to match rlmpaper's iteration-aware prompting:

```python
def build_user_prompt(root_prompt: str | None = None, iteration: int = 0,
                      context_count: int = 1, history_count: int = 0) -> dict:
    """Build iteration-aware user prompt with first-iteration safeguard."""
    if iteration == 0:
        safeguard = "You have not interacted with the REPL environment or seen your prompt / context yet. Your next action should be to look through and figure out how to answer the prompt, so don't just provide a final answer yet.\n\n"
        prompt = safeguard + USER_PROMPT
    else:
        prompt = "The history before is your previous interactions with the REPL environment. " + USER_PROMPT

    if context_count > 1:
        prompt += f"\n\nNote: You have {context_count} contexts available (context_0 through context_{context_count - 1})."

    if history_count > 0:
        prompt += f"\n\nNote: You have {history_count} prior conversation histories available."

    return {"role": "user", "content": prompt}
```

### Change 3: Align QueryMetadata Constructor

Update `QueryMetadata` to auto-compute from prompt:

```python
@dataclass
class QueryMetadata:
    context_lengths: list[int]
    context_total_length: int
    context_type: str

    def __init__(self, prompt: str | list | dict):
        if isinstance(prompt, str):
            self.context_lengths = [len(prompt)]
            self.context_type = "str"
        elif isinstance(prompt, dict):
            self.context_type = "dict"
            self.context_lengths = [len(str(v)) for v in prompt.values()]
        elif isinstance(prompt, list):
            self.context_type = "list"
            self.context_lengths = [len(str(chunk)) for chunk in prompt]

        self.context_total_length = sum(self.context_lengths)
```

### Change 4: Align REPLResult Fields

```python
@dataclass
class REPLResult:
    stdout: str = ''
    stderr: str = ''  # was: error
    locals: dict = field(default_factory=dict)
    execution_time: float = 0.0
    llm_calls: list = field(default_factory=list)  # new field
```

### Change 5: Update `rlm_run()` to Use Aligned Prompts

Ensure the main loop uses:
1. `build_rlm_system_prompt()` for initial messages
2. `build_user_prompt()` with correct iteration number
3. Proper metadata formatting

### Change 6: Add Compatibility Module (Optional)

Consider creating `rlm/_rlmpaper_compat.py` to centralize protocol artifacts:

```python
"""Protocol artifacts from rlmpaper.
We use claudette for LLM calls but follow rlmpaper's protocol."""

RLM_SYSTEM_PROMPT = """..."""
USER_PROMPT = """..."""
USER_PROMPT_WITH_ROOT = """..."""

def build_rlm_system_prompt(...): ...
def build_user_prompt(...): ...
```

## Testing

After changes, verify:

1. **First-iteration safeguard works**:
   - Run a query and confirm the model explores before answering
   - Check that iteration 0 includes the safeguard text

2. **QueryMetadata auto-computes correctly**:
   ```python
   meta = QueryMetadata(["chunk1", "chunk2", "chunk3"])
   assert meta.context_type == "list"
   assert len(meta.context_lengths) == 3
   ```

3. **System prompt matches rlmpaper**:
   - Compare generated system prompt against rlmpaper's output
   - Verify examples are included

4. **Existing tests still pass**:
   - `llm_query` works
   - `find_final` parses correctly
   - `find_code_blocks` extracts repl blocks

## Definition of Done

- [ ] `RLM_SYSTEM_PROMPT` matches rlmpaper verbatim
- [ ] `build_user_prompt()` implements first-iteration safeguard
- [ ] `QueryMetadata` auto-computes from prompt
- [ ] `REPLResult` fields align with rlmpaper (`stderr`, `llm_calls`)
- [ ] `rlm_run()` uses aligned prompt builders
- [ ] Existing notebook tests pass
- [ ] Documentation cell explains relationship to rlmpaper

## References

- `rlmpaper/rlm/utils/prompts.py` - System prompt and prompt builders
- `rlmpaper/rlm/core/types.py` - Type definitions
- `rlmpaper/rlm/utils/parsing.py` - Code block and FINAL parsing
- `rlmpaper/rlm/core/rlm.py` - Main RLM loop (for reference, not import)

---

## Completion Status

**Status**: ✅ **COMPLETED** (2026-01-17)

### What Was Done

1. **Created `rlm/_rlmpaper_compat.py`** - Protocol artifacts module containing:
   - Full `RLM_SYSTEM_PROMPT` (~80 lines with examples)
   - `build_rlm_system_prompt()` and `build_user_prompt()` with first-iteration safeguard
   - `QueryMetadata` that auto-computes from prompt
   - `REPLResult`, `CodeBlock`, `RLMIteration` types aligned with rlmpaper
   - `find_code_blocks()`, `find_final_answer()`, `format_iteration()` parsing functions

2. **Re-implemented `nbs/00_core.ipynb`** from scratch with:
   - Namespace-explicit design (all functions take `ns: dict`)
   - Imports from `_rlmpaper_compat.py` (no duplicate type definitions)
   - `in_solveit()` environment detection helper
   - `llm_query()` and `llm_query_batched()` using claudette with explicit namespace
   - `exec_code()` using rlmpaper-aligned `REPLResult`
   - `rlm_run()` with hybrid namespace pattern (`ns=None` creates `{}`, returns `(answer, iterations, ns)`)
   - Tests that work outside Solveit (no frame-walking required)
   - Usage examples with `#| eval: false` for API-dependent code

3. **Design Decisions**:
   - Used `functools.partial` (not lambdas) to bind `llm_query` functions to namespace
   - Returned namespace from `rlm_run()` for inspection (Answer.AI style)
   - Solveit integration deferred to separate notebook (not implemented yet)
   - No pre-population of imports in namespace (let REPL code import what it needs)

### Test Results

```bash
$ nbdev_test --path nbs/00_core.ipynb
Success.
```

All tests pass:
- ✅ Environment detection (`in_solveit()`)
- ✅ QueryMetadata auto-computation
- ✅ Code block extraction
- ✅ FINAL/FINAL_VAR parsing
- ✅ exec_code with error handling
- ✅ Namespace setup for rlm_run

### Generated Output

- `rlm/core.py` (6.9KB) - Exported module with 5 functions:
  - `in_solveit`
  - `llm_query`
  - `llm_query_batched`
  - `exec_code`
  - `rlm_run`

### Next Steps

1. Create `01_solveit.ipynb` for Solveit integration layer
2. Add optional stateful `RLM` class wrapper (like rlmpaper)
3. Implement bounded view primitives (Stage 2 of trajectory)
4. Add ontology/SPARQL handling (Stages 2-4 of trajectory)
