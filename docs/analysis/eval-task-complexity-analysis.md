# Eval Task Complexity Analysis

**Date:** 2026-01-22
**Purpose:** Identify optimal eval tasks for testing memory system effectiveness
**Current Task:** uniprot_bacteria_taxa_001 (medium complexity, 15 iterations max)

---

## Executive Summary

**Recommendation:** Switch to **basic_search_001** or **prov_activity_subclasses_001** for faster iteration cycles and clearer memory impact.

**Rationale:**
- Current task (bacteria taxa) is relatively complex (15 iter max, remote SPARQL)
- Simpler tasks (3-8 iterations) allow faster experimentation
- Hierarchy tasks test similar patterns (transitive queries) but with faster feedback
- Can run 10 trials in minutes vs hours

**Interesting Alternative:** **uniprot_ecoli_k12_sequences_001** - tests whether memories correctly distinguish transitive vs NON-transitive hierarchies (requires materialized hierarchy awareness)

---

## Task Complexity Matrix

| Task ID | Category | Difficulty | Max Iters | Complexity Factors | Memory Test Value |
|---------|----------|------------|-----------|-------------------|-------------------|
| **basic_search_001** | regression | trivial | 3 | Simple search_entity call | ⭐ Fast baseline |
| **prov_instant_event_001** | entity_discovery | easy | 5 | Entity lookup + describe | ⭐⭐ Entity vs query |
| **prov_activity_subclasses_001** | hierarchy | medium | 8 | Hierarchy navigation | ⭐⭐⭐ Hierarchy patterns |
| **uniprot_bacteria_taxa_001** | uniprot/taxonomy | medium | 15 | Taxonomy + remote SPARQL | ⭐⭐⭐ Current task |
| **uniprot_ecoli_k12_sequences_001** | uniprot/taxonomy | medium | 10 | Taxonomy + sequences + **materialized** | ⭐⭐⭐⭐ Tests transitive awareness |
| **uniprot_rhea_reaction_ec_protein_001** | uniprot/federated | hard | 12 | Federation + SERVICE | ⭐⭐ Complex |
| **uniprot_dopamine_similarity_variants_disease_001** | uniprot/complex | very_hard | 14 | Multi-hop + similarity + federation | ⭐ Too complex |

---

## Detailed Task Analysis

### 1. basic_search_001 (Trivial)

**Query:** "Search for 'Activity' in the PROV ontology and tell me what you find."

**Complexity:**
- ✅ Single ontology (PROV, small)
- ✅ Local only (no remote queries)
- ✅ Max 3 iterations (very fast)
- ✅ Simple tool usage (search_entity)

**Graders:**
- tool_called: search_entity
- convergence: 3 iterations
- groundedness: 0.3 min score

**Memory Test Value:** ⭐ Fast baseline
- Tests if memories HURT simple tasks (over-optimization)
- Quick iteration cycles (3 trials in ~1 minute)
- Clear pass/fail criteria

**Recommendation:** Good for quick sanity check - "do memories break simple tasks?"

---

### 2. prov_instant_event_001 (Easy)

**Query:** "What is prov:InstantaneousEvent and what are its properties?"

**Complexity:**
- ✅ Single ontology (PROV, small)
- ✅ Local only (no remote queries)
- ✅ Max 5 iterations
- ✅ Entity discovery pattern (search → describe)

**Graders:**
- groundedness: require "InstantaneousEvent" evidence
- convergence: 5 iterations
- answer_contains: "event"

**Memory Test Value:** ⭐⭐ Entity vs query strategy
- Tests whether memories guide entity discovery correctly
- Different pattern from SPARQL construction
- Still fast enough for quick experiments

**Recommendation:** Good for testing memory applicability - do learned SPARQL patterns transfer to entity tasks?

---

### 3. prov_activity_subclasses_001 (Medium)

**Query:** "What are the subclasses and superclasses of prov:Activity?"

**Complexity:**
- ✅ Single ontology (PROV, small)
- ✅ Local only (no remote queries)
- ⚠️ Max 8 iterations (moderate)
- ⚠️ Hierarchy navigation (probe_relationships or SPARQL)

**Graders:**
- groundedness: "Activity" evidence
- convergence: 8 iterations
- evidence_pattern: must use probe_relationships or describe_entity with "subclass"

**Memory Test Value:** ⭐⭐⭐ Hierarchy patterns
- Tests same hierarchy patterns as bacteria taxa (transitive queries)
- But simpler (local ontology, no remote complexity)
- Faster feedback loop (8 iterations vs 15)
- Memories about hierarchy should directly apply

**Recommendation:** ⭐ **BEST CHOICE for next memory experiment**
- Tests key memory patterns (hierarchy navigation)
- Fast iteration (8 iters max)
- Clear success criteria
- Same domain as current learned memories (hierarchy)

---

### 4. uniprot_bacteria_taxa_001 (Medium) ← CURRENT

**Query:** "Select all bacterial taxa and their scientific name from UniProt taxonomy."

**Complexity:**
- ⚠️ Local ontology + remote SPARQL endpoint
- ⚠️ Max 15 iterations
- ⚠️ Requires understanding remote vs local
- ⚠️ Taxonomy hierarchy navigation
- ⚠️ SPARQL construction

**Graders:**
- convergence: 15 iterations
- outcome_verification: min 3 results with taxon + scientificName
- llm_judge: semantic correctness

**Memory Test Value:** ⭐⭐⭐ Current task
- Already have 25 memories specific to this task
- Good for testing full memory system
- BUT: slow iteration cycles (15 iterations, remote queries)

**Issues Found:**
- Only 1/3 trials followed transitive query guidance
- Average performance slightly worse than baseline (11.0 vs 10.2 iters)
- Sample size too small (3 trials) for statistical significance

**Recommendation:** Continue with this if want to test full complexity, or switch to simpler task for faster iteration.

---

### 5. uniprot_ecoli_k12_sequences_001 (Medium)

**Query:** "Select UniProtKB proteins (and their amino acid sequences) for E. coli K12 and all its strains."

**Complexity:**
- ⚠️ Local ontology + remote SPARQL endpoint
- ⚠️ Max 10 iterations (faster than bacteria taxa)
- ⚠️ Taxonomy hierarchy navigation
- ⚠️ Sequence extraction (additional property)
- ⚠️ **CRITICAL: Requires NON-transitive hierarchy (materialized)**

**Graders:**
- convergence: 10 iterations
- outcome_verification: min 3 results with protein + sequence (amino acids)
- llm_judge: CRITICAL note about NON-transitive hierarchy
- tool_called: sparql_query

**Exemplar Note:**
```yaml
# Note: Materialized - do NOT use rdfs:subClassOf+
```

**Memory Test Value:** ⭐⭐⭐⭐ **Tests transitive awareness!**
- Similar to bacteria taxa but with critical difference
- Tests whether memories correctly distinguish:
  - "Find all bacteria" → USE transitive (rdfs:subClassOf+)
  - "Find all E. coli K12 strains" → DON'T USE transitive (materialized)
- If memories are too prescriptive ("always use transitive"), they'll fail this task
- Excellent test of memory specificity vs generalization

**Recommendation:** ⭐ **EXCELLENT FOLLOW-UP TEST**
- Run this AFTER establishing baseline on simpler tasks
- Tests critical edge case: when NOT to follow general guidance
- Will reveal if seed heuristics are too rigid

---

### 6. uniprot_rhea_reaction_ec_protein_001 (Hard)

**Query:** "For a given Rhea reaction, retrieve the EC and reviewed UniProt proteins (federated from Rhea to UniProt)."

**Complexity:**
- ❌ Federation required (SERVICE keyword)
- ❌ Two endpoints (Rhea + UniProt)
- ⚠️ Max 12 iterations
- ⚠️ Complex SERVICE pattern

**Graders:**
- sparql_structural: requires_service ["sparql.uniprot.org"]
- outcome_verification: EC + protein fields
- llm_judge: federation approach

**Memory Test Value:** ⭐⭐ Complex, different domain
- Federation is new pattern (no existing memories)
- Would test memory transfer to new task type
- BUT: slower, more complex

**Recommendation:** Later phase - test memory transfer to federation tasks

---

### 7. uniprot_dopamine_similarity_variants_disease_001 (Very Hard)

**Query:** "Find reviewed proteins catalyzing reactions involving dopamine-like molecules, with natural variants related to a disease."

**Complexity:**
- ❌ Similarity search (sachem:similarCompoundSearch)
- ❌ Multiple federation (CHEBI service + Rhea GRAPH)
- ❌ Multi-hop reasoning (dopamine → reactions → enzymes → variants → diseases)
- ❌ Max 14 iterations
- ❌ Very complex SPARQL patterns

**Graders:**
- sparql_structural: requires_service ["elixir-czech.cz"]
- outcome_verification: proteins with variants + diseases
- llm_judge: highly complex evaluation

**Memory Test Value:** ⭐ Too complex for memory testing
- Likely fails even without memory system
- Too many failure modes to isolate memory impact
- Better for research questions (reasoning boundaries) than memory testing

**Recommendation:** Skip for memory experiments - use for Phase 6 (reasoning boundary) research

---

## Recommendations by Testing Goal

### Goal: Quick memory sanity check (5 minutes)
**Task:** `basic_search_001` (trivial, 3 iterations)
**Why:** Verify memories don't break simple tasks
**Command:**
```bash
python -m evals.cli run 'regression/basic_search_001' --trials 5 --enable-memory
```

### Goal: Test hierarchy pattern learning (10 minutes)
**Task:** `prov_activity_subclasses_001` (medium, 8 iterations)
**Why:** Same patterns as bacteria taxa, faster feedback
**Command:**
```bash
python -m evals.cli run 'hierarchy/prov_activity_subclasses_001' --trials 10 --enable-memory
```

### Goal: Test memory specificity (transitive vs non-transitive)
**Task:** `uniprot_ecoli_k12_sequences_001` (medium, 10 iterations)
**Why:** Tests whether memories correctly distinguish when NOT to use transitive
**Command:**
```bash
python -m evals.cli run 'uniprot/taxonomy/uniprot_ecoli_k12_sequences_001' --trials 5 --enable-memory
```

### Goal: Continue current experiment (30+ minutes)
**Task:** `uniprot_bacteria_taxa_001` (medium, 15 iterations)
**Why:** Already have 25 memories, want to see consistency with larger sample
**Command:**
```bash
python -m evals.cli run 'uniprot/taxonomy/uniprot_bacteria_taxa_001' --trials 10 --enable-memory
```

---

## Optimal Testing Strategy

**Phase 1: Fast validation (15 minutes)**
1. Run `basic_search_001` (5 trials) - verify no harm on simple tasks
2. Run `prov_activity_subclasses_001` (10 trials) - test hierarchy learning

**Expected outcome:**
- basic_search should pass 100% with or without memory (regression test)
- Activity subclasses should show improvement if memories help with hierarchy

**Phase 2: Edge case testing (15 minutes)**
3. Run `uniprot_ecoli_k12_sequences_001` (5 trials) - test transitive awareness

**Expected outcome:**
- If memories are too prescriptive ("always use transitive"), this will fail
- If memories correctly contextualize, should pass by using NON-transitive

**Phase 3: Full experiment (30+ minutes)**
4. Run `uniprot_bacteria_taxa_001` (10 trials) - establish statistical significance

**Expected outcome:**
- Larger sample to determine if Trial 2's success (9 iterations with transitive) is consistent
- Answer: Do memories help 30%, 50%, or 100% of trials?

---

## Comparison: Current Task vs Recommended Alternatives

| Metric | bacteria_taxa (current) | prov_activity_subclasses | ecoli_k12_sequences |
|--------|-------------------------|--------------------------|---------------------|
| **Max iterations** | 15 | 8 | 10 |
| **Complexity** | Remote + local | Local only | Remote + local |
| **Feedback speed** | Slow (~3 min/trial) | Fast (~1 min/trial) | Medium (~2 min/trial) |
| **Memory pattern** | Transitive hierarchy | Transitive hierarchy | NON-transitive (edge case) |
| **Existing memories** | 25 (specific to task) | Transferable | Transferable |
| **Test value** | Current baseline | Faster iteration | Edge case detection |

**Winner:** `prov_activity_subclasses_001` for next experiment
- **2-3x faster** than bacteria taxa
- Tests **same hierarchy patterns** memories are about
- **Local only** - removes remote query variability
- Can run **10 trials in 10 minutes** vs 30+ minutes

---

## Implementation Notes

### Running Alternative Tasks

All tasks are already configured in `evals/tasks/` directory.

**Check available tasks:**
```bash
python -m evals.cli list
```

**Run specific task:**
```bash
# Quick test
python -m evals.cli run 'hierarchy/prov_activity_subclasses_001' --trials 3 --enable-memory

# Full experiment
python -m evals.cli run 'hierarchy/prov_activity_subclasses_001' --trials 10 --enable-memory
```

### Memory Considerations

**Current memory database:** 25 memories
- 4 human seeds (transferable: hierarchy, taxonomy, SPARQL)
- 3 meta-analysis patterns (transferable: exploration, consistency)
- 18 single-trajectory (specific to bacteria taxa)

**For new tasks:**
- Human seeds WILL apply (generic hierarchy guidance)
- Meta-analysis patterns WILL apply (exploration patterns)
- Single-trajectory memories MAY apply (if similar task)

**Memory retrieval:** BM25 will surface relevant memories based on query similarity.

Query: "What are the subclasses of prov:Activity?"
- Will retrieve: "Hierarchical Property Testing", "Task Scope Recognition"
- Won't retrieve: UniProt-specific memories

---

## Conclusion

**Primary Recommendation:** Switch to `prov_activity_subclasses_001` for next memory experiment

**Reasons:**
1. **2-3x faster** iteration cycles (8 vs 15 iterations)
2. **Same patterns** (hierarchy navigation, transitive queries)
3. **Simpler environment** (local only, no remote variability)
4. **Existing memories transfer** (human seeds + meta-analysis)

**Secondary Recommendation:** Run `uniprot_ecoli_k12_sequences_001` to test edge case

**Reasons:**
1. Tests **memory specificity** (when NOT to use transitive)
2. Reveals if heuristics are **too rigid** or appropriately contextualized
3. **Critical edge case** for hierarchy tasks

**Continue with bacteria_taxa if:**
- Want to establish statistical significance on current experiment
- Have time for 30+ minute runs
- Want to measure consistency of existing memories

**Quick validation sequence:**
```bash
# 1. Sanity check (5 minutes)
python -m evals.cli run 'regression/basic_search_001' --trials 5 --enable-memory

# 2. Fast hierarchy test (10 minutes)
python -m evals.cli run 'hierarchy/prov_activity_subclasses_001' --trials 10 --enable-memory

# 3. Edge case test (15 minutes)
python -m evals.cli run 'uniprot/taxonomy/uniprot_ecoli_k12_sequences_001' --trials 5 --enable-memory
```

Total time: ~30 minutes for comprehensive validation vs 30+ minutes for single bacteria taxa experiment.
