# AGENT_GUIDE.md Generation Experiments

This directory contains experiments comparing different approaches for generating AGENT_GUIDE.md documentation for ontologies.

## Four Approaches

### 1. Direct LLM (Baseline)
**File:** `agent_guide_generation.py` - `approach_1_direct_llm()`

- **Method:** Single prompt with full ontology content (first 50K chars)
- **Model:** Claude Sonnet 4
- **No REPL, no tools**
- **Strengths:**
  - Fast (~30 seconds for PROV)
  - Can see full ontology structure at once
  - Good at generating affordance-focused guidance
- **Weaknesses:**
  - Limited to 50K chars of ontology
  - No runtime exploration capability
  - Single-shot, no iterative refinement

### 2. RLM-based (Recursive Exploration)
**File:** `agent_guide_generation.py` - `approach_2_rlm_based()`

- **Method:** Iterative exploration with DSPy RLM + bounded tools
- **Tools:** `search_entity`, `sparql_select`
- **REPL:** NamespaceCodeInterpreter (code execution)
- **Max Iterations:** 8
- **Strengths:**
  - Systematic exploration of ontology structure
  - Can handle large ontologies (not limited by prompt size)
  - Discovers patterns through exploration
- **Weaknesses:**
  - Slow (~145 seconds for PROV, 5x slower than direct)
  - Context accumulation overhead (trajectory grows unbounded)
  - May spend time on exploration that doesn't improve guide

### 3. DSPy ReAct (Structured Tool Use)
**File:** `agent_guide_dspy_react.py` - `approach_3_dspy_react()`

- **Method:** DSPy ReAct pattern with tools (non-recursive)
- **Tools:** `search_entity`, `sparql_query`, `get_class_info`
- **No REPL** - pure function calls
- **Max Iterations:** 8
- **Strengths:**
  - Structured approach (not fully recursive like RLM)
  - Tool-based exploration without REPL overhead
  - DSPy's ReAct pattern for tool selection
- **Weaknesses:**
  - Still tool-based (may have similar overhead to RLM)
  - Not as fast as direct LLM
  - No persistent state across tool calls

### 4. Scratchpad (Original RLM Design)
**File:** `agent_guide_scratchpad.py` - `approach_4_scratchpad()`

- **Method:** Persistent namespace with direct function calls (like original `rlm/core.py`)
- **REPL:** Full code execution in persistent namespace
- **Functions:** `search_entity`, `sparql_query`, `get_classes`, `get_properties`, `llm_query`
- **Rich upfront context:** Ontology metadata + GraphMeta in namespace
- **Max Iterations:** 10
- **Strengths:**
  - **Scratchpad model** - variables persist across iterations
  - Direct function calls (no tool wrappers)
  - Lightweight history (truncated at 20K chars)
  - Can use `llm_query()` for sub-LLM analysis
  - Builds up state incrementally
- **Weaknesses:**
  - Still iterative (may be slower than direct LLM)
  - Requires code execution

## Key Differences

| Aspect | Direct LLM | RLM | DSPy ReAct | Scratchpad |
|--------|-----------|-----|------------|------------|
| **Context** | Full ontology | Minimal stats | Stats + tools | Rich metadata |
| **REPL** | None | Heavy (interpreter) | None | Lightweight |
| **Namespace** | None | Per-iteration | None | **Persistent** |
| **Tools** | None | Wrapped | Functions | **Direct in ns** |
| **History** | Single prompt | Unbounded trajectory | ReAct history | **Truncated 20K** |
| **Speed** | Fast (~30s) | Slow (~145s) | Medium (TBD) | Medium (TBD) |
| **Scalability** | Limited (50K) | Unlimited | Unlimited | Unlimited |
| **Model** | Rails pattern | Current RLM | Pure ReAct | **Original RLM** |

## Running Experiments

### Quick Tests (Individual Approaches)
```bash
# Test DSPy ReAct
python experiments/test_dspy_react.py

# Test Scratchpad (original rlm/core.py style)
python experiments/test_scratchpad.py
```

### Run Single Approach
```bash
# Direct LLM only
python experiments/agent_guide_generation.py prov ontology/prov.ttl

# DSPy ReAct only
python experiments/agent_guide_dspy_react.py prov ontology/prov.ttl

# Scratchpad only
python experiments/agent_guide_scratchpad.py prov ontology/prov.ttl
```

### Run All Three Approaches
```bash
python experiments/agent_guide_comparison_all.py prov ontology/prov.ttl
```

This will:
1. Run all three approaches
2. Save generated guides to `experiments/results/`
3. Generate an LLM-based comparison
4. Save metadata (timing, tokens, iterations)

### Compare Other Ontologies
```bash
# Small ontology (SKOS)
python experiments/agent_guide_comparison_all.py skos ontology/skos.ttl

# Upper ontology (DUL)
python experiments/agent_guide_comparison_all.py dul ontology/dul/DUL.ttl

# Large ontology (Schema.org)
python experiments/agent_guide_comparison_all.py schema ontology/schemaorg-current-https.ttl
```

## Output Files

All results saved to `experiments/results/`:

- `{ontology}_AGENT_GUIDE_direct_{timestamp}.md` - Direct LLM guide
- `{ontology}_AGENT_GUIDE_rlm_{timestamp}.md` - RLM-based guide
- `{ontology}_AGENT_GUIDE_react_{timestamp}.md` - DSPy ReAct guide
- `{ontology}_all_comparison_{timestamp}.json` - Metadata (timing, tokens, etc.)
- `{ontology}_comparison_{timestamp}.md` - LLM comparison of all approaches

## Hypothesis

Based on initial PROV results and design analysis:

- **Direct LLM wins for speed and affordances** - Better "HOW to use" guidance, ~30s
- **RLM wins for completeness** - More comprehensive coverage (59 classes, 89 properties), but slow (~145s)
- **DSPy ReAct should be lighter than RLM** - Structured exploration without REPL overhead
- **Scratchpad should combine best of both** - Rich context + iterative refinement + lightweight history

The key questions:
1. **Does Scratchpad get the best of both worlds?** (Rails upfront context + iterative refinement)
2. **Is DSPy ReAct faster than RLM?** (no REPL overhead)
3. **Which produces better affordances?** (Direct vs Scratchpad vs RLM vs ReAct)

## Connection to Design Patterns

### Rails Doc Writer Pattern
**Direct LLM** is closest:
- Load everything upfront (full ontology in context)
- No tools needed (everything accessible directly)
- Let LLM traverse structure naturally

### Current rlm_runtime Pattern
**RLM** follows this:
- Minimal upfront context (sense card / metadata)
- Iterative tool-based exploration
- Unbounded trajectory accumulation

### Original rlm/core.py Pattern
**Scratchpad** implements this:
- Rich upfront context (metadata in namespace)
- Persistent scratchpad (variables survive iterations)
- Direct function calls (no tool wrappers)
- Lightweight history (20K truncation)

### Pure ReAct Pattern
**DSPy ReAct** tests this:
- Structured tool use (ReAct pattern)
- Bounded iterations
- No recursive REPL (lighter weight than RLM)
- No persistent state

## Architecture Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPROACH SPECTRUM                            │
└─────────────────────────────────────────────────────────────────────┘

Rich Context ←──────────────────────────────────────→ Minimal Context

┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Direct LLM  │  │  Scratchpad  │  │  DSPy ReAct  │  │     RLM      │
├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
│ Full ontology│  │ Rich metadata│  │ Stats only   │  │ Stats only   │
│ in prompt    │  │ in namespace │  │              │  │              │
│              │  │              │  │              │  │              │
│ No REPL      │  │ Persistent   │  │ No REPL      │  │ Heavy REPL   │
│ No tools     │  │ namespace    │  │ Pure tools   │  │ Tool wrappers│
│              │  │              │  │              │  │              │
│ Single shot  │  │ Direct calls │  │ Structured   │  │ Unbounded    │
│ ~30s         │  │ Lightweight  │  │ calls        │  │ trajectory   │
│              │  │ history      │  │              │  │ ~145s        │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
     ▲                   ▲                  │                  │
     │                   │                  │                  │
     └─── Rails ─────────┘                  └── Current RLM ───┘
         Pattern                                  Pattern
```

## Next Steps

1. ✅ Created all four approaches
2. Test each approach on PROV:
   - ✅ Direct LLM (30s, good affordances)
   - ✅ RLM (145s, comprehensive)
   - ⏳ DSPy ReAct (TBD)
   - ⏳ Scratchpad (TBD - most interesting!)
3. Run comparison on multiple ontologies (PROV, SKOS, DUL)
4. Analyze results:
   - Which produces better affordances?
   - Which is more complete?
   - Which is most efficient?
   - **Does Scratchpad hit the sweet spot?**
5. Consider: Should we replace current RLM with Scratchpad model for certain tasks?
