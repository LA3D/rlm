# Multi-Service Federation Query Strategy
**Created**: 2026-01-23
**Status**: Planning / Open Question
**Priority**: Medium (after core eval system stabilizes)

## Problem Statement

The dopamine eval task (uniprot_dopamine_similarity_variants_disease_001) requires multi-service federated SPARQL queries that the current RLM agent cannot construct. This represents a class of complex bioinformatics queries that require:

1. **Chemical similarity search** (IDSM/SACHEM service)
2. **Reaction database queries** (Rhea)
3. **Protein database queries** (UniProt)
4. **Complex cross-database linking**

**Current status**: Agent fails legitimately because it lacks the tools, vocabulary knowledge, and federation patterns to construct these queries.

---

## Exemplar Query Analysis

### The Dopamine Query

From: `ontology/uniprot/examples/UniProt/71_enzymes_interacting_with_molecules_similar_to_dopamine_with_variants_related_to_disease.ttl`

```sparql
PREFIX CHEBI: <http://purl.obolibrary.org/obo/CHEBI_>
PREFIX rh: <http://rdf.rhea-db.org/>
PREFIX sachem: <http://bioinfo.uochb.cas.cz/rdf/v1.0/sachem#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX up: <http://purl.uniprot.org/core/>

SELECT ?protein ?rhea ?chebi ?disease
WHERE {
  # 1. Chemical similarity search on IDSM endpoint
  SERVICE <https://idsm.elixir-czech.cz/sparql/endpoint/chebi>{
    ?chebi sachem:similarCompoundSearch [
      sachem:query "NCCc1ccc(O)c(O)c1" ] .  # SMILES for dopamine CHEBI:18243
  }

  # 2. Federated query to Rhea reaction database
  GRAPH<https://sparql.rhea-db.org/rhea>{
    ?rhea rh:side/rh:contains/rh:compound ?compound .
    ?compound (rh:chebi|(rh:reactivePart/rh:chebi)|rh:underlyingChebi) ?chebi .
  }

  # 3. Link to UniProt proteins with disease variants
  ?protein up:reviewed true ;
    up:annotation ?caa, ?natural_variant_annotation, ?disease_annotation .
  ?caa up:catalyticActivity/up:catalyzedReaction ?rhea .
  ?natural_variant_annotation a up:Natural_Variant_Annotation ;
    skos:related ?disease .
  ?disease_annotation a up:Disease_Annotation ;
    up:disease ?disease .
}
```

### Why This is Hard

**Three distinct challenges:**

1. **Multi-endpoint federation**
   - IDSM endpoint (chemical search)
   - Rhea endpoint (reactions)
   - UniProt endpoint (proteins)
   - Each has different vocabulary and data model

2. **Specialized vocabulary knowledge**
   - `sachem:similarCompoundSearch` - Not discoverable from UniProt ontology
   - SMILES structures - Requires external knowledge
   - `rh:side/rh:contains/rh:compound` - Complex Rhea property paths
   - ChEBI identifier mapping

3. **Complex join patterns**
   - Chemical → Reaction (via ChEBI ID)
   - Reaction → Protein (via Rhea ID)
   - Protein → Disease (via annotations)
   - Requires understanding cross-database identifiers

---

## Current Agent Limitations

### What the Agent Can't Do (Yet)

1. **No access to IDSM/Rhea endpoints**
   - Current tools only expose UniProt SPARQL endpoint
   - No chemical similarity search capability
   - No reaction database access

2. **No multi-service federation patterns**
   - Tools are single-endpoint focused
   - No examples of SERVICE clauses with multiple endpoints
   - No vocabulary for cross-database linking

3. **No chemical structure knowledge**
   - Doesn't know SMILES notation
   - Can't look up chemical structures for compounds
   - No access to ChEBI vocabulary

4. **No Rhea vocabulary**
   - Doesn't know `rh:side`, `rh:contains`, property paths
   - No examples of Rhea query patterns
   - No understanding of reaction representation

### What the Agent CAN Do

- ✅ Single-endpoint SPARQL queries (UniProt)
- ✅ Progressive disclosure over local ontologies
- ✅ Bounded view exploration
- ✅ Simple federated queries (single SERVICE clause with known vocabulary)
- ✅ UniProt-specific vocabulary (proteins, annotations, diseases)

---

## Potential Solutions

### Short-term: Downscope Task

**Option 1a**: Mark task as "research-level" or skip
- Accept this as beyond current scope
- Use as benchmark for future capabilities
- Don't penalize agent for failing this task

**Option 1b**: Simplify task to single-service query
- Remove chemical similarity search requirement
- Focus on UniProt → Rhea linking only
- Example: "Find proteins that catalyze dopamine-related reactions (use Rhea cross-references)"

### Medium-term: Provide Additional Context

**Option 2a**: Enhanced sense cards with federation patterns
- Include SHACL examples showing multi-service queries
- Document SACHEM vocabulary in sense card
- Provide SMILES lookup examples

**Option 2b**: Expand tool surface
- Add IDSM endpoint tools with chemical similarity search
- Add Rhea endpoint tools with reaction queries
- Provide federation examples in tool descriptions

**Option 2c**: Multi-endpoint tool abstraction
```python
def federated_query(
    primary_endpoint: str,
    federated_services: dict[str, str],  # {service_name: endpoint_url}
    query: str
) -> ResultHandle
```

### Long-term: Research-Level Capabilities

**Option 3a**: Meta-learning for federation patterns
- Store successful multi-service queries in ReasoningBank
- Retrieve federation patterns based on endpoint combinations
- Learn SERVICE clause structure from examples

**Option 3b**: Vocabulary discovery across endpoints
- Crawl VOID descriptions for endpoints
- Index vocabularies from SHACL shapes
- Build cross-endpoint identifier mappings

**Option 3c**: Chemical informatics integration
- Add ChEBI lookup tool for SMILES structures
- Integrate PubChem/ChemSpider for chemical search
- Provide compound identifier translation

**Option 3d**: Multi-agent collaboration
- Specialist agents for each endpoint (IDSM, Rhea, UniProt)
- Coordinator agent orchestrates federation
- Each specialist provides endpoint-specific expertise

---

## Decision Criteria

Before implementing any solution, consider:

1. **Use case frequency**: How common are multi-service federation tasks?
   - Are there other examples in the eval suite?
   - Is this a real-world need for users?

2. **Tool complexity**: How much infrastructure is needed?
   - Does it require new endpoint access?
   - Are there authentication/API key requirements?
   - What's the maintenance burden?

3. **Eval suite goals**: What are we actually testing?
   - Progressive disclosure over complex schemas?
   - Federation capability?
   - Chemical informatics knowledge?
   - All of the above?

4. **Agent architecture fit**: Does it align with RLM principles?
   - Bounded views (yes - if tools are bounded)
   - Progressive disclosure (yes - if vocabularies are explorable)
   - Handles not dumps (yes - if results are handles)

---

## Recommended Next Steps

### Immediate (Post-Baseline Eval)

1. **Mark dopamine task appropriately**
   - Add `difficulty: research` or `category: uniprot/stretch-goals`
   - Document why it's expected to fail
   - Keep as aspirational benchmark

2. **Inventory other federation tasks**
   - Check if other eval tasks have similar requirements
   - Identify patterns across multi-service queries

3. **Document federation gap**
   - Create list of missing vocabularies (SACHEM, Rhea)
   - Document missing endpoints (IDSM, Rhea)
   - Prioritize by eval task coverage

### Medium-term (After Core System Stabilizes)

4. **Prototype federation tool design**
   - Design bounded multi-endpoint tool interface
   - Test with simplified two-endpoint query
   - Validate that agent can discover SERVICE patterns

5. **Evaluate sense card approach**
   - Add SHACL examples for simple federation
   - Test if agent can learn federation patterns
   - Measure whether examples are sufficient

### Long-term (Research Direction)

6. **Multi-agent federation experiment**
   - Prototype specialist agents for each endpoint
   - Test coordinator pattern for query assembly
   - Compare to single-agent with multi-endpoint tools

7. **Meta-learning for federation**
   - Store successful federation queries in memory
   - Implement cross-endpoint pattern retrieval
   - Measure impact on complex query success rate

---

## Related Issues

- **Tool provisioning gap** (docs/design/tool-provisioning-gap-analysis.md)
  - How do we provide endpoint-specific tools dynamically?
  - How do we discover what endpoints a query needs?

- **SHACL-driven query construction** (trajectory_v2.md Phase D)
  - Can SHACL examples teach federation patterns?
  - Do we need federation-specific SHACL shapes?

- **ReasoningBank meta-learning** (docs/design/reasoningbank-meta-learning.md)
  - Can procedural memories capture federation patterns?
  - How do we index memories by endpoint combinations?

---

## Open Questions

1. **Should we support multi-service federation at all?**
   - Is this in scope for RLM ontology query construction?
   - Or should we focus on single-endpoint mastery first?

2. **What's the right abstraction level for tools?**
   - Per-endpoint tools (IDSM tool, Rhea tool, UniProt tool)?
   - Generic federated query tool?
   - Multi-step workflow with intermediate results?

3. **How do we teach vocabulary for external services?**
   - Crawl and index VOID descriptions?
   - Manually curated sense cards?
   - Let agent discover through trial and error?

4. **What's the evaluation strategy?**
   - Mark multi-service tasks as "research-level"?
   - Create separate eval suite for federation?
   - Use as stretch goals to measure progress?

---

## References

- **Dopamine task**: `evals/tasks/uniprot/complex/uniprot_dopamine_similarity_variants_disease_001.yaml`
- **Exemplar query**: `ontology/uniprot/examples/UniProt/71_enzymes_interacting_with_molecules_similar_to_dopamine_with_variants_related_to_disease.ttl`
- **IDSM SPARQL**: https://idsm.elixir-czech.cz/sparql/endpoint/chebi
- **Rhea SPARQL**: https://sparql.rhea-db.org/sparql/
- **SACHEM documentation**: http://bioinfo.uochb.cas.cz/rdf/v1.0/sachem

---

## Status: Open for Discussion

This document captures the challenge but doesn't prescribe a solution. We should revisit this after:
- Baseline eval suite is stable
- Core RLM capabilities are validated
- We've measured how often multi-service queries are actually needed

**For now**: Accept dopamine task failure as expected, keep as aspirational benchmark.
