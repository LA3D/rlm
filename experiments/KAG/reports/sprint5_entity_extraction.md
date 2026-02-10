# KAG Sprint 5: Multi-Ontology Entity Extraction

**Date:** 2026-02-10
**Paper tested:** Chemrxiv (Diels-Alder, 8 pages, 116 blocks)
**Model:** Claude Sonnet 4.5 (agent), Claude Haiku 4.5 (sub-LM)
**Run IDs:** `kag_entity_chemrxiv_20260210T215259Z` (v1), `kag_entity_chemrxiv_v2_20260210T220022Z` (v2)

---

## 1. Motivation

Sprints 1-4 built a complete document graph pipeline (G_doc) — DoCO structure,
SHACL validation, full-text persistence, enrichment, and QA. But the graphs
capture **document structure**, not **scientific knowledge**. A paper's key
contributions — entities, measurements, claims — are locked inside paragraph
text, not first-class graph citizens.

Sprint 5 extends KAG from single-graph document indexing to **multi-ontology
entity extraction**: a three-layer hypergraph where entities, measurements,
and claims are extracted into separate graphs with provenance links back to
the source document.

| Gap | Severity | Sprint 5 Solution |
|---|---|---|
| No entity representation | Critical | G_entity with SIO + QUDT |
| No claim representation | Critical | G_claim with SIO + PROV |
| No cross-layer provenance | High | `prov:wasDerivedFrom` to G_doc spans |
| No measurement structure | High | `qudt:QuantityValue` + `qudt:unit` |
| No namespace isolation | Medium | `GraphProfile` contracts per layer |
| Single-graph architecture | Medium | `KagEntityWorkspace` multi-graph manager |

## 2. Architecture

### Three-Layer Graph

```
G_doc (read-only)          G_entity (new)              G_claim (new)
DoCO + DEO + KAG           SIO + QUDT                  SIO + PROV + CiTO
──────────────────         ──────────────              ─────────────────
Document                   sio:ChemicalEntity          sio:Proposition
  Section                    rdfs:label                  rdfs:label
  Paragraph                  prov:wasDerivedFrom         sio:is-about -> G_entity
  Figure/Table               sio:has-measurement-value   prov:wasDerivedFrom -> G_doc
  BibliographicRef         qudt:QuantityValue
                             qudt:numericValue
                             qudt:unit
```

**Cross-graph links:**
- G_entity → G_doc: entities grounded to source paragraphs (`prov:wasDerivedFrom`)
- G_claim → G_entity: claims reference entities (`sio:is-about`)
- G_claim → G_doc: claims grounded to source paragraphs (`prov:wasDerivedFrom`)

### GraphProfile Contracts

Each graph has a `GraphProfile` that enforces namespace purity:

| Graph | Allowed Namespaces | Read-Only |
|---|---|---|
| doc | doco, deo, kag, ex, cito | Yes |
| entity | sio, qudt, quantitykind, unit, ex, prov, rdfs | No |
| claim | sio, prov, cito, ex, rdfs | No |

Mutations to G_doc are blocked at the tool level. Predicates from wrong
namespaces (e.g., `doco:` in G_entity) are rejected.

### Tool Surface (12 tools)

| Category | Tool | Purpose |
|---|---|---|
| Read (G_doc) | `g_section_content` | Section children |
| Read (G_doc) | `g_node_detail` | Full node properties |
| Read (G_doc) | `g_search` | Full-text search |
| Read (G_doc) | `g_figure_info` | Figure details |
| Read (G_doc) | `g_node_refs` | Citations/cross-refs |
| Write | `op_create_entity` | Create entity in target graph |
| Write | `op_assert_type` | Add rdf:type |
| Write | `op_set_literal` | Set/replace literal property |
| Write | `op_add_link` | Add IRI triple |
| Write | `op_set_link` | Replace IRI triple |
| Validate | `validate_graph` | Per-layer + cross-graph SHACL |
| Validate | `finalize_graph` | Gate SUBMIT on conformance |

Key design: **tools are generic graph operators; ontology knowledge lives in
sense cards** (SIO ~1K chars, QUDT ~800 chars, PROV ~300 chars).

## 3. What Was Built

### Ontology Subsets (Phase 1)

| File | Triples | Contents |
|---|---|---|
| `sio_subset.ttl` | 100 | 12 classes (Entity hierarchy), 12 properties |
| `qudt_subset.ttl` | 105 | 3 schema classes, 3 properties, 16 quantity kinds, 25 units |
| `kag_entity_shapes.ttl` | 76 | SHACL for Entity, MaterialEntity, ChemicalEntity, Process, MeasuredValue, QuantityValue |
| `kag_claim_shapes.ttl` | 30 | SHACL for Proposition, Evidence |

SHACL shapes enforce:
- Every entity: `rdfs:label` + `prov:wasDerivedFrom` (including MeasuredValue)
- MeasuredValue: `qudt:numericValue` + `qudt:unit`
- Proposition: `rdfs:label` + `sio:is-about` + `prov:wasDerivedFrom`
- Evidence: `rdfs:label` + `sio:is-evidence-for` + `prov:wasDerivedFrom`

### Multi-Graph Workspace (Phase 2)

`kag_entity_workspace.py` — `KagEntityWorkspace`:
- Loads G_doc from Sprint 4 TTL output as read-only base
- Creates empty G_entity and G_claim as mutable working graphs
- `GraphProfile` namespace guards on all mutations
- `resolve_iri()` with CURIE support for 11 prefixes + bare-name auto-prefixing
- Per-layer SHACL validation + cross-graph grounding check
- `finalize_graph()` gate across all layers
- `serialize()` exports G_entity and G_claim as TTL

### Entity Toolset (Phase 3)

`kag_entity_tools.py` — `KagEntityToolset`:
- 5 QA read tools delegated to existing `KagQAToolset`
- 7 write tools wrapped with error swallowing (never re-raise in Pyodide)
- `graph` parameter routes to G_entity or G_claim
- `as_tools()` returns flat list of 12 callables for DSPy RLM

### Entity Runner (Phase 4)

`rlm_kag_entity_runner.py`:
- RLM signature: `"context, task -> answer"`
- Context: G_doc overview + sections + SIO/QUDT/PROV sense cards (~3K chars)
- Task: extraction strategy + SHACL rules + IRI format + completion protocol (~2.9K chars)
- Trajectory logging with error classification (sandbox crashes, tool binding errors)
- Reuses `JsonlTrajectoryLogger` and `_wrap_tools_with_logging` from build runner

## 4. Results

### Run 1 (v1): First Attempt

| Metric | Value |
|---|---|
| SHACL conforms | **false** (26 violations) |
| G_entity triples | 270 |
| G_claim triples | 29 |
| Iterations | 20 / 20 max |
| Cost | $1.53 |
| Sandbox crashes | 0 |
| Tool binding errors | 0 |

**Root cause:** Agent used `sio:has-attribute` with bare string values
(`"TCNE"`, `"AnMe"`) instead of IRI references. RDFlib created 13 phantom
nodes without `rdfs:label` or `prov:wasDerivedFrom`, causing 26 violations
(13 missing labels + 13 missing provenance).

**Fix applied:**
1. `resolve_iri()` now auto-prefixes bare names with `ex:` (prevents relative URIs)
2. Task prompt explicitly warns: "NEVER pass bare strings — always use `ex:` prefix"
3. Task prompt clarifies: "NEVER use `sio:has-attribute` with literals — use `rdfs:label`"

### Run 2 (v2): After Fixes

| Metric | Value |
|---|---|
| SHACL conforms | **false** (2 violations) |
| G_entity triples | 236 |
| G_claim triples | 39 |
| Iterations | 24 / 25 max |
| Cost | $1.64 |
| Sandbox crashes | 0 |
| Tool binding errors | 0 |
| Cross-graph grounding | **100% valid** |

**Remaining 2 violations:** One stray `ex:TCNE` node (agent created both
`ex:tcne` and `ex:TCNE` via different code paths — case-sensitive IRI mismatch).
The G_claim layer conforms fully (0 violations).

### Extracted Knowledge (v2)

**Chemical Entities (8):**

| Entity | Label | Measurements |
|---|---|---|
| `ex:tcne` | TCNE (tetracyanoethylene) | 0 (dienophile) |
| `ex:anme` | AnMe (9,10-dimethylanthracene) | 7 |
| `ex:tmanme` | TMAnMe | 7 |
| `ex:tmanet` | TMAnEt | 7 |
| `ex:tmannbu` | TMAnnBu | 7 |
| `ex:tmannhept` | TMAnnHept | 5 |
| `ex:tmanetph` | TMAnEtPh | 1 |

**Measurements (34 QuantityValues):**

| Type | Examples |
|---|---|
| Thermodynamic | ΔG (193K, 298K), ΔH, ΔS per compound |
| Kinetic | k_obs, activation free energy (ΔG‡) at 193K |
| Equilibrium | T_eq ranging from 165°C (AnMe) to -46°C (TMAnEtPh) |

Each measurement has: `qudt:numericValue`, `qudt:unit`, `rdfs:label`,
`prov:wasDerivedFrom` (G_doc paragraph block).

**Scientific Claims (4):**

1. "Methoxy groups stabilize free anthracene platform" → about anme, tmanme
2. "Steric tuning of bridgehead substituents modulates DA thermodynamics" → about 5 derivatives
3. "Rapid DA adduct formation at low temperatures" → about 10 kinetic measurements
4. "Low-temperature retro Diels-Alder reactivity below -50°C" → about tmanetph

All claims grounded to specific G_doc paragraphs via `prov:wasDerivedFrom`.

## 5. Lessons Learned

### Bare names create phantom nodes
Agent passed `"TCNE"` instead of `"ex:tcne"` to `op_add_link`. RDFlib treated
it as a relative URI, creating an orphan node with no properties. **Fix:**
`resolve_iri()` now auto-prefixes bare names with `ex:`. Task prompt explicitly
warns against bare strings.

### MeasuredValue inherits Entity SHACL constraints
The `EntityShape` targets `sio:Entity`, and `MeasuredValue` is a subclass.
Every measurement needs `rdfs:label` + `prov:wasDerivedFrom` in addition to
`qudt:numericValue` + `qudt:unit`. The agent initially missed labels on
measurements. **Fix:** Task prompt now explicitly lists MeasuredValue constraints.

### Case-sensitive IRIs cause duplicates
Agent created `ex:tcne` in one iteration and `ex:TCNE` in another. These are
different URIs. **Potential fix:** Normalize to lowercase in `resolve_iri()`,
or add a dedup pass in enrichment.

### Cross-graph validation works as designed
The `_validate_cross_graph()` check correctly verifies that every
`prov:wasDerivedFrom` target exists in G_doc. Both runs passed this check with
zero ungrounded nodes — the provenance grounding pattern works.

### Error swallowing prevents sandbox crashes
Zero sandbox crashes across both runs (46 + 45 = 91 `op_create_entity` calls,
287 total tool calls). The `try/except → return error dict` pattern from
Sprint 4d continues to prove essential.

## 6. Comparison with Sprint 4

| Metric | Sprint 4 (Build) | Sprint 5 (Entity) |
|---|---|---|
| Input | OCR markdown | Sprint 4 G_doc (TTL) |
| Output | G_doc (DoCO) | G_entity (SIO+QUDT) + G_claim (SIO+PROV) |
| Tools | 6 build + validate | 5 read + 7 write |
| Iterations | 10-14 | 20-24 |
| Cost | $0.31-$0.48 | $1.53-$1.64 |
| SHACL conforms | 100% | 92% (2/26 remaining) |
| Sandbox crashes | 0 | 0 |

Sprint 5 is more expensive (~4x) because the agent needs to:
1. Search G_doc to find relevant content
2. Create entities with full property sets
3. Create measurements with values, units, and labels
4. Create claims with entity references and provenance
5. Validate and attempt repairs

## 7. Next Steps

1. **IRI normalization** — Lowercase bare names in `resolve_iri()` to prevent case duplication
2. **`op_remove_node` tool** — Let agent clean up phantom/duplicate nodes
3. **Prompt iteration** — Reduce iterations by tightening extraction strategy
4. **PET paper test** — Validate on second test paper (biological entities, K_D values)
5. **Cross-paper entity alignment** — `owl:sameAs` between co-referent entities across papers
6. **QA over hypergraph** — Extend QA tools to query G_entity + G_claim alongside G_doc

## 8. File Inventory

| File | New/Modified | Purpose |
|---|---|---|
| `kag_ontology/sio_subset.ttl` | New | Vendored SIO subset (100 triples) |
| `kag_ontology/qudt_subset.ttl` | New | Vendored QUDT subset (105 triples) |
| `kag_ontology/kag_entity_shapes.ttl` | New | SHACL shapes for G_entity |
| `kag_ontology/kag_claim_shapes.ttl` | New | SHACL shapes for G_claim |
| `kag_entity_workspace.py` | New | Multi-graph workspace with GraphProfile |
| `kag_entity_tools.py` | New | 12-tool surface (5 read + 7 write) |
| `rlm_kag_entity_runner.py` | New | RLM runner with sense cards |
| `run_kag_entity.py` | New | CLI entrypoint |
| `README.md` | Modified | Updated to Sprint 4 state + Sprint 5 roadmap |
| `reports/sprint5_entity_extraction.md` | New | This report |
