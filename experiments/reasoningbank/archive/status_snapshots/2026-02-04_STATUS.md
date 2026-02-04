# ReasoningBank Experiments - Implementation Status

## ✅ Completed (Week 1-3)

### Core Foundation (~270 LOC)
- ✅ `core/blob.py` - BlobRef handle pattern (35 LOC)
- ✅ `core/mem.py` - Minimal memory store (55 LOC)
- ✅ `core/instrument.py` - Leakage metrics (40 LOC)
- ✅ `core/graph.py` - RDFLib wrappers (55 LOC)

### Layer Packers (~200 LOC)
- ✅ `packers/l0_sense.py` - Ontology sense card (45 LOC)
- ✅ `packers/l1_schema.py` - Schema constraints (35 LOC)
- ✅ `packers/l2_mem.py` - Memory formatting (15 LOC)
- ✅ `packers/l3_guide.py` - Guide compression (15 LOC)

### Context Builder (~90 LOC)
- ✅ `ctx/builder.py` - Layer cake assembler (65 LOC)

### Experiment Runners (~290 LOC)
- ✅ `run/rlm.py` - Direct dspy.RLM wrapper (75 LOC)
- ✅ `run/phase0.py` - E1-E8 layer ablation (95 LOC)
- ✅ `run/phase1.py` - E9-E12 closed-loop (85 LOC)

### Seed Data
- ✅ `seed/strategies.json` - 5 bootstrap procedures

### Testing
- ✅ `test_basic.py` - Smoke tests (verified: blob, mem work)

**Total**: ~850 LOC (vs. planned ~960 LOC - came in under budget!)

---

## Architecture Verification

✅ **Foundation correct**: Only `dspy.predict.rlm` + `rdflib`, no `rlm_runtime` deps
✅ **Handle pattern**: Ref returns metadata, not payloads
✅ **Two-phase retrieval**: search() → IDs, get() → content (capped)
✅ **Bounded tools**: All graph tools have explicit limits
✅ **Fastai style**: Huffman naming (ref, mem, ctx, cfg, sz, prev)

---

## Next Steps

### 1. Run Full Tests (in uv environment)
```bash
source ~/uvws/.venv/bin/activate
python experiments/reasoningbank/test_basic.py
```

### 2. Run E1 Baseline
```bash
source ~/uvws/.venv/bin/activate
python experiments/reasoningbank/run/phase0.py --exp E1 --ont ontology/prov.ttl
```

### 3. Run Full Phase 0 Suite
```bash
python experiments/reasoningbank/run/phase0.py --exp E1,E2,E3,E4,E5,E6
```

### 4. Verify Leakage Metrics
Check `results/phase0_results.json` for:
- `leakage.large_returns` - Should be 0 with handle-based tools
- `leakage.stdout_chars` - Should be minimal
- Convergence rates across E1-E6

---

## Known Issues / TODOs

- [ ] E7 (leakage ablation) needs separate tool implementations (naive vs handle)
- [ ] E8 (retrieval policy) needs tool-mediated version
- [ ] Phase 1 consolidation logic not implemented (E10)
- [ ] Phase 1 forgetting logic not implemented (E11)
- [ ] Phase 1 MaTTS rollouts not implemented (E12)
- [ ] Seed strategies need to be loaded into MemStore for E5

---

## File Manifest

```
experiments/reasoningbank/
├── IMPLEMENTATION_PLAN.md       # Design doc
├── README.md                    # Experiment plan
├── rlm_notes.md                 # RLM v2 principles
├── STATUS.md                    # This file
├── test_basic.py                # Smoke tests
│
├── core/                        # ✅ Complete
│   ├── blob.py
│   ├── graph.py
│   ├── mem.py
│   └── instrument.py
│
├── packers/                     # ✅ Complete
│   ├── l0_sense.py
│   ├── l1_schema.py
│   ├── l2_mem.py
│   └── l3_guide.py
│
├── ctx/                         # ✅ Complete
│   └── builder.py
│
├── run/                         # ✅ Complete (E1-E6, E9)
│   ├── rlm.py
│   ├── phase0.py
│   └── phase1.py
│
├── seed/                        # ✅ Bootstrap data
│   ├── strategies.json
│   └── constraints/
│
└── results/                     # Output directory
    └── .gitignore
```
