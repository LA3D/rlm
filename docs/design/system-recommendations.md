# Recommendations: Reducing Flakiness and Improving Efficiency

This document consolidates recommendations for addressing a recurring theme in the system’s current behavior:

> What you’re seeing are mostly mismatched expectations and missing affordances that make the system look flaky or inefficient.

The core RLM approach (REPL-based progressive disclosure with bounded views) is sound. The primary issues are (a) how we *configure and evaluate* it, and (b) whether we provide the model *high-leverage affordances* so it can use metadata shortcuts instead of rediscovering structure via repeated tool calls.

---

## 1) Symptoms We Should Treat as Signals (Not “Random LLM Flakiness”)

### Apparent non-convergence
- Ontology exploration tasks often hit `max_iters` and return a fallback answer (e.g., `[Max iterations] ...`).
- This looks like instability, but is frequently an iteration-budget mismatch.

### High tool-call / iteration counts on complex questions
- Pattern synthesis across multiple entities (e.g., “process pattern in SIO”) requires many sequential tool calls.
- This is expected under the RLM protocol (observe → act → observe), but can be reduced with better metadata usage.

### Tests that pass while behavior regresses (or fail for the wrong reasons)
- Some tests check “it ran” rather than protocol invariants, boundedness, and grounding.
- Some tests or docs claim executability without clearly declaring environment requirements.

---

## 2) Root Cause Map: Where the System Is Actually Weak

### A. Iteration budget mismatches
Many ontology tasks follow a stable multi-step pattern:
1) orient to environment/tools
2) fetch
3) extract
4) synthesize
5) finalize (FINAL/FINAL_VAR)

If a test (or eval) sets `max_iters=3` for an ontology question, it is effectively asking the model to skip required stages.

### B. Missing metadata-first affordances
`GraphMeta` already contains high-leverage indexes (labels, inverted labels, hierarchy, predicate stats, domain/range).
However, the model does not reliably exploit them unless we:
- expose them as explicit bounded tools, and
- teach “metadata-first” as the default recipe.

### C. Evaluation harness mismatches
We need clarity and consistency across:
- deterministic tests vs live API tests
- contracts/schemas for judging/extraction outputs
- what counts as “success” (protocol success vs semantic correctness)

### D. Sequential decision cost (expected)
RLM is intentionally sequential: tool calls require observing results before deciding next actions.
The design cost is real (latency + tokens). The remedy is to reduce unnecessary sequential calls via better shortcuts and better initial guidance (ReasoningBank recipes), not to “make the LLM smarter.”

---

## 3) Recommendations: Align Expectations First (Fast Wins)

### Recommendation 1: Treat `max_iters` as task-class dependent
Define a policy for iteration budgets and use it consistently across tests/evals:

- **Trivial tasks** (math, simple variable checks): `max_iters=2–3`
- **Single-entity ontology lookup** (“What is X?”): `max_iters=5`
- **Multi-entity pattern synthesis** (“Explain pattern relating X/Y/Z”): `max_iters=8–12`
- **Open-ended discovery** (“Find all relevant … and compare”): `max_iters=10–15` with strong bounded-view rules

Success criteria should focus on:
- converging without fallback,
- using bounded views,
- and providing grounded evidence.

### Recommendation 2: Separate deterministic vs live tests
Make the default `pytest` command safe and deterministic:

- **Deterministic suite** (no API calls): unit + integration without `llm_query` / `rlm_run`
- **Live suite** (opt-in): explicitly requires `ANTHROPIC_API_KEY` and network

Additionally:
- no API calls at module import time (live calls only inside test functions)
- live tests should auto-skip when `ANTHROPIC_API_KEY` is missing

### Recommendation 3: Standardize “judge” and “extract” schemas
Define and enforce the output contract for:
- trajectory judgment (`is_success`, `reason`, `confidence`, `missing`)
- memory extraction (0–3 items, required fields, bounded content)

Tests must validate the contract exactly; no alternate key names.

---

## 4) Recommendations: Add Missing Affordances (Metadata-First Tools)

The most consistent efficiency gains will come from enabling high-signal “metadata shortcuts” so the model can pick the next action intelligently.

### Recommended bounded tools (conceptual)
Expose these as explicit functions in the REPL namespace for each ontology:

1) **Exact label lookup**
   - Inputs: label string
   - Output: bounded list of matching URIs (exact match first; optionally fuzzy as a separate tool)
   - Purpose: avoid repeated substring scans when the label is known or near-known

2) **Hierarchy lookup**
   - Inputs: class URI
   - Output: bounded subclasses/superclasses (with labels)
   - Purpose: answer hierarchy questions without graph traversal or “probe then guess”

3) **Predicate frequency**
   - Output: top predicates with counts
   - Purpose: pick “important” properties early; reduces exploratory thrash

4) **Domain/range reverse lookup**
   - Inputs: class URI
   - Output: properties whose domain/range match (bounded)
   - Purpose: quickly identify likely relationship predicates for a pattern/task

### Improve `describe_entity` to reduce follow-up calls
Where feasible, include bounded, metadata-derived fields such as:
- immediate superclasses/subclasses (bounded)
- salient predicates (from predicate frequency / outgoing predicates)

Goal: fewer “describe → probe → describe again” loops.

---

## 5) Recommendations: ReasoningBank Owns the Default Recipe

The default exploration recipe should not live in the core RLM loop; it belongs in the procedural memory layer.

### A. One global “bootstrap recipe” (always injected)
Maintain a canonical procedural memory that teaches the model how to learn any ontology using progressive disclosure and metadata-first moves:

1) Read meta summary + list available tools
2) Resolve entity by exact label lookup; fallback to substring search
3) `describe_entity` on 1–3 candidates (bounded)
4) If hierarchy: use subclass/superclass tool (bounded)
5) If “what matters”: call predicate frequency tool (bounded)
6) Build an answer buffer; finalize via `FINAL_VAR`

This recipe is global, stable, and always present.

### B. Curriculum-driven micro-recipes (learned)
Use a curriculum so the system can self-specialize per ontology:

1) Orientation tasks (prefix/URI patterns, label predicates, key classes/properties)
2) Entity discovery tasks (definitions/comments/usage)
3) Hierarchy tasks (subclass patterns, taxonomy conventions)
4) Property semantics tasks (domain/range/inverse/subproperty)
5) Query construction tasks (select/construct templates)
6) Pattern synthesis tasks (multi-entity relationships)

Each stage should yield extracted micro-recipes tagged with ontology identity and task type.

### C. Human-in-the-loop prompt/hint injection
Treat human hints as first-class procedural memories:
- structured, bounded, typed (`strategy`, `tool_use`, `schema`, `debugging`, `constraint`)
- stored with provenance (`source=human`, session id)
- injected when relevant alongside the global recipe

The goal is to convert “one-off coaching” into reusable procedural knowledge.

---

## 6) Recommendations: Use UniProt Examples as a Curriculum and Eval Substrate

`ontology/uniprot/examples/**` is a high-quality corpus of query templates (`sh:SPARQLExecutable`) with:
- `rdfs:comment` (intent),
- `schema:keywords` (tags),
- `schema:target` (endpoint),
- query text.

### A. Offline evals: retrieval + adaptation (no endpoint calls)
Evaluate that the system can:
1) index templates
2) retrieve relevant examples by keyword/comment
3) extract query text and endpoint
4) adapt the query per instruction (e.g., add LIMIT, change taxon)

Grade via tool-use and transcript evidence, without requiring network calls.

### B. Live evals: execute with bounded results (opt-in)
Optionally execute the adapted query against the example’s `schema:target` and grade:
- use of bounded result handles,
- no large dumps,
- convergence without fallback.

---

## 7) What “Done” Looks Like (Success Metrics)

### Reliability
- Deterministic test suite passes without API key and without network access.
- Live test suite is opt-in and auto-skips without `ANTHROPIC_API_KEY`.
- Convergence failures are mostly explained by task difficulty (not random).

### Efficiency
- Single-entity ontology queries converge in ≤5 iterations consistently.
- Complex pattern queries show reduced iterations (target 20–30% reduction) after metadata-first affordances are available.

### Safety / grounding
- Answers remain grounded in REPL evidence; groundedness scores do not drop as iteration counts improve.

### Learning
- ReasoningBank shows measurable improvements on held-out tasks after curriculum training runs:
  - fewer iterations/tool calls,
  - earlier use of metadata-first tools,
  - stable convergence rates.

