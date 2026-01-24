# Create Core Curriculum Tasks
**Created**: 2026-01-23
**Status**: Ready to implement
**Priority**: High (fixes gene_protein_rhea failure)

## Goal

Create 5 core curriculum tasks that teach the critical patterns needed to solve the gene_protein_rhea task. These tasks will populate the procedural memory with the specific patterns the agent missed.

---

## Background

The gene_protein_rhea task failed because the agent:
1. ❌ Used `rdfs:seeAlso` with string filtering instead of `up:catalyzedReaction`
2. ❌ Didn't know about `up:transcribedFrom` for transcript→gene navigation

**Root cause**: No procedural memories teaching these patterns (73 existing memories are about E. coli sequences and taxonomy, nothing about catalytic activities or gene navigation)

**Solution**: Run 5 curriculum tasks that extract these patterns into memory

---

## Task Definitions

### Task 1: Protein Retrieval (L1.1)

**File**: `evals/tasks/uniprot/curriculum/01_protein_retrieval_reviewed.yaml`

**Source exemplar**: ex:106 (106_uniprot_reviewed_or_not.ttl)

```yaml
task:
  id: "curriculum_01_protein_retrieval_reviewed"
  category: "uniprot/curriculum"
  difficulty: "easy"

  query: "List all reviewed proteins"

  context:
    ontologies:
      - name: uniprot_core
        source: ontology/uniprot/core.ttl
    sparql:
      endpoint: "https://sparql.uniprot.org/sparql/"
      prefixes: "ontology/uniprot/examples/prefixes.ttl"
      exemplar: "ontology/uniprot/examples/UniProt/106_uniprot_reviewed_or_not.ttl"

  exemplar_patterns:
    - "?protein a up:Protein"
    - "?protein up:reviewed true"

  graders:
    - type: convergence
      max_iterations: 10
    - type: sparql_structural
      requires_patterns: ["up:reviewed"]
    - type: outcome_verification
      result_type: "present"
      min_results: 1
      required_fields: ["protein"]
    - type: llm_judge
      use_exemplar_patterns: true
    - type: tool_called
      required: ["sparql_query"]

  trials: 1
  enable_memory: true  # CRITICAL: Extract pattern to memory
```

**Expected memory**: "Use `up:reviewed true` to filter for Swiss-Prot entries"

---

### Task 2: Organism Filtering (L1.2)

**File**: `evals/tasks/uniprot/curriculum/02_organism_filtering_ecoli.yaml`

**Source exemplar**: ex:3 (3_entry_sequences_organism.ttl)

```yaml
task:
  id: "curriculum_02_organism_filtering_ecoli"
  category: "uniprot/curriculum"
  difficulty: "easy"

  query: "Find all E. coli K12 proteins and their sequences"

  context:
    ontologies:
      - name: uniprot_core
        source: ontology/uniprot/core.ttl
    sparql:
      endpoint: "https://sparql.uniprot.org/sparql/"
      prefixes: "ontology/uniprot/examples/prefixes.ttl"
      exemplar: "ontology/uniprot/examples/UniProt/3_entry_sequences_organism.ttl"

  exemplar_patterns:
    - "?protein up:organism ?organism"
    - "?organism rdfs:subClassOf taxon:83333"

  graders:
    - type: convergence
      max_iterations: 10
    - type: sparql_structural
      requires_patterns: ["up:organism", "rdfs:subClassOf"]
    - type: outcome_verification
      result_type: "present"
      min_results: 1
      required_fields: ["protein"]
    - type: llm_judge
      use_exemplar_patterns: true
    - type: tool_called
      required: ["sparql_query"]

  trials: 1
  enable_memory: true
```

**Expected memory**: "Use `?organism rdfs:subClassOf taxon:X` to filter by taxonomy (taxon subclasses are materialized)"

---

### Task 3: Cross-Reference Filtering (L2.1)

**File**: `evals/tasks/uniprot/curriculum/03_xref_filtering_pdb.yaml`

**Source exemplar**: ex:5 (5_mapping_to_PDB.ttl)

```yaml
task:
  id: "curriculum_03_xref_filtering_pdb"
  category: "uniprot/curriculum"
  difficulty: "medium"

  query: "Map proteins to PDB structure entries"

  context:
    ontologies:
      - name: uniprot_core
        source: ontology/uniprot/core.ttl
    sparql:
      endpoint: "https://sparql.uniprot.org/sparql/"
      prefixes: "ontology/uniprot/examples/prefixes.ttl"
      exemplar: "ontology/uniprot/examples/UniProt/5_mapping_to_PDB.ttl"

  exemplar_patterns:
    - "?protein rdfs:seeAlso ?db"
    - "?db up:database <http://purl.uniprot.org/database/PDB>"

  graders:
    - type: convergence
      max_iterations: 10
    - type: sparql_structural
      requires_patterns: ["rdfs:seeAlso", "up:database"]
    - type: outcome_verification
      result_type: "present"
      min_results: 1
      required_fields: ["protein", "db"]
    - type: llm_judge
      use_exemplar_patterns: true
    - type: tool_called
      required: ["sparql_query"]

  trials: 1
  enable_memory: true
```

**Expected memory**: "Filter cross-references by database: `rdfs:seeAlso ?xref . ?xref up:database <database_uri>`"

---

### Task 4: Catalyzed Reactions (L4.1) ⭐ CRITICAL

**File**: `evals/tasks/uniprot/curriculum/04_catalyzed_reactions_rhea.yaml`

**Source exemplar**: ex:61 (61_Gene_Protein_Reaction_sets.ttl) - simplified to focus on catalyzed reactions

```yaml
task:
  id: "curriculum_04_catalyzed_reactions_rhea"
  category: "uniprot/curriculum"
  difficulty: "medium"

  query: "Find reviewed proteins that catalyze Rhea reactions"

  context:
    ontologies:
      - name: uniprot_core
        source: ontology/uniprot/core.ttl
    sparql:
      endpoint: "https://sparql.uniprot.org/sparql/"
      prefixes: "ontology/uniprot/examples/prefixes.ttl"
      exemplar: "ontology/uniprot/examples/UniProt/61_Gene_Protein_Reaction_sets.ttl"

  exemplar_patterns:
    - "?protein up:annotation ?caa"
    - "?caa up:catalyticActivity ?ca"
    - "?ca up:catalyzedReaction ?rhea"

  graders:
    - type: convergence
      max_iterations: 12
    - type: sparql_structural
      requires_patterns: ["up:catalyticActivity", "up:catalyzedReaction"]
    - type: outcome_verification
      result_type: "present"
      min_results: 1
      required_fields: ["protein", "rhea"]
    - type: llm_judge
      use_exemplar_patterns: true
      strict: true  # Must use catalyzedReaction, not rdfs:seeAlso
    - type: tool_called
      required: ["sparql_query"]

  trials: 3
  enable_memory: true
```

**Expected memory** (CRITICAL):
- "For Rhea reactions: Use `up:catalyzedReaction ?rhea`, NOT `rdfs:seeAlso` with string filtering"
- "Catalytic activities: `?annotation up:catalyticActivity ?ca . ?ca up:catalyzedReaction ?rhea`"

**Anti-pattern to avoid**:
```sparql
# ❌ WRONG (what agent did in gene_protein_rhea)
?activity rdfs:seeAlso ?rhea .
FILTER(CONTAINS(STR(?rhea), "rhea"))
```

---

### Task 5: Transcript→Gene (L2.3) ⭐ CRITICAL

**File**: `evals/tasks/uniprot/curriculum/05_transcript_to_gene_ensembl.yaml`

**Source exemplar**: ex:61 (61_Gene_Protein_Reaction_sets.ttl) - simplified to focus on transcript→gene

```yaml
task:
  id: "curriculum_05_transcript_to_gene_ensembl"
  category: "uniprot/curriculum"
  difficulty: "medium"

  query: "Find Ensembl genes for reviewed human proteins via transcript cross-references"

  context:
    ontologies:
      - name: uniprot_core
        source: ontology/uniprot/core.ttl
    sparql:
      endpoint: "https://sparql.uniprot.org/sparql/"
      prefixes: "ontology/uniprot/examples/prefixes.ttl"
      exemplar: "ontology/uniprot/examples/UniProt/61_Gene_Protein_Reaction_sets.ttl"

  exemplar_patterns:
    - "?protein rdfs:seeAlso ?ensemblTranscript"
    - "?ensemblTranscript up:database <http://purl.uniprot.org/database/Ensembl>"
    - "?ensemblTranscript up:transcribedFrom ?ensemblGene"

  graders:
    - type: convergence
      max_iterations: 12
    - type: sparql_structural
      requires_patterns: ["up:transcribedFrom"]
    - type: outcome_verification
      result_type: "present"
      min_results: 1
      required_fields: ["protein", "ensemblGene"]
    - type: llm_judge
      use_exemplar_patterns: true
      strict: true  # Must use up:transcribedFrom
    - type: tool_called
      required: ["sparql_query"]

  trials: 3
  enable_memory: true
```

**Expected memory** (CRITICAL):
- "For Ensembl genes: Use `up:transcribedFrom ?gene` to navigate from transcript to gene"
- "Pattern: `?protein rdfs:seeAlso ?transcript . ?transcript up:database Ensembl . ?transcript up:transcribedFrom ?gene`"

---

## Implementation Steps

### Step 1: Create Task Files

```bash
# Create curriculum directory
mkdir -p evals/tasks/uniprot/curriculum

# Create 5 task files (use Write tool or copy templates above)
# Files:
# - 01_protein_retrieval_reviewed.yaml
# - 02_organism_filtering_ecoli.yaml
# - 03_xref_filtering_pdb.yaml
# - 04_catalyzed_reactions_rhea.yaml
# - 05_transcript_to_gene_ensembl.yaml
```

### Step 2: Run Curriculum (With Memory Enabled)

```bash
# Run all curriculum tasks with memory enabled
python -m evals.cli run 'curriculum/*'

# Expected output:
# ✅ curriculum_01_protein_retrieval_reviewed - PASSED
# ✅ curriculum_02_organism_filtering_ecoli - PASSED
# ✅ curriculum_03_xref_filtering_pdb - PASSED
# ✅ curriculum_04_catalyzed_reactions_rhea - PASSED (extracts catalyzedReaction pattern)
# ✅ curriculum_05_transcript_to_gene_ensembl - PASSED (extracts transcribedFrom pattern)
```

### Step 3: Verify Memory Extraction

```bash
# Check memory database
sqlite3 evals/memory.db "SELECT id, title, strategy FROM reasoning_memories WHERE strategy LIKE '%catalyzed%' OR strategy LIKE '%transcribed%'"

# Expected results:
# - Memory about up:catalyzedReaction pattern
# - Memory about up:transcribedFrom pattern
```

### Step 4: Re-test gene_protein_rhea

```bash
# Run the failing task again (with memory retrieval enabled)
python -m evals.cli run 'multihop/uniprot_gene_protein_rhea_sets_001'

# Expected outcome:
# ✅ PASSED - Agent retrieves memories and constructs correct query
```

### Step 5: Verify Success

Check the trajectory to confirm:
1. Agent retrieved procedural memories about `catalyzedReaction` and `transcribedFrom`
2. Agent used these patterns in the SPARQL query
3. Query returned results
4. All graders passed

---

## Task Configuration Details

### Common Settings

All curriculum tasks share these settings:
- `enable_memory: true` - Extract procedural memories
- `trials: 1` (or 3 for critical tasks) - Run once to populate memory
- `category: "uniprot/curriculum"` - Organize as curriculum
- `use_exemplar_patterns: true` - LLM judge checks for patterns

### Grader Configuration

Each task uses 5 graders:
1. **convergence** - Ensures task completes within iteration limit
2. **sparql_structural** - Checks for required SPARQL patterns
3. **outcome_verification** - Verifies results are present and non-empty
4. **llm_judge** - Primary arbiter, checks exemplar patterns
5. **tool_called** - Verifies sparql_query tool was used

### Memory Extraction

After each successful task:
- DSPy RLM judges the trajectory (success/failure)
- Memory extraction identifies key strategies
- Memories stored in SQLite with BM25 indexing
- Future queries retrieve relevant memories

---

## Success Criteria

### Phase 1 Success (Curriculum Population)

- ✅ All 5 curriculum tasks pass
- ✅ At least 2 new memories extracted (catalyzedReaction, transcribedFrom)
- ✅ Memories contain correct SPARQL patterns

### Phase 2 Success (gene_protein_rhea Fix)

- ✅ gene_protein_rhea task now passes
- ✅ Agent query uses `up:catalyzedReaction` (not rdfs:seeAlso)
- ✅ Agent query uses `up:transcribedFrom` (not missing)
- ✅ Query returns results
- ✅ LLM judge passes

### Phase 3 Success (Other Multi-hop Tasks)

- ✅ Other multi-hop tasks benefit from memories
- ✅ Pass rate improves from 75% to 85%+

---

## Timeline

- **Day 1**: Create 5 task files (~2 hours)
- **Day 1**: Run curriculum tasks (~15 minutes)
- **Day 1**: Verify memory extraction (~15 minutes)
- **Day 1**: Re-test gene_protein_rhea (~5 minutes)
- **Day 2**: Analyze results and iterate if needed

**Total estimated time**: 3-4 hours to implementation + validation

---

## Risks and Mitigations

### Risk 1: Memory Extraction Fails

**Symptom**: Tasks pass but no memories extracted

**Mitigation**:
- Check trajectory judgment logic
- Verify memory extraction is enabled
- Manually inspect successful queries

### Risk 2: Memories Not Retrieved

**Symptom**: gene_protein_rhea still fails after curriculum

**Mitigation**:
- Check BM25 retrieval query
- Verify memory relevance scoring
- Add explicit memory injection for debugging

### Risk 3: Agent Ignores Memories

**Symptom**: Memories retrieved but agent uses wrong pattern

**Mitigation**:
- Check memory injection in context
- Add stronger prompting about using procedural memories
- Review DSPy RLM prompt engineering

---

## Next Steps After Core Curriculum

Once the core curriculum works:

1. **Add Phase 3 tasks** (Multi-hop integration)
   - Gene→Protein→Reaction full task (ex:61)
   - Disease + Location + Enzyme (ex:63)

2. **Add Phase 4 tasks** (Annotations)
   - Disease annotations (ex:21, ex:62)
   - Natural variants (ex:10)
   - GO classification (ex:23)

3. **Add Federation tasks** (Research-level)
   - Rhea federation (ex:40)
   - OrthoDB federation (ex:36)
   - IDSM/SACHEM federation (ex:70)

4. **Add Anti-pattern Detection**
   - Grader that penalizes known anti-patterns
   - Negative curriculum tasks showing wrong approaches

---

## Related Documents

- **Curriculum design**: `docs/planning/procedural-memory-curriculum.md`
- **Exemplar mapping**: `docs/planning/uniprot-curriculum-exemplar-mapping.md`
- **gene_protein_rhea failure analysis**: `docs/analysis/eval-rerun-post-llm-judge-fix-2026-01-23.md`
- **Multi-service federation**: `docs/planning/multi-service-federation-strategy.md`

---

## Status

**Ready to implement** - Task definitions are complete and exemplars are identified.

**Next action**: Create the 5 YAML files in `evals/tasks/uniprot/curriculum/`
