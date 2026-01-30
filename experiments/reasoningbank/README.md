# ReasoningBank + RLM + Ont-Sense: Layered Memory Architecture & Experiment Plan

This document updates the original “ReasoningBank + RLM” integration plan using lessons from the rest of the repo’s experiment suite under `experiments/` (notably `experiments/ontology_exploration/`, `experiments/agent_guide_generation/`, `experiments/cost_analysis/`, `experiments/complexity_test/`, `experiments/pattern_comparison/`, and `experiments/reasoning_chain_validation/`).

The goal stays the same:

- Implement and evaluate a **ReasoningBank-style continual-learning loop** (retrieve → run → judge → extract → persist → consolidate) on top of an RLM executor.
- Make it **experimentable**: clean ablations across memory layers, packing/retrieval policies, and execution patterns.

The key change: treat “memory” as a **layer cake** of distinct artifact types with different lifecycles and budgets, rather than a single bank to dump into prompts.

---

## What We Learned (Architectural Implications)

### 1) Packing > raw retrieval
`experiments/ontology_exploration/analysis/e4_results.md` shows a compressed guide summary (≈935 chars) materially improves cost/latency and query quality versus no guide. The “memory system” must include **packers** (summarizers/formatters) and explicit **budgets** per layer.

### 2) Delegation doesn’t reliably “emerge”
Across `experiments/ontology_exploration/`, `experiments/cost_analysis/`, and `experiments/complexity_test/`, explicit instructions to use `llm_query()` (or expecting the model to use it spontaneously) did not reliably change behavior. Therefore:

- Tool-mediated retrieval (`mem_search` / `mem_get`) is valuable, but cannot be the only retrieval path.
- A default **auto-injection** policy (system retrieves + packs + injects) must exist so experiments work even when the model never learns to call retrieval tools.

### 3) Deterministic schema constraints can beat exemplars
`experiments/reasoning_chain_validation/results/comparison_summary.md` suggests that adding domain/range constraints and anti-pattern guardrails improved reasoning quality more reliably than adding a small number of exemplars in that setup. This motivates a first-class “schema/constraints” layer distinct from learned procedural memory.

### 4) The executor matters less than data structure
`experiments/agent_guide_generation/README.md` indicates that Scratchpad-style execution (persistent namespace + lightweight history) can outperform "current RLM" patterns for some tasks. However, `experiments/ontology_exploration/` (E1-E5) demonstrates that **DSPy RLM works well for query construction tasks** (44-53% cost reduction with guides, 100% convergence). The memory stack should be reusable across executors, but **executor ablation is not a priority**—the ontology_exploration experiments already validate RLM effectiveness.

### 5) Handles, not payloads (RLM v2 invariants)
From `rlm_notes.md`: the difference between "RLM as a scalable scaffold" and "an agent that slowly turns into a summarizer" is **data structure**. Critical invariants:

- **Treat prompt/context/memory as REPL state, not chat history**
- **Store handles (IDs, references), not payloads (full text)**
- **Make recursion programmatic** (Python loops + batched LLM calls), not "sub-agent vibes"
- **Avoid Finish(answer) trap**: return variables, then `SUBMIT(answer=var)`
- **Instrument prompt leakage**: measure whether context leaks into iterative history

> "A lot of 'RLM quality' is downstream of how you structure the environment, tools, and the 'shape' of information you let leak back into the iterative prompt."

---

## The Layer Cake (Memory Taxonomy)

The goal of this taxonomy is to let experiments toggle layers independently, and to prevent “memory” from becoming an unbounded prompt dump.

### L0 — Ont-Sense (deterministic, compact, grounded)
- **What**: A small, programmatically-derived ontology “sense” artifact (namespaces, core entities/properties, affordances).
- **Why**: Cheap orientation; reduces exploration overhead.
- **Lifecycle**: recompute when ontology changes; no LLM required.

### L1 — Schema Constraints & Guardrails (deterministic / curated)
- **What**: Domain/range constraints, common anti-patterns, verification rubrics.
- **Why**: Can improve correctness without relying on emergent behavior.
- **Lifecycle**: curated + optionally auto-derived; updated slowly.

### L2 — Procedural Memory (ReasoningBank “strategies”)
- **What**: Transferable “how to do it” strategies extracted from trajectories, including failure guardrails.
- **Why**: Continual improvement via experience distillation.
- **Lifecycle**: judge+extract → persist; then consolidate/forget.

### L3 — Materialized Task Artifacts (expensive to create, cheap to reuse)
- **What**: “One-time” rich artifacts (e.g., an ontology guide produced via exploration), then compressed into a small summary for repeated use.
- **Why**: E3→E4 suggests materialization amortizes quickly if the runtime injection is packed.
- **Lifecycle**: generate rarely; store full artifact; inject only packed summary.

### L4 — Trace & Observability (not injected as context)
- **What**: trajectories, tool logs, verification traces, run metadata.
- **Why**: debuggability + offline learning; required for ReasoningBank extraction and evaluation.
- **Lifecycle**: append-only; used by analysis/judging/extraction tooling.

---

## Architecture (Components & Boundaries)

To keep the system general and experiment-friendly, separate these concerns:

### A) Executors (how reasoning happens)
Pluggable runtime patterns:
- **DSPy RLM** (code generation + execution)
- **DSPy ReAct** (tool loop, no code generation)
- **Scratchpad** (persistent namespace + truncated history; “original RLM” style)

Executors should share the same memory/context stack (below).

### B) Memory substrate (storage + retrieval + provenance)
Generic services:
- **Store**: persistence (SQLite, JSONL packs) + provenance (run_id, trajectory_id, ontology_id, timestamps).
- **Retriever**: lexical first (BM25/FTS) with an embeddings upgrade path.
- **Usage logger**: link retrieved items ↔ trajectories; update simple “wins/uses” counters.

### C) Packers (bounded injection)
Layer-specific packers enforce budgets and avoid prompt bloat:
- L0 packer: short sense card (or per-task “sense slices”).
- L1 packer: compact constraint list + anti-pattern bullets.
- L2 packer: top-K success + top-K failure (guardrails).
- L3 packer: guide summary (E4-style compression).

### D) ContextBuilder (the layer cake assembler)
Given `{task, ontology_id, toggles, budgets}`, build the final runtime context:

- Base instructions (tools, output schema, safety)
- L0 Ont-Sense payload (optional)
- L1 constraints payload (optional)
- L2 procedural payload (optional)
- L3 guide-summary payload (optional)

This is the primary experimental control surface.

### E) Policies (ReasoningBank is a policy suite, not a store)
Policies define behavior on top of the substrate:
- **Retrieval policy**: how many items per layer; success/failure mix; curriculum-aware selection; ontology scoping.
- **Judging policy**: success/failure labeling, rubric, confidence.
- **Extraction policy**: how to distill memories; how many; how to avoid generic noise.
- **Consolidation/forgetting policy**: merge/supersede/discard; bounded-bank GC.
- **Rollout policy (MaTTS)**: N rollouts; selection; contrastive extraction.

---

## RLM-Friendly Tool API (Foundation)

Before running experiments, implement a tool API that enforces the "handles, not payloads" principle. This is the **most important implementation detail** for RLM quality.

### Handle Pattern (Required)

Large data should be represented as references, not raw text:

```python
class BlobRef:
    def __init__(self, key: str, n: int):
        self.key, self.n = key, n
    def __repr__(self):
        return f"BlobRef(key={self.key!r}, n={self.n})"
```

The REPL sees `BlobRef(key='graph_001', n=1664)`, not 400K characters.

### Context Inspection Tools (Bounded)

Force "inspect before load" as a tool contract:

```python
ctx_stats(ref)                    # → length, line count, checksum
ctx_peek(ref, n=200)              # → short preview
ctx_slice(ref, start, end)        # → bounded excerpt
ctx_find(ref, pattern, k=20)      # → offsets + tiny snippets
```

### Memory Retrieval Tools (Two-Phase)

Separate search (IDs only) from fetch (full content, capped):

```python
mem_search(query, k=6, polarity=None, role=None)  # → IDs + titles + 1-line descriptions
mem_get(ids)                                       # → full items (hard cap: refuse >N items)
mem_quote(id, max_chars)                          # → bounded excerpt if needed
```

### Write Tools (No Stdout)

Tools that write should not print verbose output:

```python
mem_add(...)        # → writes to store, returns confirmation
event_log(obj)      # → writes to SQLite, no stdout
```

### Tool API Contract

All tools MUST:
- Return JSON / dicts (structured, parseable)
- Avoid printing to stdout (bloats history)
- Return bounded results (explicit caps)
- Represent large objects as references (never full payloads)

### Prompt Leakage Instrumentation

Every experiment run should log:
- Total characters printed to stdout
- Total size of `variables_info` (or proxy: number/type of variables + previews)
- Number of times a tool returned >X chars
- Number of subcalls

This enables correlating "RLM quality" with "context leakage."

---

## Runtime Integration Modes (A Critical Ablation)

There are two ways for the agent to “use memory”:

### Mode 1: Auto-inject (system retrieves + packs + injects)
- Pros: works even if the model never calls retrieval tools; consistent with observed “delegation doesn’t emerge”.
- Cons: retrieval decisions move outside the agent.

### Mode 2: Tool-mediated retrieval (agent calls `mem_search` / `mem_get`)
- Pros: agent autonomy; keeps prompts smaller by default.
- Cons: fragile; often requires training/prompting to be used consistently.

Recommendation: implement both; default to **auto-inject**; explicitly compare modes.

---

## Concrete Experimental Plan (Synthesis of Ideas)

We want experiments that isolate:
- which layers help (L0/L1/L2/L3),
- which packers help (full vs summary; strict budgets),
- whether handle-based tools prevent prompt leakage,
- whether closed-loop learning improves over time.

**Note on executor comparison**: `experiments/ontology_exploration/` (E1-E5) already validates that DSPy RLM works well for query construction (44-53% cost reduction, 100% convergence). We skip executor ablation and focus on **memory architecture**.

### Benchmarks / task suites
Use existing task suites so we can compare across patterns:

1) **Query construction suite (L1–L5)**
   - Use tasks from `experiments/pattern_comparison/` (entity lookup → relationships → multi-hop → filtering → aggregation).

2) **Ontology materialization → query (two-phase workflow)**
   - Leverage artifacts and approach from `experiments/ontology_exploration/`:
     - Phase 1: materialize guide (L3 full artifact)
     - Phase 2: inject packed summary (L3 packer)

### Metrics (minimal set)
- **Convergence**: did we produce an answer (and/or valid SPARQL)?
- **Quality**:
  - query tasks: correctness + anti-pattern avoidance (re-use reasoning-chain validation checks where possible)
  - guide tasks: rubric/judge score + grounded URI coverage
- **Efficiency**: time, tokens, LLM calls, iterations, tool calls
- **Prompt leakage**: stdout chars, variables_info size, large-return count (NEW)
- **Memory health** (when L2 enabled): size, duplicate rate, novelty rate, win-rate drift, usage distribution

---

### Phase 0: Layer Ablation (no learning)

**E1 — Baseline (no memory layers)**
- Layers: none (base instructions only)
- Tasks: query suite (L1–L5)
- Purpose: establish baseline for layer comparisons

**E2 — L0 Ont-Sense only**
- Add deterministic sense card (namespaces, core entities, affordances)
- Compare to E1 to measure sense-card value

**E3 — L1 constraints only**
- Add domain/range + anti-pattern guardrails (no exemplars)
- Goal: validate "constraints help" independent of learned memory

**E4 — L3 guide-summary only**
- Materialize guide once, then inject only a compact summary (E4-style packing)
- Track break-even point: guide creation cost amortized over N queries

**E5 — L2 procedural memory retrieval-only (seeded)**
- Seed bank with a small curated pack:
  - success strategies (what to do)
  - failure guardrails (what not to do)
- No extraction, no consolidation

**E6 — Full layer cake**
- Enable L0 + L1 + L2 + L3 simultaneously
- Goal: measure additive/synergistic gains and detect redundancy

**E7 — Prompt leakage ablation** (NEW)
- **Condition A**: Naive tools (return full payloads, verbose stdout)
- **Condition B**: Handle-based tools (BlobRef pattern, two-phase retrieval)
- Measure: context size per iteration, total iterations, cost, convergence
- Goal: validate that handle pattern improves RLM quality

**E8 — Retrieval policy ablation**
- Compare Mode 1 (auto-inject) vs Mode 2 (tool-mediated) under identical budgets

---

### Phase 1: Closed-loop learning (ReasoningBank proper)

**E9 — Closed loop: judge + extract (append-only)**
- After each task: judge success/failure; extract up to N memories into L2 store
- No consolidation/forgetting yet
- Track extraction quality and whether later tasks improve

**E10 — Add consolidation**
- Merge/supersede/discard decisions per new memory item; track duplicate rate

**E11 — Add forgetting**
- Bound active memory size; keep floors for both success and failure items

**E12 — MaTTS-style rollouts**
- Run N rollouts per task; select best by judge
- Extraction:
  - v0: extract from best only
  - v1: contrastive extraction using all rollouts (success vs failure)

---

### Phase 2: Analysis (optional)

If Phase 0-1 results warrant deeper investigation:

**E13 — Layer interaction analysis**
- Re-run E6 (full layer cake) with ablated subsets to detect which layer combinations have synergy vs redundancy

**E14 — Executor cross-over** (if needed)
- Re-run selected experiments across executors (Scratchpad, ReAct)
- Only if Phase 0-1 suggests executor-specific interactions
- Note: `experiments/ontology_exploration/` already shows RLM is effective, so this is low priority

---

## Implementation Priorities

### Priority 1: RLM-Friendly Tool API

The **most important** implementation work is the handle-based tool API (see "RLM-Friendly Tool API" section above). This is the foundation that determines RLM quality.

Implementation steps:
1. Create `BlobRef` wrapper for large data (graphs, documents, memory items)
2. Implement bounded context tools: `ctx_stats`, `ctx_peek`, `ctx_slice`, `ctx_find`
3. Implement two-phase memory tools: `mem_search` (IDs only), `mem_get` (capped), `mem_quote` (bounded)
4. Add prompt leakage instrumentation to trajectory logging

### Priority 2: Layer Packers

Each layer needs a packer that enforces budgets:
- L0 packer: sense card (≤600 chars)
- L1 packer: constraint list + anti-patterns (≤1000 chars)
- L2 packer: top-K success + top-K failure (configurable budget)
- L3 packer: guide summary (≤1000 chars, like E4's 935-char summary)

### Priority 3: Experiment Runners

Leverage existing `rlm_runtime/` primitives (SQLite memory, trajectory logging). Implement here:
- Runners that assemble layer toggles + budgets
- Curated seed packs (success strategies, failure guardrails, schema constraints)
- Reports (JSONL + markdown summaries)
- Leakage analysis scripts

---

## Quality Gates (Required)

1) **Reproducibility**
- Every run saves: config, results JSONL, and either a DB snapshot or DB pointer + commit hash.

2) **Observability**
- Logs must capture: what layers were enabled, what was retrieved, what was packed/injected, judge rationale, extracted memories, consolidation actions.

3) **Bounded context**
- Each layer has an explicit budget and packer; never inject “full bank” or “full guide”.

4) **Stable evaluation**
- Prefer deterministic checks where possible (constraints/anti-pattern validators); keep any LLM rubric stable and versioned.

---

## Appendix: Minimal “ReasoningBank-lite” Prototype (Concept Demo)

This is a tiny demonstration of the *loop* concept. It is not the intended experiment architecture (it omits packing policies, provenance, and reproducible storage), but it’s useful as a mental model.

```python
import json
import time
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

import dspy


@dataclass
class StrategyItem:
    title: str
    description: str
    content: str
    tags: list[str] | None = None
    created_at: float = 0.0
    uses: int = 0
    wins: int = 0


class StrategyBank:
    def __init__(self):
        self.items: list[StrategyItem] = []

    def add(self, item: StrategyItem):
        if not item.created_at:
            item.created_at = time.time()
        self.items.append(item)

    def _score(self, query: str, item: StrategyItem) -> float:
        text = f"{item.title}\n{item.description}\n{item.content}"
        return SequenceMatcher(None, query.lower(), text.lower()).ratio()

    def retrieve(self, query: str, k: int = 4) -> list[StrategyItem]:
        scored = [(self._score(query, it), it) for it in self.items]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for s, it in scored[:k] if s > 0.05]


bank = StrategyBank()


def rb_retrieve(query: str, k: int = 4) -> str:
    items = bank.retrieve(query, k=k)
    for it in items:
        it.uses += 1
    return json.dumps([asdict(it) for it in items], ensure_ascii=False)


def rb_add(title: str, description: str, content: str, tags: str = "") -> str:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    bank.add(StrategyItem(title=title, description=description, content=content, tags=tag_list))
    return "OK"


rlm = dspy.RLM(
    "context, question -> answer",
    max_iterations=12,
    max_llm_calls=25,
    tools={"rb_retrieve": rb_retrieve, "rb_add": rb_add},
)
```

