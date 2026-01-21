# DSPy RLM Architecture Review

**Date:** 2026-01-21
**Context:** DSPy released official `dspy.predict.RLM` module (Jan 2026). We need to verify our implementation aligns with official patterns and isn't doing anything "dumb."

## Summary: We're Using DSPy RLM Correctly ✅

Our implementation **directly uses** `dspy.RLM` and follows the official API design. No major architectural issues identified.

## Official DSPy RLM API

From `/Users/cvardema/uvws/.venv/lib/python3.12/site-packages/dspy/predict/rlm.py`:

```python
class RLM(Module):
    def __init__(
        self,
        signature: type[Signature] | str,
        max_iterations: int = 20,
        max_llm_calls: int = 50,
        max_output_chars: int = 100_000,
        verbose: bool = False,
        tools: dict[str, Callable[..., str]] | None = None,
        sub_lm: dspy.LM | None = None,
        interpreter: CodeInterpreter | None = None,
    ):
        """
        Args:
            signature: Defines inputs and outputs (e.g., "context, query -> answer")
            tools: Additional tool functions callable from interpreter code
            sub_lm: LM for llm_query/llm_query_batched (defaults to dspy.settings.lm)
            interpreter: CodeInterpreter implementation (defaults to PythonInterpreter)
        """
```

**Key features:**
- Uses sandboxed PythonInterpreter (Deno/Pyodide/WASM) by default
- Provides `llm_query()` and `llm_query_batched()` as built-in tools
- Uses typed `SUBMIT(**kwargs)` for final outputs
- Accepts custom `CodeInterpreter` implementations
- Uses `REPLHistory` for tracking
- Has extract fallback when max iterations reached
- Thread-safe when using default interpreter (creates fresh instance per call)

## Our Implementation

From `rlm_runtime/engine/dspy_rlm.py` (lines 343-351):

```python
# Define typed signature
class QueryConstructionSig(dspy.Signature):
    """Construct answer using bounded ontology tools, optionally via SPARQL."""

    query: str = dspy.InputField(desc="User question to answer using the ontology.")
    context: str = dspy.InputField(desc="Ontology summary and tool instructions.")

    answer: str = dspy.OutputField(desc="Final grounded answer in natural language.")
    sparql: str = dspy.OutputField(
        desc="SPARQL query executed (if used), otherwise empty string."
    )
    evidence: dict = dspy.OutputField(
        desc="Grounding evidence: URIs, result samples, tool outputs."
    )

# Create RLM
rlm = dspy.RLM(
    QueryConstructionSig,
    max_iterations=max_iterations,
    max_llm_calls=max_llm_calls,
    verbose=verbose,
    tools=tools,
    sub_lm=sub_lm,
    interpreter=NamespaceCodeInterpreter(),
)

# Execute
pred = rlm(query=query, context=context)
```

**Key features:**
- ✅ Uses `dspy.RLM` directly (official API)
- ✅ Custom typed signature with domain-specific outputs (answer, sparql, evidence)
- ✅ Custom interpreter (`NamespaceCodeInterpreter`) - non-sandboxed host Python
- ✅ Pre-built tools via factory functions (`make_ontology_tools`, `make_sparql_tools`)
- ✅ Memory integration (retrieve → inject → judge → extract → store)
- ✅ MLflow tracking and JSONL trajectory logging

## Comparison Matrix

| Feature | Official DSPy RLM | Our Implementation | Assessment |
|---------|-------------------|-------------------|------------|
| **Core Module** | `dspy.RLM` | `dspy.RLM` | ✅ Correct |
| **Interpreter** | `PythonInterpreter` (sandboxed WASM) | `NamespaceCodeInterpreter` (host Python) | ✅ Valid (custom interpreter via protocol) |
| **Tool Injection** | `tools` parameter | `tools` parameter | ✅ Correct |
| **Signature** | Generic or custom | `QueryConstructionSig` (typed outputs) | ✅ Correct (domain-specific) |
| **Sub-LLM** | `sub_lm` parameter | `sub_lm` parameter | ✅ Correct |
| **SUBMIT Protocol** | `SUBMIT(**kwargs)` | `SUBMIT(**kwargs)` | ✅ Correct |
| **Built-in Tools** | `llm_query()`, `llm_query_batched()` | Inherited from `dspy.RLM` | ✅ Available |
| **Trajectory** | `pred.trajectory` | `pred.trajectory` | ✅ Compatible |
| **Memory Integration** | Not included | Custom (retrieve/extract) | ✅ Extension (not replacement) |
| **Observability** | Basic logging | MLflow + JSONL | ✅ Extension (not replacement) |

## NamespaceCodeInterpreter Compliance

Our custom interpreter implements the `CodeInterpreter` protocol correctly:

```python
@dataclass
class NamespaceCodeInterpreter:
    """Host-Python interpreter for DSPy RLM (non-sandboxed)."""

    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)
    output_fields: list[dict] | None = None
    _tools_registered: bool = False  # DSPy compatibility flag

    def start(self) -> None:
        """Initialize the interpreter namespace."""

    def shutdown(self) -> None:
        """Clear the interpreter namespace and reset state."""

    def execute(self, code: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute code in the persistent namespace.

        Returns:
            - FinalOutput if SUBMIT was called
            - stdout content if no SUBMIT
            - Combined stderr/stdout if errors occurred
        """
```

**Protocol requirements (from `dspy.primitives.code_interpreter.CodeInterpreter`):**
- ✅ Has `tools` property
- ✅ Has `start()` method (idempotent)
- ✅ Has `execute(code, variables)` method
- ✅ Has `shutdown()` method
- ✅ Returns `FinalOutput` when SUBMIT is called
- ✅ Raises `CodeInterpreterError` on runtime errors
- ✅ Maintains state across execute() calls

**Key difference:** Host Python execution vs sandboxed WASM:
- **Sandboxed (official):** Runs in Deno/Pyodide WASM environment, cannot access host filesystem/network
- **Host Python (ours):** Runs in same Python process, can access RDF graphs, ontology objects, SPARQL endpoints

**Trade-off analysis:**
- ✅ **Pro:** Direct access to rdflib graphs, no serialization overhead, full Python stdlib
- ✅ **Pro:** Can use existing ontology tools (`GraphMeta`, `sparql_query`) without adaptation
- ⚠️ **Con:** Not sandboxed - malicious code could access filesystem (acceptable for research tool)
- ⚠️ **Con:** Not thread-safe (each RLM instance reuses same interpreter) - but we don't use concurrency

## Architectural Decisions: Are We Doing Anything Dumb?

### Decision 1: Custom Interpreter (Host Python)

**Why we chose this:**
- Need direct access to rdflib `Graph` objects (in-memory RDF graphs)
- Need direct access to SPARQL endpoints via `SPARQLWrapper`
- Need persistent state across iterations (ontology loaded once, queried many times)
- Sandboxed interpreter would require serializing graphs to JSON/string (defeats handles-not-dumps philosophy)

**Is this dumb?** ❌ No
- Official DSPy RLM **explicitly supports** custom interpreters via `CodeInterpreter` protocol
- Source code comment: "you can provide any CodeInterpreter implementation (e.g., MockInterpreter, or write a custom one using E2B or Modal)"
- Our use case (research tool, trusted code) doesn't require sandboxing

### Decision 2: Custom Signature (QueryConstructionSig)

**Why we chose this:**
- Need typed outputs: `answer`, `sparql`, `evidence`
- Graders inspect structured fields (not just answer)
- MLflow logging requires structured metrics

**Is this dumb?** ❌ No
- Official DSPy RLM **expects** custom signatures: "String like 'context, query -> answer' or a Signature class"
- Typed outputs are core DSPy design pattern

### Decision 3: Pre-built Tools via Factories

**Why we chose this:**
- Bounded tool surface (max_results, timeouts, safe limits)
- Consistent API across local ontology and remote SPARQL
- LLM-friendly docstrings
- Enforces handles-not-dumps (tools return summaries, not full dumps)

**Is this dumb?** ❌ No
- Official DSPy RLM accepts tools via `tools` parameter
- Factory pattern ensures consistent configuration (endpoint, limits, namespace)
- Alternative (passing raw functions) would lose bounds/safety

### Decision 4: Memory Integration (Retrieve/Extract)

**Why we chose this:**
- Need closed-loop learning (retrieve → inject → judge → extract → store)
- Want longitudinal experiments (does system improve with experience?)
- Need provenance tracking (which memories were used? which were successful?)

**Is this dumb?** ❌ No
- Memory integration is **orthogonal** to DSPy RLM (happens before/after RLM execution)
- We use standard DSPy RLM for execution, wrap it with memory lifecycle
- This is an **extension**, not a replacement

### Decision 5: MLflow + JSONL Logging

**Why we chose this:**
- Need real-time debugging (JSONL stream)
- Need structured analysis (MLflow programmatic queries)
- Need experiment tracking (compare ablations across testing matrix)

**Is this dumb?** ❌ No
- Observability is **orthogonal** to DSPy RLM (happens alongside execution)
- DSPy RLM provides `trajectory` output - we just log it to multiple sinks
- This is an **extension**, not a replacement

## Official DSPy RLM Features We Should Consider

### 1. Built-in `llm_query_batched()` for Parallel Sub-LLM Calls

**What it does:**
```python
def llm_query_batched(prompts: list[str]) -> list[str]:
    """Query the LLM with multiple prompts concurrently."""
```

**Current usage:** We don't explicitly use this yet, but it's **automatically available** in our RLM environment because we use `dspy.RLM`.

**Should we use it?** ✅ Yes, for specific scenarios:
- Extracting multiple entity descriptions in parallel
- Batch entity classification tasks
- Parallel sense card generation for multiple ontologies

**Action:** Document in tool guide, add examples

### 2. Extract Fallback When Max Iterations Reached

**What it does:**
- If RLM reaches `max_iterations` without calling SUBMIT, DSPy uses an "extract" module
- Extract module reviews trajectory and synthesizes final output

**Current behavior:** We always get a result (DSPy RLM handles this internally)

**Should we change?** ❌ No
- Already handled by `dspy.RLM`
- Our graders can detect low-quality outputs via groundedness checks

### 3. `max_output_chars` Parameter

**What it does:**
- Truncates REPL output to prevent context overflow
- Default: 100,000 chars

**Current usage:** We don't set this (uses default)

**Should we tune it?** ⚠️ Maybe
- For SPARQL result handles with 10K+ rows, we rely on bounded views (`res_head`, `res_sample`)
- If LLM prints full result despite instructions, truncation is safety net
- Current default (100K) is reasonable for our use case

**Action:** Monitor if we see truncation warnings, tune if needed

## Recommendations

### 1. Thread Safety for Concurrent Experiments (Low Priority)

**Current state:** `NamespaceCodeInterpreter` reuses same instance across calls (not thread-safe)

**Official guidance:** "RLM instances are not thread-safe when using a custom interpreter. Create separate RLM instances for concurrent use."

**Recommendation:** ⚠️ Document limitation
- Current code is single-threaded (eval harness runs trials sequentially)
- If we add parallel trials, create fresh RLM instance per trial
- Not urgent (Phase 4 doesn't require concurrency)

### 2. Tool Docstring Quality (Medium Priority)

**Current state:** Our tool docstrings are good, but could be more concise for token efficiency

**Official pattern:**
```python
def llm_query(prompt: str) -> str:
    """Query the LLM with a prompt string."""
```

**Recommendation:** ✅ Review and optimize
- Audit `make_ontology_tools` and `make_sparql_tools` docstrings
- Ensure first line is <80 chars (LLM sees this in tool signature)
- Move detailed examples to second paragraph

**Action:** Quick audit in Phase 4

### 3. Sense Card Integration Pattern (Medium Priority)

**Current state:** Sense cards are generated once per ontology but not auto-injected into context

**Opportunity:** Add optional `sense_card` parameter to `run_dspy_rlm()`
```python
result = run_dspy_rlm(
    "What is Activity?",
    "prov.ttl",
    sense_card=prov_sense,  # Pre-built sense card
    memory_backend=backend,
    retrieve_memories=3
)
```

**Recommendation:** ✅ Add in Phase 4
- Enables ablation experiments (baseline vs sense vs memory vs both)
- Sense cards should be pre-built (not regenerated per run)
- Inject as additional context section

**Action:** Add `sense_card` parameter in Phase 4 matrix runner

## Conclusion

### Are We Doing Anything Dumb?

**No.** Our implementation:
- ✅ Uses official `dspy.RLM` API correctly
- ✅ Custom interpreter follows `CodeInterpreter` protocol
- ✅ Custom signature follows DSPy patterns
- ✅ Memory/observability are orthogonal extensions, not replacements
- ✅ Design decisions are justified by requirements (handles-not-dumps, graph access, provenance)

### What Should We Change?

**Nothing critical.** Minor improvements for Phase 4:
1. Document `llm_query_batched()` availability for batch entity operations
2. Add optional `sense_card` parameter for ablation experiments
3. Quick audit of tool docstring conciseness
4. Document thread-safety limitation (create fresh RLM per concurrent trial)

### Confidence Level

**High confidence** our architecture is sound:
- We're using DSPy RLM as intended (not fighting the framework)
- Our extensions (memory, observability) are clean wrappers, not hacks
- Custom interpreter is explicitly supported by DSPy design
- No red flags in comparison with official implementation

### Ready to Proceed to Phase 4?

✅ **Yes.** Architecture review complete. No blocking issues identified.
