# UniProt Curriculum Exemplar Mapping
**Created**: 2026-01-23
**Purpose**: Map 77 SHACL examples to procedural memory curriculum tasks

## Overview

This document maps the existing 77 SHACL examples in `ontology/uniprot/examples/UniProt/` to the 5-level curriculum structure defined in `procedural-memory-curriculum.md`. The goal is to identify which exemplars can become curriculum tasks to teach the RLM agent critical SPARQL patterns.

**Critical patterns needed** (from gene_protein_rhea failure analysis):
1. ✅ `up:catalyzedReaction ?rhea` (Level 4.1) - THE KEY PATTERN
2. ✅ `up:transcribedFrom ?ensemblGene` (Level 2.3) - Gene from transcript
3. ✅ `rdfs:seeAlso ?xref` + `up:database <...>` (Level 2.1) - Cross-reference filtering

---

## Curriculum Structure Recap

### Level 1: Foundation (Protein Discovery)
- 1.1: Basic protein retrieval (`up:Protein`, `up:reviewed`)
- 1.2: Organism filtering (`up:organism taxon:9606`)
- 1.3: Taxonomy hierarchy (`rdfs:subClassOf taxon:2`)

### Level 2: Cross-References
- 2.1: Database cross-references (`rdfs:seeAlso`, `up:database`)
- 2.2: Gene names (`up:encodedBy`, `up:mnemonic`)
- 2.3: **CRITICAL**: Transcript→Gene (`up:transcribedFrom`)

### Level 3: Annotations
- 3.1: GO classification (`up:classifiedWith`)
- 3.2: Disease annotations (`up:Disease_Annotation`, `up:disease`)
- 3.3: Natural variants (`up:Natural_Variant_Annotation`, `skos:related`)
- 3.4: Subcellular location (`up:Subcellular_Location_Annotation`, `up:locatedIn`)

### Level 4: Catalytic Activity
- 4.1: **CRITICAL**: Catalyzed reactions (`up:catalyzedReaction ?rhea`)
- 4.2: Evidence-based catalytic activities (`up:attribution`, `up:evidence`)
- 4.3: Enzyme classification (`up:enzyme`, `up:enzymeClass`)

### Level 5: Multi-Hop Integration
- 5.1: **TARGET**: Gene→Protein→Reaction (combines 2.3 + 4.1)
- 5.2: Disease + Location + Enzyme
- 5.3: Variants + Active Sites + Disease

### Federation Branches (F-series)
- F1: Simple SERVICE clause (OrthoDB)
- F2: Rhea reaction federation
- F3: Multi-endpoint federation (Rhea + IDSM/SACHEM)

---

## Exemplar → Curriculum Mapping

### Level 1: Foundation

| Example | File | Description | Patterns | Curriculum Task |
|---------|------|-------------|----------|----------------|
| **ex:106** | 106_uniprot_reviewed_or_not.ttl | List proteins by review status | `up:Protein`, `up:reviewed` | **L1.1**: Protein retrieval basics |
| **ex:3** | 3_entry_sequences_organism.ttl | E. coli K12 sequences | `up:organism`, `rdfs:subClassOf taxon:83333`, `up:sequence` | **L1.2**: Organism filtering |
| **ex:2** | 2_bacteria_taxa_and_their_scientific_name.ttl | Bacterial taxa | `up:Taxon`, `up:scientificName`, `rdfs:subClassOf taxon:2` | **L1.3**: Taxonomy hierarchy |
| ex:1 | 1_select_all_taxa_used_in_uniprot.ttl | All taxa in UniProt | `up:Taxon` class | L1.3 variant |
| ex:4 | 4_uniprot_mnemonic_id.ttl | Protein mnemonic IDs | `up:mnemonic` | L1.1 variant |

### Level 2: Cross-References

| Example | File | Description | Patterns | Curriculum Task |
|---------|------|-------------|----------|----------------|
| **ex:5** | 5_mapping_to_PDB.ttl | Map UniProt to PDB | `rdfs:seeAlso ?db`, `up:database <.../PDB>` | **L2.1**: Database cross-references |
| **ex:61** | 61_Gene_Protein_Reaction_sets.ttl | Gene→Protein→Reaction | `rdfs:seeAlso ?ensemblTranscript`, `up:database <.../Ensembl>`, **`up:transcribedFrom ?ensemblGene`** | **L2.3 + L5.1**: CRITICAL multi-hop example |
| ex:58 | 58_uniprot_to_HGNC_and_symbols.ttl | HGNC gene symbols | Cross-reference to HGNC | L2.2: Gene names |
| ex:6 | 6_cross_ref_in_category_3D.ttl | 3D structure cross-references | `rdfs:seeAlso` with category filter | L2.1 variant |

**⭐ CRITICAL EXEMPLAR**: **ex:61** teaches BOTH `up:transcribedFrom` (L2.3) AND the full gene→protein→reaction pattern (L5.1).

### Level 3: Annotations

| Example | File | Description | Patterns | Curriculum Task |
|---------|------|-------------|----------|----------------|
| **ex:23** | 23_human_proteins_related_to_kinase_activity.ttl | Kinase GO terms | `up:classifiedWith GO:0016301`, `up:classifiedWith/rdfs:subClassOf` | **L3.1**: GO classification |
| **ex:21** | 21_where_are_genetic_disease_related_proteins_in_a_cell.ttl | Disease + location | `up:annotation ?diseaseAnnotation`, `up:disease/skos:prefLabel`, `up:locatedIn/up:cellularComponent` | **L3.2 + L3.4**: Disease and subcellular location |
| **ex:62** | 62_diseases_involving_enzymes.ttl | Diseases related to enzymes | `up:Disease_Annotation`, `up:disease ?disease`, `up:enzyme` | **L3.2**: Disease annotations |
| **ex:10** | 10_human_variant_leading_to_transposition_of_tyrosine_to_phenylalanine.ttl | Y→F substitution variants | `up:Natural_Variant_Annotation`, `up:substitution`, `up:range/faldo:begin/faldo:position` | **L3.3**: Natural variants with sequence positions |
| ex:22 | 22_go_term_labels_per_go_category_for_multiple_proteins.ttl | GO terms by category | `up:classifiedWith`, GO categories | L3.1 variant |
| ex:121 | 121_proteins_and_diseases_linked.ttl | Proteins linked to diseases | Disease annotation pattern | L3.2 variant |

### Level 4: Catalytic Activity

| Example | File | Description | Patterns | Curriculum Task |
|---------|------|-------------|----------|----------------|
| **ex:61** | 61_Gene_Protein_Reaction_sets.ttl | Gene→Protein→Reaction | `?caa up:catalyticActivity ?ca`, **`?ca up:catalyzedReaction ?rhea`** | **L4.1**: CRITICAL catalyzedReaction pattern |
| **ex:39** | 39_experimental_catalytic_activities_in_swissprot.ttl | Experimental catalytic activities | `up:Catalytic_Activity_Annotation`, `up:catalyticActivity ?ca`, `up:catalyzedReaction ?rhea`, `up:attribution`, `up:evidence` | **L4.2**: Evidence-based catalytic activities |
| **ex:62** | 62_diseases_involving_enzymes.ttl | Enzyme disease relationship | `up:enzyme` OR `up:annotation/up:catalyticActivity/up:enzymeClass` | **L4.3**: Enzyme classification |
| ex:73 | 73_enzymes_related_to_protein.ttl | Enzyme queries | Enzyme patterns | L4.3 variant |
| ex:114 | 114_Number_of_EC_numbers_described_at_protein_domain_and_component_levels.ttl | EC number levels | EC classification | L4.3 variant |

**⭐ CRITICAL EXEMPLAR**: **ex:61** and **ex:39** both demonstrate the `up:catalyzedReaction` pattern that the agent missed in gene_protein_rhea.

### Level 5: Multi-Hop Integration

| Example | File | Description | Patterns | Curriculum Task |
|---------|------|-------------|----------|----------------|
| **ex:61** | 61_Gene_Protein_Reaction_sets.ttl | Gene→Protein→Reaction | Combines: `up:transcribedFrom` + `up:catalyzedReaction` + `rdfs:seeAlso` filtering | **L5.1**: MASTER EXEMPLAR for gene_protein_rhea task |
| **ex:63** | 63_diseases_involving_enzymes_located_in_mitochondrion.ttl | Disease + Location + Enzyme | Combines: Disease annotation + Subcellular location + Enzyme detection + `up:partOf*` | **L5.2**: Complex annotation integration |
| **ex:64** | 64_diseases_related_to_mutation_in_active_site.ttl | Variants in active sites | Combines: Natural variants + Active sites + Disease + sequence position overlap | **L5.3**: Extremely complex sequence-level integration |
| **ex:71** | 71_enzymes_interacting_with_molecules_similar_to_dopamine_with_variants_related_to_disease.ttl | Dopamine similarity + variants + disease | Combines: IDSM/SACHEM + Rhea + UniProt + variants + disease | **L5.4**: Research-level multi-service federation |

**⭐ MASTER EXEMPLAR**: **ex:61** is THE exemplar that, if learned, would have enabled the agent to solve gene_protein_rhea.

### Federation Branches (F-series)

| Example | File | Description | Patterns | Curriculum Task |
|---------|------|-------------|----------|----------------|
| **ex:36** | 36_orthologous_proteins_via_orthodb.ttl | OrthoDB orthologs | `SERVICE <https://sparql.orthodb.org/sparql/>`, basic federation | **F1**: Simple federated query |
| **ex:40** | 40_human_enzymes_that_metabolize_sphingolipids.ttl | Sphingolipid metabolism via Rhea | `SERVICE <https://sparql.rhea-db.org/sparql>`, `rh:side/rh:contains/rh:compound/rh:chebi`, `up:catalyzedReaction` | **F2**: Rhea federation |
| **ex:113** | 113_UniProtKB_Swiss-Prot_entries_annotated_with_CC-CA_Rhea_involving_lipids.ttl | Lipids via Rhea | `SERVICE <https://sparql.rhea-db.org/sparql>`, `rh:Reaction`, `rh:status`, ChEBI hierarchy | **F2 variant**: Complex Rhea patterns |
| **ex:70** | 70_enzymes_interacting_with_molecules_similar_to_dopamine.ttl | Chemical similarity search | `SERVICE <https://idsm.elixir-czech.cz/...>`, `sachem:similarCompoundSearch`, `GRAPH<https://sparql.rhea-db.org/rhea>` | **F3**: Multi-endpoint IDSM + Rhea |
| **ex:71** | 71_enzymes_interacting_with_molecules_similar_to_dopamine_with_variants_related_to_disease.ttl | Full dopamine query | Combines F3 + variants + disease | **F4**: Research-level federation |

---

## Priority Curriculum Tasks

Based on the exemplar analysis, here are the **priority tasks** that would fix the gene_protein_rhea failure and build toward complex queries:

### Phase 1: Foundation (Must-Pass)

1. **L1.1: Protein Retrieval** (ex:106)
   - Query: "List all reviewed proteins"
   - Pattern: `?protein up:reviewed true`

2. **L1.2: Organism Filtering** (ex:3)
   - Query: "Find all E. coli K12 proteins"
   - Pattern: `?organism rdfs:subClassOf taxon:83333`

3. **L2.1: Cross-Reference Filtering** (ex:5)
   - Query: "Map proteins to PDB structures"
   - Pattern: `rdfs:seeAlso ?db . ?db up:database <.../PDB>`

### Phase 2: Critical Predicates (Fix gene_protein_rhea)

4. **L4.1: Catalyzed Reactions** (ex:61 or ex:39) ⭐ **CRITICAL**
   - Query: "Find proteins that catalyze Rhea reactions"
   - Pattern: `?caa up:catalyticActivity ?ca . ?ca up:catalyzedReaction ?rhea`
   - **Memory to extract**: "Use `up:catalyzedReaction` for Rhea reactions, NOT `rdfs:seeAlso` with string filtering"

5. **L2.3: Transcript→Gene** (ex:61) ⭐ **CRITICAL**
   - Query: "Find Ensembl genes from protein transcripts"
   - Pattern: `?ensemblTranscript up:transcribedFrom ?ensemblGene`
   - **Memory to extract**: "Use `up:transcribedFrom` to get gene from transcript"

### Phase 3: Multi-Hop Integration

6. **L5.1: Gene→Protein→Reaction** (ex:61) ⭐ **MASTER EXEMPLAR**
   - Query: "Select Gene-Protein-Reaction sets for Human (Ensembl Gene, UniProtKB, Rhea reactions)"
   - Pattern: Full integration of 2.1 + 2.3 + 4.1
   - **Memory to extract**: "For gene-protein-reaction queries: (1) filter Ensembl cross-refs, (2) use `up:transcribedFrom` for gene, (3) use `up:catalyzedReaction` for reactions"

### Phase 4: Annotations

7. **L3.2: Disease Annotations** (ex:21 or ex:62)
   - Query: "Find diseases related to proteins"
   - Pattern: `up:Disease_Annotation`, `up:disease ?disease`

8. **L3.3: Natural Variants** (ex:10)
   - Query: "Find Y→F substitution variants"
   - Pattern: `up:Natural_Variant_Annotation`, `up:substitution`

9. **L5.2: Disease + Location + Enzyme** (ex:63)
   - Query: "Find diseases involving mitochondrial enzymes"
   - Pattern: Integrates disease + location + enzyme

### Phase 5: Federation (Optional, Research-Level)

10. **F2: Rhea Federation** (ex:40)
    - Query: "Find enzymes metabolizing sphingolipids (via Rhea)"
    - Pattern: `SERVICE <https://sparql.rhea-db.org/sparql>`

11. **F3: IDSM/SACHEM Chemical Similarity** (ex:70)
    - Query: "Find enzymes interacting with dopamine-like molecules"
    - Pattern: `SERVICE <https://idsm.elixir-czech.cz/...>`, `sachem:similarCompoundSearch`

---

## Anti-Patterns to Teach

Based on the gene_protein_rhea failure, we need to explicitly teach what NOT to do:

### ❌ Anti-Pattern 1: Using rdfs:seeAlso for Rhea reactions

**Incorrect** (what agent did):
```sparql
?activity rdfs:seeAlso ?rhea .
FILTER(CONTAINS(STR(?rhea), "rhea"))
```

**Correct** (from ex:61):
```sparql
?caa up:catalyticActivity ?ca .
?ca up:catalyzedReaction ?rhea .
```

**Memory to store**: "Rhea reactions: Use `up:catalyzedReaction`, NOT `rdfs:seeAlso` with string filtering"

### ❌ Anti-Pattern 2: Missing up:transcribedFrom

**Incorrect** (what agent did):
- Agent didn't know to use `up:transcribedFrom` for transcript→gene

**Correct** (from ex:61):
```sparql
?ensemblTranscript up:transcribedFrom ?ensemblGene
```

**Memory to store**: "For Ensembl genes: Use `up:transcribedFrom` to navigate from transcript to gene"

---

## Implementation Strategy

### Step 1: Create Core Curriculum Tasks (Phase 1-2)

Convert these exemplars to eval tasks in `evals/tasks/uniprot/curriculum/`:
- `01_protein_retrieval_reviewed.yaml` (ex:106)
- `02_organism_filtering_ecoli.yaml` (ex:3)
- `03_xref_filtering_pdb.yaml` (ex:5)
- `04_catalyzed_reactions_rhea.yaml` (ex:61 simplified) ⭐ **KEY**
- `05_transcript_to_gene_ensembl.yaml` (ex:61 simplified) ⭐ **KEY**

### Step 2: Run Curriculum with Memory Enabled

```bash
python -m evals.cli run 'curriculum/*' --enable-memory
```

### Step 3: Verify Memory Extraction

Check `evals/memory.db` for procedural memories:
- "Use `up:catalyzedReaction` for Rhea reactions"
- "Use `up:transcribedFrom` for transcript→gene"

### Step 4: Test Integration Task

Run the full gene_protein_rhea task:
```bash
python -m evals.cli run 'multihop/uniprot_gene_protein_rhea_sets_001'
```

Expected outcome: Agent retrieves and uses memories, constructs correct query

### Step 5: Add Advanced Tasks (Phase 3-5)

Once core patterns are learned, add:
- Disease annotation tasks (Phase 4)
- Multi-hop integration tasks (Phase 3)
- Federated query tasks (Phase 5)

---

## Exemplar Coverage Analysis

### Total Examples: 77

**Analyzed in detail**: 16 examples
**Categorized**: ~40 examples (preliminary)
**Remaining**: ~37 examples (to be categorized)

### Pattern Coverage

| Pattern Category | Exemplars Found | Curriculum Coverage |
|------------------|----------------|---------------------|
| Basic protein retrieval | ex:3, ex:106, ex:4 | ✅ L1.1, L1.2 |
| Taxonomy hierarchy | ex:1, ex:2 | ✅ L1.3 |
| Cross-references | ex:5, ex:6, ex:58, ex:61 | ✅ L2.1, L2.2, L2.3 |
| GO classification | ex:22, ex:23 | ✅ L3.1 |
| Disease annotations | ex:21, ex:62, ex:121 | ✅ L3.2 |
| Natural variants | ex:10, ex:64, ex:71 | ✅ L3.3 |
| Subcellular location | ex:21, ex:63 | ✅ L3.4 |
| Catalyzed reactions | ex:39, ex:61, ex:73 | ✅ L4.1, L4.2, L4.3 |
| Gene→Protein→Reaction | ex:61 | ✅ L5.1 (MASTER) |
| Disease + Location + Enzyme | ex:63 | ✅ L5.2 |
| Variants + Active Sites | ex:64 | ✅ L5.3 |
| Rhea federation | ex:40, ex:113 | ✅ F2 |
| IDSM/SACHEM federation | ex:70, ex:71 | ✅ F3, F4 |
| OrthoDB federation | ex:36 | ✅ F1 |

**Coverage**: Excellent - all major pattern categories have exemplars

---

## Remaining Work

### Immediate

1. ✅ Scan exemplars for curriculum items (this document)
2. ⬜ Create Phase 1-2 curriculum tasks (5 tasks)
3. ⬜ Run curriculum with memory enabled
4. ⬜ Verify memory extraction
5. ⬜ Re-test gene_protein_rhea

### Medium-term

6. ⬜ Categorize remaining 37 exemplars
7. ⬜ Create Phase 3-4 curriculum tasks (disease, variants)
8. ⬜ Add anti-pattern detection to graders

### Long-term

9. ⬜ Implement federation curriculum (Phase 5)
10. ⬜ Research-level: Multi-service federation (ex:70, ex:71)

---

## Key Findings

### 1. ex:61 is THE Master Exemplar

**Example 61** (Gene_Protein_Reaction_sets.ttl) contains ALL three critical patterns:
- `rdfs:seeAlso` + `up:database Ensembl` (L2.1)
- `up:transcribedFrom ?ensemblGene` (L2.3)
- `up:catalyzedReaction ?rhea` (L4.1)

**If the agent had learned from this single example**, it would have solved gene_protein_rhea.

### 2. Anti-Patterns Are Critical

The agent found `up:catalyzedReaction` during exploration but chose NOT to use it. This suggests:
- Need explicit "anti-pattern" memories: "DON'T use rdfs:seeAlso for Rhea reactions"
- Need grading that penalizes known anti-patterns
- Need curriculum tasks that contrast correct vs incorrect approaches

### 3. Curriculum Should Be Progressive

The 5-level structure is validated by exemplars:
- Level 1-2: Foundation (protein retrieval, cross-refs)
- Level 3: Annotations (disease, variants, GO terms)
- Level 4: Catalytic activity (THE critical gap)
- Level 5: Multi-hop integration (combine learned patterns)
- F-series: Federation (research-level)

### 4. Phase 1-2 Curriculum Would Fix gene_protein_rhea

Running just **5 curriculum tasks** (L1.1, L1.2, L2.1, L4.1, L2.3) would teach the patterns needed for gene_protein_rhea.

---

## References

- **Curriculum design**: `docs/planning/procedural-memory-curriculum.md`
- **gene_protein_rhea failure**: `docs/analysis/eval-rerun-post-llm-judge-fix-2026-01-23.md`
- **Exemplars directory**: `ontology/uniprot/examples/UniProt/`
- **Master exemplar**: `ontology/uniprot/examples/UniProt/61_Gene_Protein_Reaction_sets.ttl`
