# Prototype Code (Exploratory, Not Production)

This directory contains **exploratory prototype code** from the research phase.

## ⚠️ Important

This code is for **reference only**, not production use.

## Purpose

- Rapid experimentation to test hypotheses
- Validate design patterns (handle pattern, layer cake, two-phase retrieval)
- Discover what works before engineering investment
- Prove/disprove architectural assumptions

## Structure

```
core/        - Foundation: BlobRef, MemStore, instrumentation (~270 LOC)
packers/     - Layer packers: L0-L3 formatters (~200 LOC)
ctx/         - Context builder: layer cake assembler (~90 LOC)
metrics/     - Trajectory diversity, leakage metrics (~200 LOC)
tools/       - SPARQL, endpoint, memory tools (~400 LOC)
run/         - Experiment runners for DSPy RLM (~290 LOC)
```

**Total**: ~1300 LOC

## Usage

### For Current Research

✅ Run experiments via `run/` modules
✅ Add new metrics to `metrics/`
✅ Test new packers in `packers/`
✅ Debug with existing code

### For Future Production

✅ Extract patterns from `03_FINDINGS/validated_patterns/`
✅ Reference this code for implementation details
✅ Follow `04_EXTRACTION_GUIDE/` protocol

❌ Do NOT refactor or productionize this code directly
❌ Do NOT import from this directory in production packages
❌ Do NOT treat this as stable API

## Why Not Refactor?

From `00_FOUNDATIONS/IMPLEMENTATION_PLAN.md`:

> "The existing `rlm_runtime` code embodies assumptions we want to *test*, not assume. This experiment suite builds fresh implementations that directly test the hypotheses."

The same logic applies here: These prototypes embody **experimental assumptions**. Future production code should extract the validated patterns and implement cleanly, not inherit experimental baggage.

## Key Modules

### core/blob.py
**Purpose**: Handle pattern - wrap large data in references
**Status**: ✅ Validated (E7b: 52% leakage reduction)
**Extract to**: Core abstraction for production

### core/mem.py
**Purpose**: Minimal in-memory store with two-phase retrieval
**Status**: ✅ Validated (prevents unbounded context)
**Extract to**: Memory substrate design

### packers/l0_sense.py
**Purpose**: Ontology sense card (~600 chars)
**Status**: ✅ Validated (E2: enables tool usage)
**Extract to**: Metadata extractor

### packers/l1_schema.py
**Purpose**: Schema constraints + anti-patterns
**Status**: ✅ Validated (improves correctness)
**Extract to**: Constraint validator

### metrics/diversity.py
**Purpose**: Trajectory diversity metrics (Vendi Score, Jaccard)
**Status**: ✅ Validated (S3: mathematically correct)
**Extract to**: Evaluation framework

### run/rlm_uniprot.py
**Purpose**: Remote SPARQL endpoint runner
**Status**: ✅ Working (Phase 1 runs)
**Extract to**: Execution engine

## Implementation Lessons

### 1. DSPy RLM Tool Calling Convention

**Critical discovery**: Tools must use signature `lambda args, kwargs: ...` not `*args, **kwargs`.

See `00_FOUNDATIONS/IMPLEMENTATION_PLAN.md` "Implementation Lessons Learned" for details.

### 2. Context Impact on Tool Usage

Empty context (E1) → 0 tool calls (LLM uses training data)
Sense card (E2) → 5-7 tool calls (LLM explores with tools)

**Lesson**: Context layers actively guide tool discovery.

### 3. API Defaults Matter

Increasing `sparql_peek` default 5→20 rows reduced iterations by 50% (protein_properties task: 10→5 iterations).

**Lesson**: Tool design is as important as memory content.

## Architecture

See [00_FOUNDATIONS/IMPLEMENTATION_PLAN.md](../00_FOUNDATIONS/IMPLEMENTATION_PLAN.md) for:
- Module specifications
- Design rationale
- LOC budget
- Naming conventions (Huffman coding)
- Verification checklists

## Changes During Research

This code evolved during research:

- ✅ L0 enhanced: Widoco-inspired metadata (15+ vocabularies)
- ✅ L1 enhanced: Anti-patterns, property characteristics, cardinality
- ✅ L2 enhanced: Polarity filtering, separate success/failure packing
- ✅ Metrics added: Diversity, trajectory analysis, forking points
- ✅ UniProt runner: Remote SPARQL endpoint support
- ✅ Memory reflection: Human-in-the-loop augmentation

Total grew from ~960 LOC (planned) → ~1300 LOC (actual).

## Testing

```bash
# Smoke tests
python tests/smoke/test_basic.py

# Integration tests
python tests/integration/test_full_layer_cake.py

# Unit tests
python tests/unit/test_l0_comparison.py
```

---

**Last updated**: 2026-02-04
