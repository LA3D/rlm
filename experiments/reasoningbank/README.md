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

### 4) The executor matters, so memory/context must be executor-agnostic
`experiments/agent_guide_generation/README.md` indicates that Scratchpad-style execution (persistent namespace + lightweight history) can outperform “current RLM” patterns for some tasks (especially long-form guide synthesis). `experiments/cost_analysis/comparison_20260128_113311.json` shows cost/latency tradeoffs across execution patterns. Therefore, the memory stack should be reusable across DSPy RLM, DSPy ReAct, and Scratchpad.

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
- which executor works best under the same context stack,
- whether closed-loop learning improves over time.

### Benchmarks / task suites
Use existing task suites so we can compare across patterns:

1) **Query construction suite (L1–L5)**  
   - Use tasks from `experiments/pattern_comparison/` (entity lookup → relationships → multi-hop → filtering → aggregation).

2) **Ontology materialization → query (two-phase workflow)**  
   - Leverage artifacts and approach from `experiments/ontology_exploration/`:
     - Phase 1: materialize guide (L3 full artifact)
     - Phase 2: inject packed summary (L3 packer)

3) **Agent guide generation (separate track)**  
   - Use `experiments/agent_guide_generation/` to test executor choice (Scratchpad vs RLM vs ReAct) under the same memory layers.

### Metrics (minimal set)
- **Convergence**: did we produce an answer (and/or valid SPARQL)?
- **Quality**:
  - query tasks: correctness + anti-pattern avoidance (re-use reasoning-chain validation checks where possible)
  - guide tasks: rubric/judge score + grounded URI coverage
- **Efficiency**: time, tokens, LLM calls, iterations, tool calls
- **Memory health** (when L2 enabled): size, duplicate rate, novelty rate, win-rate drift, usage distribution

---

### Phase 0: Baselines (no learning)

**E0 — Baseline executor performance**
- Executors: DSPy RLM vs ReAct (and Scratchpad when applicable)
- Layers: base only
- Tasks: query suite (L1–L5)

**E1 — L0 Ont-Sense only**
- Compare to E0 to measure deterministic sense-card value.

**E2 — L1 constraints only**
- Add domain/range + anti-pattern guardrails (no exemplars).
- Goal: validate “constraints help” in the broader suite.

**E3 — L3 guide-summary only**
- Materialize guide once, then inject only a compact summary (E4-style packing).
- Track break-even point: guide creation cost amortized over N queries.

**E4 — L2 procedural memory retrieval-only (seeded)**
- Seed bank with a small curated pack:
  - success strategies (what to do)
  - failure guardrails (what not to do)
- No extraction, no consolidation.

**E5 — Full layer cake**
- Enable L0 + L1 + L2 + L3 simultaneously.
- Goal: measure additive/synergistic gains and detect redundancy.

**E6 — Retrieval policy ablation**
- Compare Mode 1 (auto-inject) vs Mode 2 (tool-mediated) under identical budgets.

---

### Phase 1: Closed-loop learning (ReasoningBank proper)

**E7 — Closed loop: judge + extract (append-only)**
- After each task: judge success/failure; extract up to N memories into L2 store.
- No consolidation/forgetting yet.
- Track extraction quality and whether later tasks improve.

**E8 — Add consolidation**
- Merge/supersede/discard decisions per new memory item; track duplicate rate.

**E9 — Add forgetting**
- Bound active memory size; keep floors for both success and failure items.

**E10 — MaTTS-style rollouts**
- Run N rollouts per task; select best by judge.
- Extraction:
  - v0: extract from best only
  - v1: contrastive extraction using all rollouts (success vs failure)

---

### Phase 2: Executor cross-over (same memory stack, different runtime)

Re-run selected experiments (E2/E5/E7) across executors:
- Scratchpad (for long synthesis / materialization / guide generation)
- DSPy RLM vs DSPy ReAct (for cost/latency and convergence tradeoffs)

Goal: validate the memory stack is executor-agnostic and quantify interactions (some layers may benefit some executors more).

---

## Updated “Implementation Tasks” (Experiment-first, reuse runtime primitives)

This README previously suggested implementing a fresh store/tools/prompts stack inside `experiments/reasoningbank/`.
In this repo, substantial primitives already exist in runtime code (SQLite memory, extraction/judging hooks, trajectory logging).

Updated recommendation:

- Keep **generic memory primitives** (store/retrieve/log/extract) in `rlm_runtime/`.
- Implement **ReasoningBank experiments** here as glue/config:
  - runners that assemble layer toggles + budgets + executor choice
  - curated packs (seed procedural items, schema constraints, exemplars)
  - summary packers (especially for L3 guides)
  - reports (JSONL + markdown summaries)

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

