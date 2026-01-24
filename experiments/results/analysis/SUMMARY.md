# Experiment Results Summary

Quick reference to experiment results and key findings.

## Latest Results

**Access latest guides via symlinks:** [`../latest/`](../latest/)

| Ontology | Direct LLM | RLM | DSPy ReAct | Scratchpad |
|----------|-----------|-----|------------|------------|
| **PROV** | [prov_direct.md](../latest/prov_direct.md) | [prov_rlm.md](../latest/prov_rlm.md) | [prov_react.md](../latest/prov_react.md) | [prov_scratchpad.md](../latest/prov_scratchpad.md) |
| **UniProt** | [uniprot_direct.md](../latest/uniprot_direct.md) | [uniprot_rlm.md](../latest/uniprot_rlm.md) | [uniprot_react.md](../latest/uniprot_react.md) | [uniprot_scratchpad.md](../latest/uniprot_scratchpad.md) |

## Key Metrics

### PROV (Small Ontology - 112K chars)

| Approach | Time | Lines | Winner |
|----------|------|-------|--------|
| Direct LLM | 30.6s | 189 | ⚡ Speed |
| RLM | 144.7s | 241 | |
| DSPy ReAct | 72.9s | 221 | |
| Scratchpad | 161.1s | **383** | 🏆 Comprehensive |

### UniProt (Large Ontology - 139K chars)

| Approach | Time | Lines | Winner |
|----------|------|-------|--------|
| Direct LLM | 24.0s | **129** | ❌ Truncated |
| RLM | 100.8s | 190 | |
| DSPy ReAct | 68.2s | 201 | 🏆 Affordances (LLM Judge) |
| Scratchpad | 155.1s | **379** | 🏆 Comprehensive |

## Winner Analysis

### PROV (Small)
- **Scratchpad wins** - 2x more comprehensive than Direct LLM
- **Direct LLM acceptable** - If speed matters, 6x faster

### UniProt (Large)
- **Scratchpad wins on completeness** - Only approach handling full ontology
- **DSPy ReAct wins on affordances** - LLM judge: "Best practical guidance"
- **Direct LLM fails** - Truncated to 50K chars, missing 64% of content

## Design Pattern Winners

| Pattern | Approach | Wins On |
|---------|----------|---------|
| **Rails** (load upfront) | Direct LLM, Scratchpad | Small ontologies, speed |
| **Progressive Disclosure** | RLM, DSPy ReAct | Scalability |
| **Scratchpad** (incremental) | Scratchpad | Large ontologies, comprehensiveness |

## Recommendations

```
Ontology Size     → Recommended Approach
───────────────────────────────────────
< 50K chars       → Direct LLM (speed) or Scratchpad (quality)
50-150K chars     → Scratchpad (handles full context)
> 150K chars      → Scratchpad (only viable option)
```

## Detailed Analysis

- **UniProt Comparison:** [uniprot_comparison.md](./uniprot_comparison.md)
- **Main README:** [../../README.md](../../README.md)
- **Experiment Details:** [../../agent_guide_generation/README.md](../../agent_guide_generation/README.md)
