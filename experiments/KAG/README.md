# KAG: Agentic Knowledge-Augmented Generation (RLM-Based)

## Overview

This experiment implements **agentic document understanding** using RLM principles to build hierarchical knowledge graphs from scientific papers. Unlike the original KAG architecture which uses LLM workflow patterns, this is a **fully agentic multi-agent system** with local memory layers.

**Goal:** Build document graphs agentically from DeepSeek OCR outputs, enabling multi-hop reasoning and figure understanding.

## Why This Experiment?

### Original KAG (from KAG notebooks)
- LLM workflow: `text → llm.extract_entities() → graph.add()`
- Hardcoded extraction rules
- Domain-specific (requires rewriting for new domains)
- No memory/learning

### RLM-Based KAG (This Experiment)
- Multi-agent reasoning: Agents decide structure, not hardcoded rules
- Memory layers (L0-L4): Deterministic analysis → Learned strategies
- Domain-agnostic: Same agents work on chemistry, medical, technical docs
- Handle-based: No payload leakage, bounded access
- Learns from failures: Accumulates parsing strategies

## Architecture

### Multi-Agent Pipeline

```
Input: DeepSeek OCR Markdown
    ↓
┌─────────────────────────────────────┐
│ L0: OCR Sense (Deterministic)       │ ← Fast metadata extraction
│ - Page count, detection types       │ ← No LLM needed
│ - Inferred document type            │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Agent 1: StructureParser            │ ← Reasons about hierarchy
│ - Parses detection tags             │ ← Builds DocumentTree
│ - Returns: DocumentTreeRef (handle) │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Agent 2: HierarchicalSummarizer     │ ← Multi-level summaries
│ - Bottom-up (leaf → root)           │ ← Coarse → fine
│ - Returns: SummaryTreeRef (handle)  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Agent 3: RelationExtractor          │ ← Links elements
│ - Section ↔ Figure ↔ Table          │ ← Semantic relations
│ - Returns: RelationGraphRef (handle)│
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Agent 4: KGConstructor              │ ← Builds RDF graph
│ - Document + Fact graphs            │ ← PROV provenance
│ - Returns: KnowledgeGraphRef        │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Judge: StructureValidator           │ ← Quality check
│ - Validates completeness            │ ← Learns from failures
│ - Returns: ValidationReport         │
└─────────────────────────────────────┘
```

### Memory Layers (Following reasoningbank pattern)

**L0: OCR Sense** (Deterministic, Fast)
```python
{
    "page_count": 8,
    "detection_types": ["title", "text", "equation", "image"],
    "inferred_type": "research_paper",
    "has_equations": True
}
```

**L1: Document Schema** (Constraints)
```python
{
    "type": "research_paper",
    "expected_structure": {
        "Document": ["Section"],
        "Section": ["Paragraph", "Figure", "Equation"]
    }
}
```

**L2: Procedural Memory** (Learned Strategies)
```python
{
    "pattern": "chemistry_paper_with_equations",
    "parse_steps": ["Group equations with text", "Link figures by proximity"],
    "success_count": 15
}
```

**L3: Materialized Guides** (Packed Summaries)
```
"8-page chemistry paper. IMRaD format. 12 equations, 6 figures."
```

**L4: Trajectories** (Logged, not injected)
```jsonl
{"event": "agent_start", "agent": "StructureParser", ...}
{"event": "tool_call", "tool": "parse_detection_tags", ...}
```

## RLM Principles (Following owl/ patterns)

### Handles Not Payloads

```python
# ❌ BAD: Payload leakage
page_content = file.read_text()  # 10KB text
agent(page_content=page_content)  # Injected into context!

# ✅ GOOD: Handle-based
page_ref = blob_store.store(file.read_text())  # ContentRef
agent(page_ref=page_ref)  # Only handle (50 bytes) in context
```

### Bounded Access

```python
# Tools return bounded previews, not full content
def get_page_content(page_ref: ContentRef, max_chars: int = 500) -> str:
    full_content = blob_store.retrieve(page_ref)
    return full_content[:max_chars]  # Bounded!
```

### Safe Repr

```python
@dataclass
class ContentRef:
    ref_id: str
    size_bytes: int

    def __repr__(self):
        # Safe - doesn't leak payload
        return f"ContentRef({self.ref_id}, {self.size_bytes}B)"
```

### Trajectory Logging

```python
logger.log("tool_call", {
    "tool": "parse_detection_tags",
    "page_ref": str(page_ref),  # Handle, not content
    "tags_found": len(tags)
})
```

## File Structure (Following owl/ and reasoningbank/)

```
KAG/
├── README.md                      # This file
├── test_data/                     # Test documents (copied from techindex-exp)
│   ├── chemrxiv_ocr/
│   ├── pet_test_ocr/
│   └── omd_test_ocr/
│
├── Core Components
├── agentic_kag_runner.py          # Main runner (like agentic_owl_runner.py)
├── agentic_doc_agents.py          # 5 agents (Parser, Summarizer, etc.)
├── agentic_doc_tools.py           # Bounded tools for agents
├── kag_memory.py                  # Memory layers (L0-L4)
├── symbolic_handles.py            # Handle store (similar to owl/)
│
├── Schemas & Strategies
├── document_schemas.py            # L1 schemas (research_paper, etc.)
├── parsing_strategies.py          # L2 learned strategies
│
├── Experiment Runs
├── run_kag_0.py                   # Baseline: Single agent
├── run_kag_1.py                   # + L0 optimization
├── run_kag_2.py                   # + L1 schema
├── run_kag_3.py                   # + L2 strategy learning
├── run_kag_full.py                # Full 5-agent pipeline
│
├── Tests
├── test_structure_parser.py       # Unit tests for Agent 1
├── test_rlm_compliance.py         # Leakage tracking
│
└── results/                       # Experiment outputs
    ├── chemrxiv/
    │   ├── blobs/                 # Content behind handles
    │   ├── trajectory.jsonl       # Execution log
    │   ├── document_tree.json     # Built structure
    │   └── knowledge_graph.ttl    # RDF graph
    └── pet_test/
```

## Experiment Progression

### Run 0: Baseline (Prove RLM Compliance)
- Single agent: StructureParser
- Minimal memory (no L2 strategies)
- **Goal:** Parse chemrxiv into DocumentTree without payload leakage
- **Metrics:** stdout_chars < 2000, large_returns = 0

### Run 1: OCR Sense Optimization
- Add L0 analysis for fast orientation
- Cache detection type counts
- **Goal:** Reduce initial exploration overhead by 50%

### Run 2: Schema Guidance
- Add L1 DocumentSchema per inferred type
- Schema validates expected structure
- **Goal:** Catch structural errors early

### Run 3: Strategy Learning
- Add L2 procedural memory
- Extract patterns from successful parses
- **Goal:** Reuse strategies across similar documents

### Run Full: Complete Pipeline
- All 5 agents + Judge
- Full memory layers (L0-L4)
- **Goal:** Build complete KG with provenance

## Integration Points

### With Original KAG Notebooks
```python
# Use agentic output in KAG notebooks
from rlm.experiments.KAG.agentic_kag_runner import run_pipeline

result = run_pipeline("test_data/chemrxiv_ocr")
document_tree = result["document_tree"]  # Handle

# Build LLMFriSPG on top
build_llmfrispg(document_tree)
```

### With RLM+OWL System
```python
# Store learned strategies in OWL memory
from rlm.experiments.owl.owl_memory import OwlMemoryStore

memory = OwlMemoryStore()
memory.add_procedure(
    title="Parse chemistry papers",
    compiled_fields=strategy.parse_steps,
    content_ref=blob_store.store(full_strategy)
)
```

## Success Criteria

### RLM Compliance
- [ ] All content behind handles
- [ ] Bounded access (max_chars enforced)
- [ ] Safe repr() - no payload leakage
- [ ] Trajectory logging complete
- [ ] stdout_chars < 2000
- [ ] large_returns = 0

### Agentic Behavior
- [ ] No hardcoded rules (agents reason)
- [ ] Domain-agnostic (works on chem, medical, tech docs)
- [ ] Learns strategies (L2 accumulation)
- [ ] Self-validates (Judge catches errors)

### Output Quality
- [ ] Correct hierarchy (Document → Section → Paragraph)
- [ ] Figures linked to captions
- [ ] Equations grouped with text
- [ ] Multi-level summaries (coarse → fine)
- [ ] Full provenance (fact → source)

## Next Steps

1. ✅ Copy test data from techindex-exp
2. ⬜ Implement symbolic_handles.py (following owl/)
3. ⬜ Implement kag_memory.py (L0-L4 layers)
4. ⬜ Implement agentic_doc_tools.py (bounded tools)
5. ⬜ Implement Agent 1 (StructureParser)
6. ⬜ Create run_kag_0.py baseline experiment
7. ⬜ Test on chemrxiv → validate RLM compliance
8. ⬜ Implement remaining agents (2-5)
9. ⬜ Test on all three papers
10. ⬜ Extract learned strategies → L2 memory

## References

- Original KAG: https://arxiv.org/html/2409.13731v3
- DeepSeek-OCR-2: Uses semantic detection tags for structure
- RLM patterns: `../owl/` and `../reasoningbank/`
- PROV-O: W3C provenance ontology
