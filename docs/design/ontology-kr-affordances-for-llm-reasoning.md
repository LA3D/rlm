# Ontology KR Affordances for LLM Reasoning

**Created**: 2026-01-26
**Status**: Research Design / Active Discussion
**Purpose**: Define what symbolic structures in ontologies LLMs can effectively leverage for SPARQL query construction via Chain-of-Thought reasoning

## Research Question

**What symbolic structures of ontologies can LLMs effectively use and take advantage of for SPARQL query construction from natural language questions?**

This is fundamentally about the **interface between symbolic AI (ontologies, KR) and neural AI (LLMs)** - what formal constructs translate into useful reasoning affordances?

### Sub-questions

1. Which ontological constructs (classes, properties, axioms, patterns) do LLMs "understand" and leverage?
2. How do different levels of KR formalization affect LLM reasoning quality?
3. What's the minimal/optimal KR structure for LLM-based query construction?
4. How should ontology "sense" be presented to enable effective CoT reflection?

---

## Background: OWL/RDFS Influenced Modern KR Systems

The research is grounded in understanding that OWL/RDFS concepts inspired many modern KR systems, including Wikidata's property-based model. However, different systems use different levels of formalization:

| System | KR Approach | Formalization Level |
|--------|------------|---------------------|
| **RDFS** | Class/property hierarchies | Low |
| **SKOS** | Concept schemes, labels | Low |
| **OWL** | Description logic axioms | High |
| **SHACL** | Constraint shapes | Medium (validation-focused) |
| **Wikidata** | Property graph + reification | Medium (community conventions) |

The question is: **which level of formalization translates into LLM reasoning affordances?**

---

## Ontology Categorization by KR Level

Based on analysis of the `ontology/` directory:

| Level | Type | Examples | Characteristics | Size |
|-------|------|----------|-----------------|------|
| **L0** | Vocabulary | `skos.ttl`, `rdfs.ttl` | Labels, hierarchies, no axioms | <300 lines |
| **L1** | Domain Ontology | `prov.ttl` | Classes, properties, domain/range | ~2.5K lines |
| **L2** | Upper + Patterns | `dul/DUL.ttl`, `sio/` | Ontology Design Patterns, rich semantics | 2-25K lines |
| **L3** | Standard + Examples | `ogc-geosparql/` | Vocabulary + SPARQL examples + SHACL | Multi-file |
| **L4** | Full KB + SHACL | `uniprot/`, `pubchem/` | Schema + constraints + 126+ examples | Large |

### Key Observations

**DUL (DOLCE+DnS Ultralite)** is particularly interesting for patterns:
- Explicit modeling patterns documented in `rdfs:comment`
- Five different approaches for data value assertion
- Quality-Region patterns for measurements
- Description-Situation patterns for plans/execution

**GeoSPARQL** demonstrates the L3 "standard + examples" pattern:
- `vocabularies/` - Core ontology
- `examples/` - Concrete SPARQL query examples
- `alignments/` - Mappings to other ontologies
- SHACL shapes for validation

**UniProt** represents the richest affordance surface (L4):
- Core ontology (`core.ttl`)
- 126 SPARQL examples organized by topic
- SHACL shapes
- Live SPARQL endpoint for verification

---

## Symbolic Structures Taxonomy

### Structures Available in Ontologies

| Structure | OWL/RDFS Construct | What it Provides |
|-----------|-------------------|------------------|
| **Labels** | `rdfs:label`, `skos:prefLabel` | Natural language bridge |
| **Comments** | `rdfs:comment`, `dcterms:description` | Intent/usage hints |
| **Hierarchy** | `rdfs:subClassOf`, `rdfs:subPropertyOf` | Taxonomic navigation |
| **Domain/Range** | `rdfs:domain`, `rdfs:range` | Type constraints for joins |
| **Inverse** | `owl:inverseOf` | Bidirectional navigation |
| **Transitivity** | `owl:TransitiveProperty` | Path inference |
| **Symmetry** | `owl:SymmetricProperty` | Bidirectional equality |
| **Cardinality** | `owl:minCardinality`, etc. | Multiplicity constraints |
| **Restrictions** | `owl:someValuesFrom`, `owl:allValuesFrom` | Existential/universal |
| **Defined Classes** | `owl:equivalentClass` + restrictions | Necessary & sufficient |
| **Patterns** | ODPs (participation, roles, etc.) | Modeling idioms |
| **Examples** | SHACL `sh:SPARQLExecutable` | Concrete query templates |
| **Constraints** | SHACL shapes | Validation rules |

### Hypothesized LLM Leverage by Structure

| Structure | Hypothesis | Reasoning |
|-----------|------------|-----------|
| **Labels/Comments** | **High** | Direct natural language match |
| **Class Hierarchy** | **Moderate** | Structural navigation, well-represented in training data |
| **Domain/Range** | **Moderate** | Guides joins, type inference |
| **Examples** | **High** | Pattern matching, in-context learning |
| **Inverse Properties** | **?** | Do LLMs recognize and use this? |
| **Transitivity** | **?** | Or do they just use `+` syntax pattern? |
| **Complex Axioms** | **Low** | LLMs don't reason formally |
| **ODPs** | **High if explicit** | Need explicit description, not implicit |

**Core Hypothesis**: LLMs don't reason with formal semantics - they **pattern-match on structure**. This means:
- Rich `rdfs:comment` annotations > complex OWL axioms
- Explicit pattern descriptions > implicit formal patterns
- Examples > definitions

---

## PDDL-INSTRUCT: A Framework for Symbolic Reasoning with LLMs

### Key Paper: "Teaching LLMs to Plan: Logical Chain-of-Thought Instruction Tuning for Symbolic Planning" (arXiv:2509.13351v1)

This paper provides a potential general approach for teaching LLMs to leverage symbolic structures.

### Core Insight: Decomposition into Verifiable Reasoning Chains

PDDL planning is structured as explicit state-action-state sequences:

```
⟨s₀, a₁, s₁⟩ → ⟨s₁, a₂, s₂⟩ → ... → ⟨sₙ₋₁, aₙ, sₙ⟩
```

Each step involves:
1. **Check preconditions** against current state
2. **Apply effects** (add/delete predicates)
3. **Verify state transition**
4. **Check goal progress**

**Result**: 28% → 94% accuracy on Blocksworld with this structured approach.

### Two-Phase Training

1. **Phase 1 (Initial Instruction Tuning)**: Learn what valid patterns look like
   - Both correct AND incorrect examples
   - Explanations of WHY each action is valid/invalid

2. **Phase 2 (CoT Instruction Tuning)**: Learn to reason about patterns
   - Generate reasoning chains
   - External verification (VAL validator)
   - Feedback loop with detailed error information

### Critical Finding: Detailed Feedback >> Binary Feedback

| Feedback Type | Mystery Blocksworld Accuracy |
|---------------|------------------------------|
| Binary (valid/invalid) | 49% |
| Detailed (why it failed) | 64% |

**Implication**: Specific reasoning about WHY queries fail helps more than just pass/fail.

### External Verification is Essential

The paper explicitly notes: *"LLMs do not possess sufficient self-correction capabilities in terms of reasoning."*

External verification (VAL for PDDL) provides ground-truth feedback that enables learning.

---

## Mapping PDDL-INSTRUCT to Ontology/SPARQL

### Structural Analogies

| PDDL Concept | Ontology/SPARQL Analog |
|--------------|----------------------|
| **Fluents (predicates)** | RDF triples, graph state |
| **Preconditions** | Domain/range constraints, SHACL shapes |
| **Effects** | Query patterns matched, results returned |
| **Actions** | SPARQL graph patterns, property paths |
| **State** | Current query being constructed |
| **State transitions** | Adding triple patterns to query |
| **Goal conditions** | Answering the NL question correctly |
| **VAL verifier** | SPARQL execution + result validation |

### PDDL-INSTRUCT Style Reasoning for SPARQL

```
[Step 1: Identify needed concepts]
- Query asks for: "proteins with disease annotations"
- Ontology classes: up:Protein, up:Disease_Annotation
- Precondition check: Both classes exist ✓

[Step 2: Find connecting property]
- Looking for: Protein → Annotation link
- Check: up:annotation property
- Domain: up:Protein ✓, Range: up:Annotation ✓
- Property path valid ✓

[Step 3: Construct pattern]
- Pattern: ?protein up:annotation ?ann . ?ann a up:Disease_Annotation
- Verify: Consistent with domain/range ✓

[Step 4: Execute and verify]
- Run query, check results
- Evidence: 1,247 results returned ✓
- Goal achieved ✓
```

### Implications for Sense Guides

**Current approach** (schema enumeration):
```
Classes: up:Protein, up:Annotation, up:Disease_Annotation
Properties: up:annotation (domain: Protein, range: Annotation)
```

**PDDL-INSTRUCT inspired approach** (reasoning patterns):
```
[Pattern: Finding annotations of a specific type]

Preconditions:
- Need: Entity class (e.g., up:Protein)
- Need: Annotation type (e.g., up:Disease_Annotation)
- Verify: up:annotation connects Entity → Annotation

Valid Construction:
  ?entity up:annotation ?ann .
  ?ann a <AnnotationType> .

Invalid Pattern (and why):
  ?entity a up:Disease_Annotation .
  # WRONG: Proteins aren't annotations
  # up:Disease_Annotation is annotation type, not entity type

Verification:
- Execute with LIMIT 10
- Check: Results have expected structure
```

---

## Connection to Existing Work

### Agent Guide Generation Experiments (Jan 24, 2026)

Four approaches were tested for generating AGENT_GUIDE.md files:

| Approach | Method | Result |
|----------|--------|--------|
| **Direct LLM** | Full ontology in single prompt | Fast but truncates large ontologies |
| **RLM** | DSPy RLM with bounded tools | Comprehensive but "overwhelming" |
| **DSPy ReAct** | Structured tool calls | Good affordances, efficient |
| **Scratchpad** | Persistent namespace + direct functions | **Best on large ontologies** |

**Key Finding**: Scratchpad pattern (original RLM design) outperformed current DSPy RLM on both speed and comprehensiveness.

**Relevance**: The scratchpad approach maintains **state across iterations** - analogous to PDDL-INSTRUCT's state tracking.

### E002: Think-Act-Verify-Reflect

The E002 experiment added explicit reasoning fields to query construction:
- Thinking: What needs to be done
- Verification: Check results match expectations
- Reflection: Does evidence include actual data?

**Result**: E. coli K12 pass rate improved 0% → 100% (preliminary, N=1)

**Relevance**: This is a lightweight version of PDDL-INSTRUCT's CoT approach.

### Procedural Memory Curriculum (Jan 23, 2026)

Designed a 5-level curriculum to build procedural memory for complex queries:
- Level 1: Basic entity retrieval
- Level 2: Cross-references
- Level 3: Annotations
- Level 4: Reactions (the key missing patterns)
- Level 5: Multi-hop integration

**Relevance**: This curriculum approach aligns with PDDL-INSTRUCT's instruction tuning on progressively complex examples.

---

## Open Questions: ReasoningBank and RLM Architecture

### How Does ReasoningBank Fit?

The SQLite-backed ReasoningBank stores procedural memories extracted from successful query construction runs.

**Potential roles**:

1. **Memory as "Instruction Examples"**: Retrieved memories could serve as PDDL-INSTRUCT-style examples for the current query
   - Instead of pre-training, memories provide in-context examples
   - BM25 retrieval finds relevant patterns

2. **Memory as "Detailed Feedback"**: Failed attempts with extracted lessons become negative examples
   - "Don't use rdfs:seeAlso for reactions, use up:catalyzedReaction"
   - Explicit anti-patterns with explanations

3. **Memory as "State Transition History"**: Store successful reasoning chains
   - ⟨question, step₁, step₂, ..., query, results⟩
   - Retrieve similar reasoning chains for new questions

### How Does RLM Architecture Fit?

The RLM (Recursive Language Model) architecture has several relevant properties:

1. **Context Externalization**: Large context (graphs, results) stays in REPL; model sees bounded summaries
   - Maps to PDDL-INSTRUCT's state representation

2. **REPL-first Discovery**: Agent explores via bounded view functions before answering
   - Maps to precondition checking (does this class/property exist?)

3. **Recursive Delegation**: Sub-LLM calls for meaning extraction
   - Could be used for detailed verification feedback

4. **Handles-not-dumps**: Results stored as handles; inspection via bounded views
   - State remains manageable across iterations

5. **Bounded Iteration**: Max iterations and call budgets enforced
   - Maps to PDDL-INSTRUCT's iteration limit (η)

### Questions to Explore

1. **Can ReasoningBank memories substitute for instruction tuning?**
   - PDDL-INSTRUCT fine-tunes the model
   - We retrieve memories into context
   - Is in-context learning sufficient, or is something lost?

2. **What's the right "state" representation for SPARQL construction?**
   - Current query being built?
   - Ontology exploration history?
   - Both?

3. **What's the "VAL validator" equivalent for SPARQL?**
   - SPARQL execution + result checking?
   - SHACL validation?
   - LLM judge?

4. **How do we generate "detailed feedback" for failed queries?**
   - Parse SPARQL errors?
   - Compare results to expectations?
   - Use sub-LLM to analyze failures?

5. **Does the scratchpad pattern align with PDDL-INSTRUCT's state tracking?**
   - Persistent namespace = state
   - Direct functions = actions
   - History truncation = bounded context

---

## Proposed Experimental Framework

### E-KR-001: Sense Guide Structure Comparison

**Question**: Does PDDL-INSTRUCT-style reasoning patterns outperform schema enumeration?

**Design**:
- **Guide Type A** (Schema): Current AGENT_GUIDE.md style (class/property lists)
- **Guide Type B** (Patterns): PDDL-INSTRUCT style with:
  - Precondition checking templates
  - Valid/invalid pattern examples with explanations
  - Explicit verification steps

**Ontologies**: PROV (L1), UniProt (L4)

**Measure**: Query construction accuracy, iteration count, evidence quality

### E-KR-002: KR Level Impact on CoT Quality

**Question**: Does higher KR complexity improve query construction?

**Design**: Test same query complexity across ontologies of different KR levels

**Ontologies**:
- L1: PROV
- L2: DUL (upper ontology with patterns)
- L3: GeoSPARQL (with examples)
- L4: UniProt (full KB)

### E-KR-003: ReasoningBank as Instruction Examples

**Question**: Can retrieved memories substitute for instruction tuning?

**Design**:
- **Condition A**: No memories
- **Condition B**: Memories as context (current approach)
- **Condition C**: Memories formatted as PDDL-INSTRUCT examples

**Measure**: Pass rate difference, memory utilization

### E-KR-004: External Verification Impact

**Question**: Does detailed execution feedback improve query construction?

**Design**:
- **Condition A**: No execution feedback
- **Condition B**: Binary feedback (query succeeded/failed)
- **Condition C**: Detailed feedback (why it failed, which results were unexpected)

---

## Next Steps

1. **Prototype PDDL-INSTRUCT style guide** for PROV or UniProt
2. **Define "state" representation** for SPARQL query construction
3. **Design verification/feedback mechanism** using SPARQL execution
4. **Connect to ReasoningBank** for memory-as-examples approach
5. **Evaluate against current RLM architecture** to understand gaps

---

## References

- PDDL-INSTRUCT paper: arXiv:2509.13351v1
- Agent guide generation experiments: `experiments/agent_guide_generation/`
- Procedural memory curriculum: `docs/planning/procedural-memory-curriculum.md`
- ReasoningBank architecture: `docs/design/reasoningbank-sqlite-architecture.md`
- E002 Think-Act-Verify-Reflect: `evals/experiments/E002_rung1_think_act_verify_reflect/`
