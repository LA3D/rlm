# Procedural Memory Curriculum Design
**Created**: 2026-01-23
**Purpose**: Define task sequences that build procedural memory for complex query construction
**Status**: Planning / Proposal

## Problem Statement

The agent failed the gene_protein_rhea task because it:
1. Found the correct `catalyzedReaction` property during exploration
2. But chose to use generic `rdfs:seeAlso` with string filtering instead
3. Didn't discover/use `up:transcribedFrom` for transcript→gene links

**Root cause**: No procedural memory of similar patterns. The agent had to discover everything from scratch each time.

**Solution**: Build a curriculum that progressively teaches patterns, with each task extracting memories that help with later tasks.

---

## Curriculum Design Principles

### 1. Scaffolded Complexity
Start with simple patterns, build to complex multi-hop federated queries.

**Rungs of complexity:**
- **Rung 1**: Single entity, single property (e.g., "Get protein names")
- **Rung 2**: Single hop with filtering (e.g., "Get human proteins")
- **Rung 3**: Two-hop chains (e.g., "Protein → annotation")
- **Rung 4**: Multi-hop with cross-references (e.g., "Protein → database → external ID")
- **Rung 5**: Multi-hop with specialized predicates (e.g., "Protein → activity → reaction")
- **Rung 6**: Federated multi-hop (e.g., "Protein → Rhea → ChEBI")

### 2. Pattern Isolation
Each task introduces ONE new pattern, building on previous memories.

**Example progression for catalytic reactions:**
1. First: Simple annotation retrieval (learn `up:annotation`)
2. Then: Specific annotation types (learn `up:Catalytic_Activity_Annotation`)
3. Then: Activity properties (learn `up:catalyticActivity`)
4. Finally: Reaction linking (learn `up:catalyzedReaction`)

### 3. Memory Extraction Requirements

For each task, the agent should extract memories containing:
- **Pattern**: The key predicate chain used (e.g., `?protein up:annotation ?ann . ?ann up:catalyticActivity ?ca`)
- **Context**: When this pattern is useful (e.g., "To find catalyzed reactions from proteins")
- **Pitfalls**: What NOT to do (e.g., "Don't use rdfs:seeAlso with string filtering for reactions")
- **Example**: Concrete SPARQL snippet showing the pattern

---

## UniProt Query Curriculum

### Level 1: Foundation Patterns (Rungs 1-2)

**Goal**: Basic entity retrieval and filtering

#### L1.1: Entity Enumeration
```yaml
task: "List 10 reviewed proteins from UniProt"
teaches:
  - up:Protein class
  - up:reviewed property
  - LIMIT clause
memory_extracts:
  - "Use up:reviewed true to filter for reviewed proteins"
  - "up:Protein is the main entity class"
```

#### L1.2: Taxonomy Filtering
```yaml
task: "List reviewed human proteins (taxon:9606)"
teaches:
  - up:organism property
  - Taxonomy URIs
  - Combining filters
memory_extracts:
  - "Use up:organism taxon:9606 for human proteins"
  - "Combine up:reviewed and up:organism for reviewed proteins of specific species"
depends_on: [L1.1]
```

#### L1.3: Property Extraction
```yaml
task: "Get protein names and mnemonics"
teaches:
  - up:mnemonic property
  - up:recommendedName pattern
  - OPTIONAL for missing values
memory_extracts:
  - "Protein names via up:recommendedName/up:fullName path"
  - "Use OPTIONAL when properties may be missing"
depends_on: [L1.1]
```

### Level 2: Cross-References (Rung 3-4)

**Goal**: Navigate to external databases

#### L2.1: Basic Cross-References
```yaml
task: "Find proteins with Ensembl cross-references"
teaches:
  - rdfs:seeAlso for cross-references
  - up:database property for filtering
  - Database URIs (e.g., <http://purl.uniprot.org/database/Ensembl>)
memory_extracts:
  - "Use rdfs:seeAlso to get cross-references"
  - "Filter by up:database to get specific database refs"
  - "PATTERN: ?protein rdfs:seeAlso ?xref . ?xref up:database <DB_URI>"
depends_on: [L1.2]
```

#### L2.2: Transcript References
```yaml
task: "Get Ensembl transcript IDs for human proteins"
teaches:
  - Ensembl database URI
  - Transcript vs gene distinction
  - up:translatedTo / up:transcribedFrom (if exploring reverse direction)
memory_extracts:
  - "Ensembl transcript cross-refs: ?xref up:database <http://purl.uniprot.org/database/Ensembl>"
  - "Transcripts link to genes via up:transcribedFrom (on external Ensembl data)"
depends_on: [L2.1]
```

#### L2.3: Transcript to Gene (Critical!)
```yaml
task: "For proteins with Ensembl transcripts, get the corresponding genes"
teaches:
  - up:transcribedFrom property (THE KEY MISSING PIECE!)
  - Chaining transcript → gene
memory_extracts:
  - "CRITICAL: Use up:transcribedFrom to get gene from transcript"
  - "PATTERN: ?protein rdfs:seeAlso ?transcript . ?transcript up:database <.../Ensembl> . ?transcript up:transcribedFrom ?gene"
  - "DO NOT use string filtering on seeAlso for genes - use up:transcribedFrom"
depends_on: [L2.2]
```

### Level 3: Annotations (Rung 4)

**Goal**: Navigate annotation structures

#### L3.1: Basic Annotations
```yaml
task: "List annotation types for a protein"
teaches:
  - up:annotation property
  - Annotation class hierarchy
  - Counting annotation types
memory_extracts:
  - "Proteins have up:annotation pointing to annotation objects"
  - "Annotations have specific types (subclasses of up:Annotation)"
depends_on: [L1.2]
```

#### L3.2: Disease Annotations
```yaml
task: "Find proteins with disease annotations"
teaches:
  - up:Disease_Annotation class
  - up:disease property
  - skos:prefLabel for disease names
memory_extracts:
  - "PATTERN: ?protein up:annotation ?ann . ?ann a up:Disease_Annotation . ?ann up:disease ?disease"
  - "Get disease name via skos:prefLabel"
depends_on: [L3.1]
```

#### L3.3: Catalytic Activity Annotations (Critical!)
```yaml
task: "Find proteins with catalytic activity annotations"
teaches:
  - up:Catalytic_Activity_Annotation class
  - up:catalyticActivity property
  - Activity objects
memory_extracts:
  - "PATTERN: ?protein up:annotation ?caa . ?caa a up:Catalytic_Activity_Annotation . ?caa up:catalyticActivity ?activity"
  - "Catalytic activities are separate objects, NOT direct properties"
depends_on: [L3.1]
```

### Level 4: Reactions (Rung 5) - THE CRITICAL LEVEL

**Goal**: Link activities to reactions (where gene_protein_rhea failed)

#### L4.1: Catalyzed Reactions (THE KEY PATTERN!)
```yaml
task: "For proteins with catalytic activities, get the catalyzed Rhea reactions"
teaches:
  - up:catalyzedReaction property (THE MISSING PIECE!)
  - Rhea reaction URIs
  - NOT using rdfs:seeAlso for reactions
memory_extracts:
  - "CRITICAL: Use up:catalyzedReaction to get Rhea reactions from activity objects"
  - "PATTERN: ?caa up:catalyticActivity ?ca . ?ca up:catalyzedReaction ?rhea"
  - "DO NOT use rdfs:seeAlso with string filtering for reactions"
  - "Rhea reactions are linked via up:catalyzedReaction, not rdfs:seeAlso"
  - "ANTI-PATTERN: ?activity rdfs:seeAlso ?rhea . FILTER(CONTAINS(STR(?rhea), 'rhea')) ❌"
depends_on: [L3.3]
```

#### L4.2: Full Protein→Reaction Chain
```yaml
task: "Get all human reviewed proteins with their catalyzed Rhea reactions"
teaches:
  - Complete annotation → activity → reaction chain
  - Combining filters (human, reviewed, has reaction)
memory_extracts:
  - "Full pattern for protein→reaction:"
  - "?protein up:reviewed true ; up:organism taxon:9606 ; up:annotation ?caa ."
  - "?caa a up:Catalytic_Activity_Annotation ; up:catalyticActivity ?ca ."
  - "?ca up:catalyzedReaction ?rhea ."
depends_on: [L4.1]
```

### Level 5: Multi-Hop Chains (Rung 6)

**Goal**: Combine cross-references + annotations (the gene_protein_rhea task!)

#### L5.1: Gene→Protein→Reaction (The Target!)
```yaml
task: "For human reviewed proteins, return Ensembl gene → UniProtKB protein → catalyzed Rhea reaction"
teaches:
  - Combining L2.3 (transcript→gene) + L4.2 (protein→reaction)
  - Using DISTINCT to avoid duplicates from multiple transcripts
  - Complete multi-hop pattern
memory_extracts:
  - "Gene→Protein→Reaction requires combining two patterns:"
  - "1. Transcript→Gene: ?protein rdfs:seeAlso ?transcript . ?transcript up:database <.../Ensembl> . ?transcript up:transcribedFrom ?gene"
  - "2. Protein→Reaction: ?protein up:annotation ?caa . ?caa up:catalyticActivity ?ca . ?ca up:catalyzedReaction ?rhea"
  - "Use DISTINCT because one gene may have multiple transcripts"
depends_on: [L2.3, L4.2]
```

---

## Additional Curriculum Branches

### Branch A: External Database Integration

For tasks requiring ChEMBL, PDB, etc.

#### A1: ChEMBL Annotations
```yaml
task: "Find proteins annotated in ChEMBL"
teaches:
  - ChEMBL database URI
  - ChEMBL ID extraction
memory_extracts:
  - "ChEMBL cross-refs: ?protein rdfs:seeAlso ?chembl . ?chembl up:database <.../ChEMBL>"
depends_on: [L2.1]
```

#### A2: Multi-Database Proteins
```yaml
task: "Find proteins with both ChEMBL and PDB annotations"
teaches:
  - Combining multiple cross-reference filters
  - Using multiple rdfs:seeAlso patterns
depends_on: [A1]
```

### Branch B: Taxonomy Hierarchies

For bacterial taxa, strain queries, etc.

#### B1: Taxonomic Rank
```yaml
task: "List all bacterial taxa (kingdom Bacteria)"
teaches:
  - up:rank property
  - Taxonomic hierarchy URIs
  - rdfs:subClassOf for lineage
depends_on: [L1.3]
```

#### B2: Strain Relationships
```yaml
task: "Find all strains of E. coli K-12"
teaches:
  - Strain vs species distinction
  - Taxonomic parent/child relationships
depends_on: [B1]
```

### Branch C: Sequence Retrieval

For protein sequences, features, etc.

#### C1: Sequence Extraction
```yaml
task: "Get amino acid sequences for proteins"
teaches:
  - up:sequence property
  - rdf:value for literal sequences
depends_on: [L1.2]
```

---

## Federation Curriculum (Advanced)

For multi-service queries (IDSM, Rhea, etc.)

### F1: Simple SERVICE Queries
```yaml
task: "Query Rhea directly for reactions with specific EC numbers"
teaches:
  - SERVICE clause syntax
  - Rhea vocabulary basics
  - Cross-endpoint result binding
memory_extracts:
  - "SERVICE <https://sparql.rhea-db.org/sparql> { ... }"
  - "Bind results from SERVICE to outer query variables"
depends_on: [L4.2]
```

### F2: UniProt→Rhea Federation
```yaml
task: "Find proteins catalyzing reactions with EC 2.7.11.1, using Rhea SERVICE"
teaches:
  - Binding UniProt data to Rhea queries
  - Joining on reaction URIs
depends_on: [F1, L4.2]
```

### F3: Chemical Similarity (Stretch Goal)
```yaml
task: "Find proteins catalyzing reactions with dopamine-like molecules"
teaches:
  - IDSM/SACHEM service
  - Chemical similarity search
  - Three-way federation (IDSM → Rhea → UniProt)
depends_on: [F2]
note: "Requires IDSM endpoint access and SACHEM vocabulary"
```

---

## Curriculum Implementation Strategy

### Phase 1: Core Pattern Library (Levels 1-4)

**Tasks**: L1.1 → L1.2 → L1.3 → L2.1 → L2.2 → L2.3 → L3.1 → L3.2 → L3.3 → L4.1 → L4.2

**Duration**: ~20-25 tasks
**Memory extracts**: ~40-50 procedural memories
**Outcome**: Agent can handle single-endpoint multi-hop queries

**Key memories captured**:
- Basic protein filtering patterns
- Cross-reference navigation (esp. transcript→gene via up:transcribedFrom)
- Annotation structures (disease, catalytic activity)
- **Reaction linking** (up:catalyzedReaction - THE CRITICAL ONE!)

### Phase 2: Integration (Level 5)

**Tasks**: L5.1 (gene→protein→reaction)

**Prerequisites**: All Level 4 memories
**Tests**: The current failing task should now pass!
**Validation**: Agent should retrieve memories for:
  - up:transcribedFrom (from L2.3)
  - up:catalyzedReaction (from L4.1)

### Phase 3: Domain Expansion (Branches A, B, C)

**Parallel branches** for different query types:
- ChEMBL annotations (Branch A)
- Taxonomy hierarchies (Branch B)
- Sequence retrieval (Branch C)

**Memory cross-pollination**: Patterns from one branch may help another

### Phase 4: Federation (F-series)

**Advanced topics**:
- Multi-endpoint SERVICE queries
- Cross-database joins
- Chemical similarity search

---

## Memory Extraction Criteria

For each successful task, extract memories ONLY if:

1. **Pattern is reusable** - Not task-specific, applies to multiple queries
2. **Non-obvious** - Agent is likely to make the wrong choice without it
3. **High impact** - Failure to use this pattern causes 0 results or wrong results

**Examples of HIGH-VALUE memories:**

✅ **Good memory** (from L4.1):
```
Title: "Link Activities to Rhea Reactions via catalyzedReaction"
Description: "Use up:catalyzedReaction to get Rhea reactions from activity objects, not rdfs:seeAlso"
Pattern: "?ca up:catalyzedReaction ?rhea"
Anti-pattern: "❌ ?ca rdfs:seeAlso ?rhea . FILTER(CONTAINS(STR(?rhea), 'rhea'))"
When: "When you need to find Rhea reactions catalyzed by proteins"
```

✅ **Good memory** (from L2.3):
```
Title: "Get Genes from Ensembl Transcripts"
Description: "Use up:transcribedFrom to navigate from transcript to gene"
Pattern: "?transcript up:database <http://purl.uniprot.org/database/Ensembl> . ?transcript up:transcribedFrom ?gene"
When: "When you need Ensembl gene IDs but protein has transcript cross-references"
```

❌ **Bad memory** (too specific):
```
Title: "Get Human Proteins"
Pattern: "?protein up:organism taxon:9606"
```
(This is trivial and doesn't need a memory - agent can discover it easily)

---

## Success Metrics

### Immediate (Post-Phase 1)

- **Memory count**: 40-50 procedural memories
- **Coverage**: All Level 1-4 patterns represented
- **Retrieval**: BM25 search returns relevant memories for test queries

### Medium-term (Post-Phase 2)

- **Task success**: gene_protein_rhea task passes (currently fails)
- **Pattern usage**: Agent uses up:catalyzedReaction instead of rdfs:seeAlso
- **Memory impact**: Agent cites retrieved memories in reasoning

### Long-term (Post-Phase 4)

- **Zero-shot generalization**: Agent can solve novel multi-hop queries without new memories
- **Federation**: Agent can construct SERVICE queries to external endpoints
- **Meta-learning**: Agent extracts its own memories from successful queries

---

## Curriculum Sequencing

### Option 1: Linear Progression
Execute tasks in strict dependency order (L1.1 → L1.2 → L1.3 → ...)

**Pros**: Guaranteed scaffolding, each task builds on previous
**Cons**: Slow, no parallelization

### Option 2: Breadth-First by Level
Do all L1 tasks, then all L2 tasks, etc.

**Pros**: Faster, tests each level thoroughly
**Cons**: May have dependency gaps

### Option 3: Targeted Critical Path
Focus on tasks that directly lead to gene_protein_rhea:
L1.2 → L2.1 → L2.3 → L3.1 → L3.3 → L4.1 → L4.2 → L5.1

**Pros**: Fastest path to fixing failing task
**Cons**: Narrow focus, may miss useful adjacent patterns

### Recommended: **Hybrid Approach**

1. **Week 1**: Core foundations (L1.1-L1.3, L2.1-L2.3) - 6 tasks
2. **Week 2**: Annotations (L3.1-L3.3) + Reactions (L4.1-L4.2) - 5 tasks
3. **Week 3**: Integration (L5.1) + validation
4. **Week 4+**: Branches A/B/C in parallel based on eval needs

---

## Implementation Notes

### Task Creation
Each curriculum task should be a YAML eval task with:
```yaml
task:
  id: "curriculum_L4_1_catalyzed_reactions"
  category: "curriculum/reactions"
  difficulty: "medium"
  query: "For proteins with catalytic activities, get the catalyzed Rhea reactions"

  # Memory extraction hint
  memory_hints:
    - "Pattern for linking activities to reactions"
    - "up:catalyzedReaction predicate usage"
    - "Anti-pattern: using rdfs:seeAlso for reactions"

  graders:
    - type: llm_judge
      strict: false
    - type: outcome_verification
      min_results: 1
```

### Memory Extraction Config
```python
# In task runner
if task.get('category', '').startswith('curriculum/'):
    # Force memory extraction for curriculum tasks
    extract_memories = True
    # Use LLM to extract high-quality patterns
    memory_judgment = True
```

### Memory Validation
After each level, validate memories:
```python
# Check that expected memories were extracted
required_memories = [
    "up:catalyzedReaction for reactions",
    "up:transcribedFrom for genes"
]

actual_memories = memory_backend.search("catalyzedReaction")
assert len(actual_memories) > 0, "Missing catalyzedReaction memory!"
```

---

## Open Questions

1. **How many memories is too many?**
   - 50 memories? 500? What's the retrieval quality vs quantity tradeoff?

2. **Should we curate memories or let agent extract them all?**
   - Auto-extraction may create redundant/low-quality memories
   - Manual curation is expensive but higher quality

3. **How do we prevent memory pollution?**
   - Agent might extract incorrect patterns from failed attempts
   - Need memory judgment/validation before storage

4. **What's the maintenance burden?**
   - Ontologies change (new predicates added)
   - Memories may become stale
   - Need memory versioning/deprecation strategy

5. **Can we bootstrap from existing queries?**
   - We have 71 SHACL examples in ontology/uniprot/examples/
   - Could we auto-generate curriculum tasks from these?
   - Could we extract patterns directly from exemplar queries?

---

## Next Steps

### Immediate
1. **Validate approach** - Confirm this curriculum design makes sense
2. **Prioritize** - Which branch is most important? (Likely Level 1-5 core)
3. **Create first task** - Implement L1.1 as proof of concept

### Short-term
4. **Build Level 1** - Create and run L1.1, L1.2, L1.3
5. **Validate memories** - Check that useful patterns are being extracted
6. **Iterate** - Adjust curriculum based on what memories actually get created

### Medium-term
7. **Complete critical path** - L1→L2→L3→L4→L5
8. **Retest gene_protein_rhea** - Verify it now passes with memories
9. **Measure impact** - Compare pass rates with/without memory retrieval

### Long-term
10. **Expand branches** - ChEMBL, taxonomy, sequences
11. **Add federation** - F-series tasks for multi-endpoint
12. **Meta-learning** - Agent creates its own curriculum tasks

---

## Related Documents

- **Multi-service federation strategy**: `docs/planning/multi-service-federation-strategy.md`
- **ReasoningBank meta-learning**: `docs/design/reasoningbank-meta-learning.md`
- **Trajectory v3**: `docs/planning/trajectory_v3.md`

---

## Status

**Status**: Proposal for discussion
**Next owner**: Needs validation and prioritization decision
**Estimated effort**: 2-4 weeks for Phase 1-2 (core patterns to fix gene_protein_rhea)
