# Experiment Results

This directory contains all generated agent guides and analysis from the agent_guide_generation experiment.

## Quick Start

**Latest Results:** See [`latest/`](./latest/) for symlinks to the most recent successful runs.

**Summary:** See [`analysis/SUMMARY.md`](./analysis/SUMMARY.md) for quick metrics and rankings.

**Detailed Comparison:** See [`analysis/uniprot_comparison.md`](./analysis/uniprot_comparison.md) for LLM judge analysis.

## Directory Structure

```
results/
├── README.md                              # This file
├── latest/                                # Symlinks to latest successful runs
│   ├── prov_direct.md
│   ├── prov_react.md
│   ├── prov_rlm.md
│   ├── prov_scratchpad.md
│   ├── uniprot_direct.md
│   ├── uniprot_react.md
│   ├── uniprot_rlm.md
│   └── uniprot_scratchpad.md
│
├── analysis/                              # Summary analysis and comparisons
│   ├── SUMMARY.md                         # Quick metrics table
│   └── uniprot_comparison.md              # LLM judge detailed comparison
│
├── runs/                                  # Future: timestamped run archives
│   └── archive/
│
└── [timestamped files]                    # All generated guides and metadata
    ├── prov_AGENT_GUIDE_*.md
    ├── prov_*_metadata_*.json
    ├── uniprot_AGENT_GUIDE_*.md
    └── uniprot_*_metadata_*.json
```

## File Naming Convention

```
{ontology}_AGENT_GUIDE_{approach}_{timestamp}.md
{ontology}_{approach}_metadata_{timestamp}.json
{ontology}_comparison_{timestamp}.md
{ontology}_all_comparison_{timestamp}.json
```

**Where:**
- `{ontology}` = prov | uniprot | ...
- `{approach}` = direct | rlm | react | scratchpad
- `{timestamp}` = YYYYMMDD_HHMMSS

## Ontologies Tested

### PROV (112K chars)
- **Purpose:** W3C provenance standard (entities, activities, agents)
- **Size:** Small, fits in Direct LLM prompt
- **Winner:** Scratchpad (2x more comprehensive)

### UniProt (139K chars)
- **Purpose:** Protein knowledge base ontology
- **Size:** Large, exceeds Direct LLM 50K limit
- **Winner:** Scratchpad (completeness) / DSPy ReAct (affordances)

## Approaches Compared

1. **Direct LLM** - Full ontology in single prompt (fast, limited by 50K)
2. **RLM** - DSPy RLM with bounded tools + code execution (comprehensive, slow)
3. **DSPy ReAct** - Structured tool calls without REPL (efficient, good affordances)
4. **Scratchpad** - Persistent namespace + incremental assembly (best for large ontologies)

## Key Findings

### Context Management Matters
- Direct LLM **fails on large ontologies** (truncated input)
- Scratchpad **succeeds through chunking** (persistent namespace)

### Affordances > Completeness
- LLM judge prefers DSPy ReAct's "HOW to use" guidance
- RLM's exhaustive enumeration deemed "overwhelming"

### Scratchpad Pattern Works
- **2x more comprehensive** than other iterative approaches
- **39 namespace variables** on UniProt (active context management)
- **Incremental assembly** builds better structure

## Progressive Disclosure Example

To understand results, follow this path:

1. **Start here:** [analysis/SUMMARY.md](./analysis/SUMMARY.md) - Quick metrics
2. **Browse guides:** [latest/](./latest/) - Read generated guides
3. **Deep dive:** [analysis/uniprot_comparison.md](./analysis/uniprot_comparison.md) - LLM judge analysis
4. **Reproduce:** [../agent_guide_generation/](../agent_guide_generation/) - Run experiments

## Reproducing Results

```bash
# Run all approaches on PROV
python experiments/agent_guide_generation/agent_guide_comparison_all.py prov ontology/prov.ttl

# Run single approach on UniProt
python experiments/agent_guide_generation/agent_guide_scratchpad.py uniprot ontology/uniprot/core.ttl
```

Results will be saved with timestamps in this directory.
