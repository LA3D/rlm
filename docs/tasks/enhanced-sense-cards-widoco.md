# Implementation Plan: Enhanced Sense Cards with Widoco Metadata Patterns

**Date**: 2026-01-21
**Status**: Ready for implementation
**Goal**: Enhance sense card generation with Widoco metadata patterns to provide actionable navigation guidance

## Problem Statement

Current sense cards are being ignored by the LLM:
- 0 mentions in trajectory reasoning
- Old sense cards listed generic root classes (Action, Agent, Design)
- Did not provide actionable metadata about HOW to read the ontology
- Actually slowed execution in some cases (7 iterations with sense vs 5 without)

## Solution

Focus sense cards on **HOW to read** the ontology:
- Formalism level (OWL-DL, RDFS, etc.) ✅ DONE
- Metadata conventions (SKOS, DCTERMS) ✅ DONE
- **NEW**: Import dependencies (owl:imports)
- **NEW**: Version metadata (stability signals)
- **NEW**: Deprecation warnings
- **NEW**: Maturity indicators (status annotations)
- **NEW**: Provenance patterns (PAV, PROV)

## Implementation Phases

### Phase 1: Enhance Metadata Detection (Priority Order)

#### 1.1 owl:imports Detection (HIGHEST PRIORITY)
**Why**: Critical for understanding dependencies. DUL imports from DOLCE - LLM needs to know concepts may be defined elsewhere.

**Implementation**:
```python
def detect_imports(graph: Graph) -> tuple[int, list[str]]:
    """Detect owl:imports statements.

    Returns:
        (count, list of imported ontology names)
    """
    imports = list(graph.objects(predicate=OWL.imports))
    import_names = []
    for imp in imports:
        name = str(imp).split('/')[-1].split('#')[-1]
        if name:
            import_names.append(name)
    return len(imports), import_names
```

**Format**:
- "Imports: DUL (1 ontology)"
- "Imports: DOLCE, DUL (2 ontologies)"

#### 1.2 Version Metadata (HIGH PRIORITY)
**Why**: Signals stability. Versioned ontology = mature, stable definitions.

**Detection**:
```python
def detect_version_info(graph: Graph) -> tuple[bool, Optional[str], bool]:
    """Detect version metadata.

    Returns:
        (has_version_info, version_string, has_version_iri)
    """
    version_info = None
    has_version_iri = False

    for ont in graph.subjects(RDF.type, OWL.Ontology):
        # Check versionInfo
        versions = list(graph.objects(ont, OWL.versionInfo))
        if versions:
            version_info = str(versions[0])

        # Check versionIRI
        version_iris = list(graph.objects(ont, OWL.versionIRI))
        if version_iris:
            has_version_iri = True

    return bool(version_info or has_version_iri), version_info, has_version_iri
```

**Format**: "Version: 1.2.3" or "Versioned: Yes"

#### 1.3 Deprecation Warnings (HIGH PRIORITY)
**Why**: Prevents LLM from using obsolete terms.

**Detection**:
```python
def count_deprecated_terms(graph: Graph) -> int:
    """Count deprecated terms (owl:deprecated true)."""
    deprecated = list(graph.subjects(OWL.deprecated, Literal(True)))
    return len(deprecated)
```

**Format**: "⚠ Contains 5 deprecated terms" (if count > 0)

#### 1.4 Status Annotations (MEDIUM PRIORITY)
**Why**: Indicates ontology maturity (draft vs stable).

**Detection**:
```python
from rdflib import Namespace
BIBO = Namespace("http://purl.org/ontology/bibo/")
SW = Namespace("http://www.w3.org/2003/06/sw-vocab-status/ns#")

def detect_status(graph: Graph) -> tuple[bool, Optional[str]]:
    """Detect status annotations (bibo:status, sw:term_status)."""
    has_status = False
    status_value = None

    # Check bibo:status
    for ont in graph.subjects(RDF.type, OWL.Ontology):
        statuses = list(graph.objects(ont, BIBO.status))
        if statuses:
            has_status = True
            status_value = str(statuses[0])
            break

    # Check sw:term_status usage
    if not has_status:
        term_statuses = list(graph.triples((None, SW.term_status, None)))
        has_status = len(term_statuses) > 0

    return has_status, status_value
```

**Format**: "Status: Stable" or "Status annotations present"

#### 1.5 PAV/PROV Provenance (MEDIUM PRIORITY)
**Why**: Signals best practices, but less actionable for navigation.

**Detection**:
```python
PAV = Namespace("http://purl.org/pav/")
PROV = Namespace("http://www.w3.org/ns/prov#")

def detect_provenance_vocabs(graph: Graph) -> tuple[bool, bool]:
    """Detect PAV and PROV usage."""
    uses_pav = any("purl.org/pav" in str(p) for s, p, o in graph)
    uses_prov = any("w3.org/ns/prov" in str(p) for s, p, o in graph)
    return uses_pav, uses_prov
```

**Format**: "Uses PAV provenance tracking"

#### 1.6 VANN Documentation (LOWER PRIORITY)
**Why**: Nice to have, but not critical.

**Detection**:
```python
VANN = Namespace("http://purl.org/vocab/vann/")

def detect_vann(graph: Graph) -> tuple[bool, Optional[str], bool]:
    """Detect VANN usage."""
    has_vann = False
    preferred_prefix = None
    has_examples = False

    # Check preferred namespace prefix
    for ont in graph.subjects(RDF.type, OWL.Ontology):
        prefixes = list(graph.objects(ont, VANN.preferredNamespacePrefix))
        if prefixes:
            has_vann = True
            preferred_prefix = str(prefixes[0])

    # Check for examples
    examples = list(graph.triples((None, VANN.example, None)))
    has_examples = len(examples) > 0

    return has_vann or has_examples, preferred_prefix, has_examples
```

**Format**: "Documented with VANN standards"

---

### Phase 2: Update Data Structures

#### Enhanced MetadataProfile
```python
@dataclass
class MetadataProfile:
    # Existing fields
    label_properties: list[str]
    description_properties: list[str]
    uses_skos: bool = False
    uses_void: bool = False
    uses_dcterms: bool = False
    uses_schema_org: bool = False
    uses_foaf: bool = False
    skos_concept_count: int = 0
    skos_scheme_count: int = 0

    # NEW: Versioning
    has_version_info: bool = False
    version_string: Optional[str] = None
    has_version_iri: bool = False

    # NEW: Maturity/Status
    deprecated_term_count: int = 0
    has_status_annotations: bool = False
    status_value: Optional[str] = None

    # NEW: Provenance
    uses_pav: bool = False
    uses_prov: bool = False

    # NEW: Documentation
    uses_vann: bool = False
    preferred_prefix: Optional[str] = None
    has_examples: bool = False

    # NEW: Imports
    imports_count: int = 0
    imported_ontologies: list[str] = field(default_factory=list)

    def maturity_level(self) -> str:
        """Assess ontology maturity."""
        if self.has_version_info and self.status_value in ["stable", "published"]:
            return "Stable/Mature"
        elif self.has_version_info:
            return "Versioned"
        elif self.has_status_annotations:
            return self.status_value or "In Development"
        else:
            return "Unknown"
```

#### Updated format_sense_card()
```python
def format_sense_card(card: SenseCard) -> str:
    """Format enhanced sense card (~600-700 chars)."""
    lines = [
        f"# Ontology: {card.ontology_name}",
        "",
        f"**Domain**: {card.domain_description}",
        "",
        f"**Size**: {card.triple_count:,} triples, {card.class_count} classes, {card.property_count} properties",
        "",
        f"**Formalism**: {card.formalism.description()}",
        ""
    ]

    # Version info (if available)
    if card.metadata.has_version_info:
        if card.metadata.version_string:
            lines.append(f"**Version**: {card.metadata.version_string}")
        else:
            lines.append("**Version**: Versioned")
        lines.append("")

    # Maturity/Status
    maturity = card.metadata.maturity_level()
    if maturity != "Unknown":
        lines.append(f"**Maturity**: {maturity}")
        lines.append("")

    # Imports (if any)
    if card.metadata.imports_count > 0:
        import_str = ", ".join(card.metadata.imported_ontologies[:3])
        suffix = "..." if len(card.metadata.imported_ontologies) > 3 else ""
        lines.append(f"**Imports**: {import_str}{suffix} ({card.metadata.imports_count} {'ontology' if card.metadata.imports_count == 1 else 'ontologies'})")
        lines.append("")

    # Metadata profile
    lines.append(f"**Metadata**: {card.metadata.vocabulary_summary()}")

    # Deprecation warning (if applicable)
    if card.metadata.deprecated_term_count > 0:
        lines.append(f"⚠ Contains {card.metadata.deprecated_term_count} deprecated terms")

    # Navigation guidance
    lines.append("")
    lines.append("**Navigation:**")
    lines.append(f"- Labels: Use `{card.metadata.primary_label_prop()}` property")
    lines.append(f"- Descriptions: Use `{card.metadata.primary_desc_prop()}` property")

    # Formalism-specific hints
    if card.formalism.level == "OWL-DL":
        if card.formalism.owl_disjoint_count > 0:
            lines.append(f"- Check `owl:disjointWith` for class exclusions ({card.formalism.owl_disjoint_count} axioms)")
        if card.formalism.owl_restriction_count > 0:
            lines.append(f"- Uses OWL restrictions ({card.formalism.owl_restriction_count} found)")

    if card.formalism.rdfs_subclass_count > 20:
        lines.append(f"- Rich hierarchy: {card.formalism.rdfs_subclass_count} subclass relationships")

    result = '\n'.join(lines)

    # Enforce length limit (700 chars)
    if len(result) > 700:
        # Truncate at last complete line before 700
        lines_truncated = []
        current_length = 0
        for line in lines:
            if current_length + len(line) + 1 > 700:
                break
            lines_truncated.append(line)
            current_length += len(line) + 1
        result = '\n'.join(lines_truncated)

    return result
```

---

### Phase 3: Testing Strategy

#### Test Matrix

| Ontology | Query | Condition | Expected |
|----------|-------|-----------|----------|
| PROV | "What is Activity?" | Baseline (no sense) | 4-5 iterations |
| PROV | "What is Activity?" | Old sense (root classes) | 4-5 iterations (ignored) |
| PROV | "What is Activity?" | New sense (Widoco) | 3-4 iterations (if helpful) |
| SystemsLite | "PhysicalSystem vs NonPhysicalSystem" | Baseline | 5-6 iterations |
| SystemsLite | "PhysicalSystem vs NonPhysicalSystem" | Old sense | 6-7 iterations (slows down!) |
| SystemsLite | "PhysicalSystem vs NonPhysicalSystem" | New sense | 4-5 iterations (if helpful) |
| PROV | "How do Entity and Activity relate?" | Baseline | 5-6 iterations |
| PROV | "How do Entity and Activity relate?" | Old sense | 5-7 iterations |
| PROV | "How do Entity and Activity relate?" | New sense | 4-5 iterations (if helpful) |

#### Metrics

**Per test run, collect:**
1. **Iteration count** (primary metric)
2. **Converged** (must be True)
3. **Answer length** (chars)
4. **Evidence field count**
5. **SPARQL generated** (yes/no)
6. **Sense card mentions** (count of references in reasoning)

#### Test Script

Create `examples/test_sense_effectiveness.py`:

```python
"""Comparative test: Baseline vs Old Sense vs New Sense cards."""

import os
import sys
import json
from pathlib import Path
from dataclasses import dataclass

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm
from rlm_runtime.ontology import build_sense_card, format_sense_card
from rlm.ontology import build_sense_structured, format_sense_card as format_old_sense

@dataclass
class TestResult:
    condition: str
    iterations: int
    converged: bool
    answer_length: int
    evidence_fields: int
    has_sparql: bool
    sense_mentions: int

def count_sense_mentions(log_path: Path) -> int:
    """Count sense card references in LLM reasoning."""
    keywords = [
        "formalism", "owl-dl", "restriction", "disjoint",
        "version", "import", "deprecated", "hierarchy",
        "metadata", "navigation"
    ]

    count = 0
    with open(log_path) as f:
        for line in f:
            event = json.loads(line)
            if event.get('event') == 'llm_response':
                outputs = event.get('outputs', [])
                if outputs and isinstance(outputs[0], str):
                    text = outputs[0].lower()
                    for keyword in keywords:
                        if keyword in text:
                            count += 1
                            break
    return count

def run_test(ontology_path: Path, query: str, ontology_name: str, condition: str) -> TestResult:
    """Run test with specified condition."""
    log_path = project_root / f"test_{ontology_name}_{condition}.jsonl"

    # Determine sense card
    sense_card = None
    if condition == "old_sense":
        sense = build_sense_structured(str(ontology_path), name=f"{ontology_name}_sense", ns={})
        sense_card = format_old_sense(sense['sense_card'])
    elif condition == "new_sense":
        card = build_sense_card(str(ontology_path), ontology_name)
        sense_card = format_sense_card(card)

    # Run test
    result = run_dspy_rlm(
        query,
        str(ontology_path),
        sense_card=sense_card,
        max_iterations=8,
        max_llm_calls=20,
        log_path=str(log_path),
        verbose=False
    )

    # Count sense mentions
    sense_mentions = count_sense_mentions(log_path) if sense_card else 0

    return TestResult(
        condition=condition,
        iterations=result.iteration_count,
        converged=result.converged,
        answer_length=len(result.answer),
        evidence_fields=len(result.evidence) if result.evidence else 0,
        has_sparql=bool(result.sparql),
        sense_mentions=sense_mentions
    )

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    tests = [
        ("ontology/prov.ttl", "What is Activity in PROV?", "prov"),
        ("ontology/dul/SystemsLite.ttl", "What is the difference between a PhysicalSystem and a NonPhysicalSystem in SystemsLite?", "systemslite"),
        ("ontology/prov.ttl", "How do Entity and Activity relate in PROV?", "prov_relation"),
    ]

    results = []

    for ontology_path, query, name in tests:
        print(f"\n{'='*80}")
        print(f"Testing: {name}")
        print(f"Query: {query}")
        print(f"{'='*80}\n")

        for condition in ["baseline", "old_sense", "new_sense"]:
            print(f"  Running condition: {condition}...")
            result = run_test(Path(ontology_path), query, name, condition)
            results.append((name, result))
            print(f"    → {result.iterations} iterations, converged={result.converged}")

    # Print comparison table
    print(f"\n{'='*80}")
    print("RESULTS SUMMARY")
    print(f"{'='*80}\n")

    for test_name in ["prov", "systemslite", "prov_relation"]:
        print(f"\n{test_name.upper()}:")
        test_results = [r for n, r in results if n == test_name]

        print(f"  {'Condition':<15} {'Iter':>4} {'Conv':>5} {'Ans':>6} {'Evid':>4} {'SPARQL':>7} {'Mentions':>8}")
        print(f"  {'-'*15} {'-'*4} {'-'*5} {'-'*6} {'-'*4} {'-'*7} {'-'*8}")
        for r in test_results:
            print(f"  {r.condition:<15} {r.iterations:>4} {str(r.converged):>5} {r.answer_length:>6} {r.evidence_fields:>4} {str(r.has_sparql):>7} {r.sense_mentions:>8}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Success Criteria

**Minimum**: New sense doesn't degrade performance vs baseline
- Iteration count: new_sense <= baseline
- Convergence: new_sense == True

**Good**: New sense improves on baseline
- Iteration reduction: 1-2 fewer iterations
- Sense mentions: > 0 (LLM references it)
- Answer quality maintained or improved

**Excellent**: Clear wins
- Iteration reduction: 2+ fewer iterations
- Sense mentions: 3+ references per test
- Improved evidence grounding

---

### Phase 4: Implementation Checklist

- [ ] Add imports detection to `detect_metadata_profile()`
- [ ] Add version detection to `detect_metadata_profile()`
- [ ] Add deprecation count to `detect_metadata_profile()`
- [ ] Add status detection to `detect_metadata_profile()`
- [ ] Add PAV/PROV detection to `detect_metadata_profile()`
- [ ] Add VANN detection to `detect_metadata_profile()` (optional)
- [ ] Update `MetadataProfile` dataclass with new fields
- [ ] Add `maturity_level()` method to `MetadataProfile`
- [ ] Update `format_sense_card()` with new sections
- [ ] Add 700-char length limit enforcement
- [ ] Create `test_sense_effectiveness.py` script
- [ ] Run all tests and collect data
- [ ] Analyze results and create decision matrix
- [ ] Update smoke tests if new sense cards prove beneficial
- [ ] Document findings in design doc

---

### Phase 5: Decision Framework

After running tests, make deployment decision:

**Deploy new sense cards IF:**
- New sense reduces iterations on 2+ out of 3 tests
- New sense doesn't degrade any test by >1 iteration
- Sense mentions > 0 on at least 1 test (proves engagement)

**Don't deploy IF:**
- New sense degrades performance on any test
- Sense mentions == 0 on all tests (still being ignored)
- No iteration improvement over baseline

**Iterate IF:**
- Mixed results (some better, some worse)
- Consider: reduce sense card length, prioritize different metadata
- Re-test with adjusted format

---

## Files to Modify

1. `rlm_runtime/ontology/sense_card.py`
   - Add import detection helpers
   - Add version detection helpers
   - Add deprecation/status detection
   - Update `detect_metadata_profile()`
   - Update `MetadataProfile` dataclass
   - Update `format_sense_card()`

2. `examples/test_sense_effectiveness.py` (NEW)
   - Create comparative test script

3. `examples/smoke_test_dspy_rlm.py` (UPDATE IF BENEFICIAL)
   - Already uses new module, no changes needed unless we adjust API

4. `examples/smoke_test_dul_systems.py` (UPDATE IF BENEFICIAL)
   - Already uses new module, no changes needed unless we adjust API

---

## Risk Mitigation

**Risk**: Sense cards become too verbose (>700 chars)

**Mitigation**:
- Enforce hard 700-char limit in formatter
- Prioritize: imports > version > deprecation > status > PAV/PROV
- Drop lower-priority items if length exceeded

**Risk**: Detection has false positives (detects vocabularies not meaningfully used)

**Mitigation**:
- For vocabularies: check actual usage count, not just namespace presence
- Require minimum threshold (e.g., 3+ uses)

**Risk**: New sense cards still ignored by LLM

**Mitigation**:
- Measure sense_mentions metric - if 0 across all tests, abandon approach
- Consider alternative: inject metadata as separate "Ontology Profile" section in context

**Risk**: Worse performance despite richer metadata

**Mitigation**:
- Don't deploy if tests show degradation
- Document findings for future reference
- Consider that simpler might be better

---

## Timeline Estimate

- **Detection enhancement**: 45 minutes
- **Format updates**: 20 minutes
- **Test script creation**: 30 minutes
- **Test execution**: 30 minutes (3 tests × 3 conditions × ~3 min each)
- **Analysis & decision**: 20 minutes
- **Deployment (if beneficial)**: 15 minutes

**Total**: ~2.5 hours

---

## Expected Outcome

**Best case**: New sense cards reduce iterations by 1-2 on complex queries, LLM references formalism/imports/disjointness in reasoning, deploy with confidence.

**Likely case**: Mixed results - helpful on some queries, neutral on others. Deploy if net positive.

**Worst case**: No improvement or degradation. Document as "sense cards don't help with current prompting strategy", archive work, move on.

---

## References

- Widoco metadata guide: https://github.com/dgarijo/Widoco/blob/master/doc/metadataGuide/guide.md
- Current implementation: `rlm_runtime/ontology/sense_card.py`
- Test results from current implementation:
  - PROV baseline: 5 iterations, converged=True
  - SystemsLite baseline: 5 iterations, converged=True
  - SystemsLite old_sense: 7 iterations, converged=True (WORSE!)
  - Sense mentions: 0 across all tests with old implementation
