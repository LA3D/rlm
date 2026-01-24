# Analysis Documentation

This directory contains analyses, findings, and investigations from RLM ontology query construction experiments and evaluations.

## Quick Navigation

| Category | Focus | Key Findings |
|----------|-------|--------------|
| **[Patterns](#design-patterns)** | Architecture comparisons | Rails pattern, Simple vs RLM tools |
| **[Eval Runs](#evaluation-runs)** | Baseline & regression tests | LLM judge validation, performance tracking |
| **[Convergence](#convergence-analysis)** | Iteration behavior | Complex queries need 8+ iterations |
| **[Memory](#memory--reasoningbank)** | ReasoningBank studies | Memory overhead, retrieval patterns |
| **[Performance](#performance-analysis)** | Profiling & optimization | Token usage, timing bottlenecks |
| **[Tools](#tool-usage-analysis)** | Tool call patterns | 60% wasted effort in exploration |
| **[Trajectories](#trajectory-analysis)** | Detailed execution traces | Agent behavior deep dives |
| **[Phases](#phase-retrospectives)** | Implementation milestones | Phase 1, 2 summaries |

---

## TL;DR - Key Findings

### 🎯 Most Important Insights

1. **Simple approach competitive with RLM** ([simple-vs-rlm-tools-comparison.md](./comparisons/simple-vs-rlm-tools-comparison.md))
   - 3 general tools (view, rg, sparql) vs 2 bounded tools
   - Simple: 21-33 tool calls, direct file access
   - RLM: More bounded but similar performance

2. **60% wasted effort in exploration** ([trajectory-access-patterns-analysis.md](./trajectories/trajectory-access-patterns-analysis.md))
   - Agent rediscovers patterns documented in AGENT_GUIDE.md
   - 6/10 iterations spent on schema exploration

3. **Rails pattern wins for documentation** ([rails-doc-writer-pattern.md](./patterns/rails-doc-writer-pattern.md))
   - Load everything upfront (full ontology in context)
   - Eliminates exploration overhead
   - Works for agent guide generation

4. **Memory overhead significant** ([memory-tracking-findings.md](./memory/memory-tracking-findings.md))
   - ReasoningBank adds 20-30% overhead
   - Retrieval helps on repetitive tasks
   - Needs optimization for cold-start queries

5. **LLM judge more reliable than exact match** ([llm-judge-validation-analysis.md](./eval_runs/llm-judge-validation-analysis.md))
   - 95% agreement with human evaluation
   - Handles semantic equivalence
   - Critical for eval reliability

---

## Design Patterns

**Focus:** Architecture comparisons and design pattern analysis

| File | What It Analyzes | Key Finding |
|------|-----------------|-------------|
| [simple-vs-rlm-tools-comparison.md](./comparisons/simple-vs-rlm-tools-comparison.md) | Simple tools vs bounded RLM tools | Simple approach competitive, less overhead |
| [tool-implementation-comparison.md](./comparisons/tool-implementation-comparison.md) | Side-by-side code comparison | Bounded tools add complexity |
| [rails-doc-writer-pattern.md](./patterns/rails-doc-writer-pattern.md) | Load-everything-upfront pattern | Wins for documentation generation |
| [simple-approach-findings-summary.md](./comparisons/simple-approach-findings-summary.md) | Summary of simple approach benefits | Faster convergence on small ontologies |

**Start here:** [simple-vs-rlm-tools-comparison.md](./comparisons/simple-vs-rlm-tools-comparison.md) - Most comprehensive comparison

---

## Evaluation Runs

**Focus:** Analysis of specific eval runs, baselines, and regression testing

| File | Date | What It Tests | Result |
|------|------|--------------|--------|
| [baseline-eval-run-2026-01-23.md](./eval_runs/baseline-eval-run-2026-01-23.md) | 2026-01-23 | Initial baseline after fixes | 7/8 tasks pass |
| [eval-rerun-post-llm-judge-fix-2026-01-23.md](./eval_runs/eval-rerun-post-llm-judge-fix-2026-01-23.md) | 2026-01-23 | After LLM judge improvements | 8/8 tasks pass |
| [llm-judge-validation-analysis.md](./eval_runs/llm-judge-validation-analysis.md) | 2026-01-23 | LLM judge accuracy validation | 95% human agreement |
| [dopamine-refusal-fix-2026-01-23.md](./eval_runs/dopamine-refusal-fix-2026-01-23.md) | 2026-01-23 | Dopamine task refusal handling | Fixed graceful refusal |
| [eval-task-complexity-analysis.md](./eval_runs/eval-task-complexity-analysis.md) | 2026-01-22 | Task difficulty assessment | Simple vs complex patterns |

**Most recent:** [eval-rerun-post-llm-judge-fix-2026-01-23.md](./eval_runs/eval-rerun-post-llm-judge-fix-2026-01-23.md) - 100% pass rate

---

## Convergence Analysis

**Focus:** How many iterations are needed, when agents converge, failure modes

| File | Focus | Finding |
|------|-------|---------|
| [COMPLEX_QUERY_CONVERGENCE.md](./convergence/COMPLEX_QUERY_CONVERGENCE.md) | Complex query behavior | Need 8+ iterations for multi-step queries |
| [CONVERGENCE_BEHAVIOR_SUMMARY.md](./convergence/CONVERGENCE_BEHAVIOR_SUMMARY.md) | Overall patterns | Simple: 2-4 iterations, Complex: 6-10 |
| [CONVERGENCE_ANALYSIS.md](./convergence/CONVERGENCE_ANALYSIS.md) | Detailed convergence study | Early vs late convergence patterns |

**Key insight:** Iteration limits should be task-adaptive (simple: 5, complex: 10)

---

## Memory & ReasoningBank

**Focus:** Procedural memory retrieval, storage, and effectiveness

| File | Focus | Finding |
|------|-------|---------|
| [memory-tracking-findings.md](./memory/memory-tracking-findings.md) | Memory overhead measurement | 20-30% overhead, helps on repetitive tasks |
| [memory-agent-behavior-analysis.md](./memory/memory-agent-behavior-analysis.md) | Agent memory usage patterns | Retrieval improves with similar queries |
| [memory-simple-vs-complex-comparison.md](./comparisons/memory-simple-vs-complex-comparison.md) | Memory on different task types | More valuable for complex queries |
| [memory-usage-sanity-check.md](./memory/memory-usage-sanity-check.md) | Memory correctness validation | Stored memories are accurate |
| [reasoningbank-overhead-analysis.md](./memory/reasoningbank-overhead-analysis.md) | Performance impact | Cold-start penalty, warm-up helps |
| [reasoningbank-3trial-analysis.md](./memory/reasoningbank-3trial-analysis.md) | Multi-trial comparison | Consistent benefits after trial 1 |
| [seed-heuristics-impact.md](./memory/seed-heuristics-impact.md) | Seed memory effectiveness | Good heuristics bootstrap faster |

**Best overview:** [memory-tracking-findings.md](./memory/memory-tracking-findings.md)

---

## Performance Analysis

**Focus:** Timing, token usage, profiling, bottleneck identification

| File | Focus | Finding |
|------|-------|---------|
| [performance-timing-and-token-analysis.md](./performance/performance-timing-and-token-analysis.md) | Token usage patterns | Heavy context in early iterations |
| [performance-profiling-results.md](./performance/performance-profiling-results.md) | Execution profiling | SPARQL execution dominates time |
| [performance-investigation-plan.md](./performance/performance-investigation-plan.md) | Performance optimization roadmap | Prioritize query caching |

**Bottleneck:** SPARQL query execution, not LLM calls

---

## Tool Usage Analysis

**Focus:** How agents use tools, efficiency, wasted effort

| File | Focus | Finding |
|------|-------|---------|
| [trajectory-access-patterns-analysis.md](./trajectories/trajectory-access-patterns-analysis.md) | Tool call patterns | 60% wasted on schema exploration |
| [tool-usage-inefficiency-analysis.md](./tools/tool-usage-inefficiency-analysis.md) | Inefficient tool use | Redundant searches, failed queries |
| [METADATA_USAGE_ANALYSIS.md](./tools/METADATA_USAGE_ANALYSIS.md) | Metadata exploitation | Underutilized metadata hints |
| [llm-behavior-with-structured-sense.md](./tools/llm-behavior-with-structured-sense.md) | Sense card impact | Structured sense reduces exploration |

**Key problem:** Agents rediscover what's already documented

---

## Trajectory Analysis

**Focus:** Deep dives into specific agent execution traces

| File | Focus | Finding |
|------|-------|---------|
| [trajectory-analysis-2026-01-23-post-llm-judge.md](./trajectories/trajectory-analysis-2026-01-23-post-llm-judge.md) | Post-judge trajectory | Improved convergence with judge feedback |
| [ecoli-k12-trajectory-analysis.md](./trajectories/ecoli-k12-trajectory-analysis.md) | E. coli K-12 query | Complex reasoning over protein functions |
| [meta-analysis-first-run.md](./trajectories/meta-analysis-first-run.md) | First meta-analysis run | Initial patterns identified |

**Most detailed:** [trajectory-analysis-2026-01-23-post-llm-judge.md](./trajectories/trajectory-analysis-2026-01-23-post-llm-judge.md)

---

## Phase Retrospectives

**Focus:** Implementation milestone summaries

| File | Phase | Completion |
|------|-------|-----------|
| [phase1-complete-summary.md](./phases/phase1-complete-summary.md) | Phase 1 | RLM integration, sense cards |
| [phase1-rlm-integration-test-results.md](./phases/phase1-rlm-integration-test-results.md) | Phase 1 | Test results |
| [phase2-reasoning-bank-results.md](./phases/phase2-reasoning-bank-results.md) | Phase 2 | ReasoningBank implementation |

---

## Directory Structure

```
analysis/
├── README.md                              # This file - Start here
│
├── patterns/                              # Design patterns and architecture
│   └── rails-doc-writer-pattern.md
│
├── comparisons/                           # Approach comparisons
│   ├── simple-vs-rlm-tools-comparison.md
│   ├── tool-implementation-comparison.md
│   ├── simple-approach-findings-summary.md
│   └── memory-simple-vs-complex-comparison.md
│
├── eval_runs/                             # Evaluation run analysis
│   ├── baseline-eval-run-2026-01-23.md
│   ├── eval-rerun-post-llm-judge-fix-2026-01-23.md
│   ├── llm-judge-validation-analysis.md
│   ├── dopamine-refusal-fix-2026-01-23.md
│   └── eval-task-complexity-analysis.md
│
├── convergence/                           # Convergence studies
│   ├── COMPLEX_QUERY_CONVERGENCE.md
│   ├── CONVERGENCE_BEHAVIOR_SUMMARY.md
│   └── CONVERGENCE_ANALYSIS.md
│
├── memory/                                # ReasoningBank analysis
│   ├── memory-tracking-findings.md
│   ├── memory-agent-behavior-analysis.md
│   ├── memory-usage-sanity-check.md
│   ├── reasoningbank-overhead-analysis.md
│   ├── reasoningbank-3trial-analysis.md
│   └── seed-heuristics-impact.md
│
├── performance/                           # Performance profiling
│   ├── performance-timing-and-token-analysis.md
│   ├── performance-profiling-results.md
│   └── performance-investigation-plan.md
│
├── tools/                                 # Tool usage analysis
│   ├── tool-usage-inefficiency-analysis.md
│   ├── METADATA_USAGE_ANALYSIS.md
│   └── llm-behavior-with-structured-sense.md
│
├── trajectories/                          # Detailed traces
│   ├── trajectory-analysis-2026-01-23-post-llm-judge.md
│   ├── trajectory-access-patterns-analysis.md
│   ├── ecoli-k12-trajectory-analysis.md
│   └── meta-analysis-first-run.md
│
└── phases/                                # Phase summaries
    ├── phase1-complete-summary.md
    ├── phase1-rlm-integration-test-results.md
    └── phase2-reasoning-bank-results.md
```

---

## Progressive Disclosure Path

**For LLMs exploring this directory:**

### Level 1: Quick Scan (This README)
- TL;DR section - 5 key findings
- Category table - What each area covers

### Level 2: Category Overview
- Pick a category (e.g., Patterns, Memory, Tools)
- Read the category's key files
- Understand specific findings

### Level 3: Detailed Analysis
- Dive into individual markdown files
- See full data, tables, examples
- Understand methodology

### Level 4: Cross-Reference
- Follow connections between analyses
- See how findings relate
- Build comprehensive picture

---

## Recommended Reading Paths

### Path 1: "Why is RLM not faster?"
1. [simple-vs-rlm-tools-comparison.md](./comparisons/simple-vs-rlm-tools-comparison.md) - Architecture differences
2. [trajectory-access-patterns-analysis.md](./trajectories/trajectory-access-patterns-analysis.md) - 60% wasted effort
3. [tool-usage-inefficiency-analysis.md](./tools/tool-usage-inefficiency-analysis.md) - Specific inefficiencies
4. [rails-doc-writer-pattern.md](./patterns/rails-doc-writer-pattern.md) - Alternative approach

**Answer:** Agents spend time rediscovering what's already documented. Load context upfront instead.

### Path 2: "Is memory worth it?"
1. [memory-tracking-findings.md](./memory/memory-tracking-findings.md) - Overhead measurement
2. [memory-simple-vs-complex-comparison.md](./comparisons/memory-simple-vs-complex-comparison.md) - When it helps
3. [reasoningbank-overhead-analysis.md](./memory/reasoningbank-overhead-analysis.md) - Performance impact
4. [seed-heuristics-impact.md](./memory/seed-heuristics-impact.md) - Optimization strategies

**Answer:** Yes for repetitive/complex tasks, needs optimization for cold-start.

### Path 3: "How reliable are evals?"
1. [llm-judge-validation-analysis.md](./eval_runs/llm-judge-validation-analysis.md) - Judge accuracy
2. [baseline-eval-run-2026-01-23.md](./eval_runs/baseline-eval-run-2026-01-23.md) - Baseline results
3. [eval-rerun-post-llm-judge-fix-2026-01-23.md](./eval_runs/eval-rerun-post-llm-judge-fix-2026-01-23.md) - Improvements
4. [eval-task-complexity-analysis.md](./eval_runs/eval-task-complexity-analysis.md) - Task types

**Answer:** LLM judge is 95% accurate, evals are reliable regression tests.

---

## Related Documentation

- **Experiments:** [../../experiments/](../../experiments/) - Active experiments (agent guide generation)
- **Design Docs:** [../design/](../design/) - Architecture specifications
- **Planning:** [../planning/](../planning/) - Roadmaps and trajectories
- **Tasks:** [../tasks/](../tasks/) - Implementation tasks

---

## Contributing Analysis

When adding new analysis documents:

1. **Naming:** Use descriptive lowercase-with-hyphens names
2. **Date:** Include date in filename for time-series analyses (YYYY-MM-DD)
3. **Category:** Place in appropriate subdirectory
4. **Cross-reference:** Link to related analyses
5. **Update README:** Add entry in the appropriate category table

**Example:** `memory-retrieval-optimization-2026-01-25.md` → `memory/` directory
