# Ontology Sense Improvements

This document describes improvements to the `build_sense()` function and how sense data integrates with the RLM system and ReasoningBank.

---

## Executive Summary

The current `build_sense()` produces free-form prose that is difficult for downstream systems to operationalize. This update introduces:

1. **Structured JSON schema** for sense output (typed, bounded fields)
2. **Grounding constraints** to prevent hallucination
3. **Two-tier output**: Sense Card (compact) + Sense Brief (detailed)
4. **Metadata awareness** to enable tool selection optimization
5. **Downstream evaluation** based on task performance, not prose quality

Expected impact:
- Enables ReasoningBank recipes to reference specific fields
- Reduces "pretty but un-actionable" summaries
- Prevents sense-layer hallucination
- Supports adaptive tool selection based on ontology characteristics

---

## 1. Current State Analysis

### Current Implementation

From `rlm/ontology.py`, `build_sense()`:

```python
# Current output structure (AttrDict)
sense_doc = AttrDict(
    ont=ont_name,
    ont_metadata=ont_metadata,
    stats={'cls': len(classes), 'props': len(properties), 'lbls': len(labels)},
    prefixes=metadata.prefixes,
    label_properties=label_props,
    description_properties=desc_props,
    ann_preds=metadata.ann_preds,
    roots=roots,
    hier=hier,
    top_props=top_props,
    prop_chars=prop_chars,
    owl_constructs=owl_constructs,
    uri_pattern=uri_pattern,
    summary=ns['_sense_summary']  # <-- Free-form LLM-generated prose
)
```

### Problems with Current Approach

1. **`summary` is unstructured prose**: Cannot be programmatically accessed
2. **No grounding enforcement**: LLM may invent classes/properties
3. **Single summary size**: Too verbose for simple queries, may be insufficient for complex ones
4. **No tool guidance**: Doesn't indicate which metadata indexes are available
5. **Evaluation is subjective**: "Good" summaries may not improve task performance

---

## 2. Proposed Schema

### 2.1 Sense Card (Compact, Always Injected)

```json
{
  "sense_card": {
    "ontology_id": "string",
    "domain_scope": "string (2-3 sentences max)",
    "triple_count": "integer",
    "class_count": "integer",
    "property_count": "integer",

    "key_classes": [
      {
        "uri": "string",
        "label": "string",
        "why_important": "string (1 sentence)"
      }
    ],  // max 5 items

    "key_properties": [
      {
        "uri": "string",
        "label": "string",
        "domain": "string or null",
        "range": "string or null",
        "role": "string (1 sentence)"
      }
    ],  // max 5 items

    "label_predicates": ["string"],  // e.g., ["rdfs:label", "skos:prefLabel"]
    "description_predicates": ["string"],  // e.g., ["rdfs:comment", "skos:definition"]

    "available_indexes": {
      "by_label": "integer (entry count)",
      "hierarchy": "integer (entry count)",
      "domains": "integer (entry count)",
      "ranges": "integer (entry count)",
      "pred_freq": "integer (entry count)"
    },

    "quick_hints": ["string"],  // max 3 items, actionable guidance

    "uri_pattern": "string"  // e.g., "http://semanticscience.org/resource/SIO_"
  }
}
```

**Size target**: ~400-600 characters when serialized

### 2.2 Sense Brief (Detailed, Retrieved When Needed)

```json
{
  "sense_brief": {
    "ontology_id": "string",

    "patterns": {
      "description": "string (2-3 sentences)",
      "detected_patterns": [
        {
          "name": "string",
          "entities_involved": ["string"],
          "key_properties": ["string"],
          "description": "string (1-2 sentences)"
        }
      ]  // max 3 patterns
    },

    "hierarchy_overview": {
      "root_classes": [
        {
          "uri": "string",
          "label": "string",
          "direct_subclasses": ["string"]  // max 5, labels only
        }
      ],  // max 5 roots
      "max_depth": "integer",
      "branching_factor": "string (e.g., 'high', 'medium', 'low')"
    },

    "property_details": {
      "object_properties": [
        {
          "uri": "string",
          "label": "string",
          "domain": "string",
          "range": "string",
          "characteristics": ["string"],  // e.g., ["transitive", "symmetric"]
          "usage_count": "integer"
        }
      ],  // max 10
      "datatype_properties": [...],  // max 5
      "annotation_properties": [...]  // max 5
    },

    "owl_complexity": {
      "restrictions_count": "integer",
      "unions_count": "integer",
      "intersections_count": "integer",
      "disjointness_count": "integer",
      "complexity_level": "string (low/medium/high)",
      "implications": "string (1-2 sentences)"
    },

    "gotchas": [
      {
        "issue": "string",
        "recommendation": "string"
      }
    ],  // max 5

    "starter_queries": [
      {
        "intent": "string",
        "sparql": "string",
        "parameters": ["string"]
      }
    ],  // max 4

    "metadata_first_guidance": {
      "prefer_indexes_when": ["string"],  // max 3
      "avoid_graph_traversal_when": ["string"],  // max 2
      "tool_selection_hints": ["string"]  // max 3
    }
  }
}
```

**Size target**: ~1500-2500 characters when serialized

---

## 3. Grounding Constraints

### 3.1 Evidence Sources

The LLM prompt for generating sense data MUST be constrained to use ONLY:

| Evidence Source | What It Provides | Grounding Guarantee |
|-----------------|------------------|---------------------|
| `roots` | Root classes list | All URIs exist in ontology |
| `hier` | 2-level hierarchy | All URIs exist in ontology |
| `top_props` | Top properties with domain/range | All URIs exist in ontology |
| `label_properties` | Detected label predicates | Verified via graph query |
| `description_properties` | Detected description predicates | Verified via graph query |
| `owl_constructs` | OWL usage statistics | Computed from graph |
| `uri_pattern` | URI samples | Extracted from actual URIs |
| `ont_metadata` | Ontology-level metadata | Extracted from owl:Ontology |

### 3.2 Prompt Constraints

```python
SENSE_GENERATION_PROMPT = """
Generate a structured sense document for this ontology.

STRICT RULES:
1. ONLY use URIs that appear in the provided evidence lists
2. ONLY use labels that appear in the provided label mappings
3. DO NOT invent or infer classes/properties not in the evidence
4. DO NOT use external knowledge about this ontology
5. If uncertain about something, omit it rather than guess

EVIDENCE PROVIDED:
- Root classes: {roots}
- Hierarchy (2 levels): {hier}
- Top properties: {top_props}
- Label predicates detected: {label_properties}
- Description predicates detected: {description_properties}
- OWL constructs: {owl_constructs}
- URI pattern: {uri_pattern}
- Ontology metadata: {ont_metadata}

Generate output matching this exact JSON schema:
{schema}
"""
```

### 3.3 Post-Generation Validation

```python
def validate_sense_grounding(sense: dict, meta: GraphMeta) -> dict:
    """Validate all URIs in sense exist in the ontology."""

    errors = []

    # Check key_classes URIs
    for cls in sense['sense_card'].get('key_classes', []):
        if cls['uri'] not in meta.classes:
            errors.append(f"key_class URI not found: {cls['uri']}")

    # Check key_properties URIs
    for prop in sense['sense_card'].get('key_properties', []):
        if prop['uri'] not in meta.properties:
            errors.append(f"key_property URI not found: {prop['uri']}")

    # Check pattern entities
    for pattern in sense.get('sense_brief', {}).get('patterns', {}).get('detected_patterns', []):
        for entity in pattern.get('entities_involved', []):
            if entity not in meta.labels.values() and entity not in meta.classes:
                errors.append(f"pattern entity not found: {entity}")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'error_count': len(errors)
    }
```

---

## 4. Two-Tier Injection Strategy

### 4.1 When to Use Each Tier

| Context | Inject | Rationale |
|---------|--------|-----------|
| Any ontology query | Sense Card | Minimal context, always useful |
| Pattern synthesis query | + Brief: patterns | Need pattern details |
| Hierarchy query | + Brief: hierarchy_overview | Need structure info |
| Query construction | + Brief: starter_queries | Need templates |
| Debugging/errors | + Brief: gotchas | Need trap warnings |
| Complex exploration | Full Brief | Need comprehensive guidance |

### 4.2 Implementation

```python
def get_sense_context(query: str, sense: dict, detail_level: str = 'auto') -> str:
    """Get appropriate sense context for a query."""

    # Always include card
    context = format_sense_card(sense['sense_card'])

    if detail_level == 'card_only':
        return context

    if detail_level == 'full' or detail_level == 'auto':
        brief = sense.get('sense_brief', {})

        # Auto-detect what sections are needed
        if detail_level == 'auto':
            query_lower = query.lower()

            if any(word in query_lower for word in ['pattern', 'relate', 'connect']):
                context += format_brief_section(brief, 'patterns')

            if any(word in query_lower for word in ['subclass', 'superclass', 'hierarchy', 'type']):
                context += format_brief_section(brief, 'hierarchy_overview')

            if any(word in query_lower for word in ['sparql', 'query', 'select', 'construct']):
                context += format_brief_section(brief, 'starter_queries')

            if any(word in query_lower for word in ['error', 'problem', 'issue', 'wrong']):
                context += format_brief_section(brief, 'gotchas')

        elif detail_level == 'full':
            context += format_sense_brief(brief)

    return context
```

### 4.3 Formatting for Injection

```python
def format_sense_card(card: dict) -> str:
    """Format sense card for context injection."""

    return f"""
## Ontology Sense: {card['ontology_id']}

**Domain**: {card['domain_scope']}

**Statistics**: {card['triple_count']:,} triples, {card['class_count']} classes, {card['property_count']} properties

**Key Classes**:
{chr(10).join(f"- {c['label']} ({c['uri']}): {c['why_important']}" for c in card['key_classes'][:3])}

**Key Properties**:
{chr(10).join(f"- {p['label']}: {p['domain']} → {p['range']}" for p in card['key_properties'][:3])}

**Labels via**: {', '.join(card['label_predicates'])}

**Available Indexes**: by_label({card['available_indexes']['by_label']}), hierarchy({card['available_indexes']['hierarchy']}), domains({card['available_indexes']['domains']})

**Quick Hints**:
{chr(10).join(f"- {h}" for h in card['quick_hints'])}

**URI Pattern**: {card['uri_pattern']}
"""
```

---

## 5. Metadata-First Guidance

### 5.1 Tool Selection Based on Sense

The sense card includes `available_indexes` and `quick_hints` specifically to enable smart tool selection:

```python
def get_tool_recommendation(sense_card: dict, task_type: str) -> dict:
    """Recommend tools based on sense data and task type."""

    indexes = sense_card['available_indexes']
    label_preds = sense_card['label_predicates']

    recommendations = {
        'prefer': [],
        'avoid': [],
        'rationale': []
    }

    # Label-based search recommendations
    if 'rdfs:label' not in label_preds:
        recommendations['avoid'].append('search_by_label with default assumptions')
        recommendations['prefer'].append('search_entity with mode=iri or mode=localname')
        recommendations['rationale'].append(
            f"Ontology uses {label_preds} for labels, not rdfs:label"
        )

    # Hierarchy tool recommendations
    if indexes['hierarchy'] > 100:
        recommendations['prefer'].append('get_subclasses/get_superclasses tools')
        recommendations['avoid'].append('chained describe_entity for hierarchy')
        recommendations['rationale'].append(
            f"Hierarchy is pre-indexed ({indexes['hierarchy']} entries)"
        )

    # Domain/range recommendations
    if indexes['domains'] > 10:
        recommendations['prefer'].append('find_properties_by_domain')
        recommendations['avoid'].append('probe_relationships for property discovery')
        recommendations['rationale'].append(
            f"Domain index has {indexes['domains']} entries for direct lookup"
        )

    return recommendations
```

### 5.2 Sense-Adaptive Recipe Execution

```python
def adapt_recipe_to_sense(recipe: str, sense_card: dict) -> str:
    """Adapt a generic recipe based on sense data."""

    adaptations = []

    # Check label predicates
    if 'skos:prefLabel' in sense_card['label_predicates']:
        adaptations.append(
            "Note: This ontology uses skos:prefLabel. "
            "Check prefLabel in describe_entity output, not rdfs:label."
        )

    # Check available indexes
    if sense_card['available_indexes']['by_label'] > 0:
        adaptations.append(
            f"Optimization: by_label index has {sense_card['available_indexes']['by_label']} entries. "
            "Use exact label lookup before substring search."
        )

    # Check complexity hints
    for hint in sense_card['quick_hints']:
        if 'restriction' in hint.lower() or 'owl' in hint.lower():
            adaptations.append(
                "Caution: Heavy OWL usage detected. "
                "Use probe_relationships to understand structure."
            )

    if adaptations:
        return recipe + "\n\n**Sense-Based Adaptations**:\n" + "\n".join(f"- {a}" for a in adaptations)

    return recipe
```

---

## 6. Evaluation Framework

### 6.1 Sense Quality Metrics

Sense quality is measured by **downstream task performance**, not prose aesthetics:

| Metric | Definition | Target |
|--------|------------|--------|
| **Grounding accuracy** | % of URIs in sense that exist in ontology | 100% |
| **Iteration reduction** | Iterations with sense vs without | ≥15% reduction |
| **Tool selection accuracy** | % of tool recommendations that improve efficiency | ≥70% |
| **Convergence rate** | % of queries that converge with sense context | ≥95% |
| **Groundedness preservation** | Groundedness score with sense vs without | No degradation |

### 6.2 Evaluation Tasks

```python
SENSE_EVALUATION_TASKS = {
    'baseline': [
        # These should work with just GraphMeta.summary()
        "How many classes are in {ontology}?",
        "What namespaces are used?",
    ],

    'sense_card_benefit': [
        # These should improve with sense card
        "What is {key_class}?",  # key_class from sense
        "What properties connect {entity_a} to {entity_b}?",
    ],

    'sense_brief_benefit': [
        # These need sense brief sections
        "What is the {pattern_name} pattern?",
        "Write a SPARQL query to find {target}",
        "What are the subclasses of {root_class}?",
    ],

    'metadata_first_benefit': [
        # These should use indexes when sense indicates them
        "Find all properties with {class} as domain",
        "What is the hierarchy under {class}?",
    ],
}
```

### 6.3 Evaluation Protocol

```python
def evaluate_sense_quality(sense: dict, ontology: str, meta: GraphMeta) -> dict:
    """Comprehensive sense quality evaluation."""

    results = {
        'grounding': validate_sense_grounding(sense, meta),
        'iteration_comparison': {},
        'tool_selection': {},
        'convergence': {},
    }

    # Compare iterations: no sense vs sense card vs sense + recipes
    for task_category, tasks in SENSE_EVALUATION_TASKS.items():
        for task_template in tasks:
            task = task_template.format(**get_task_params(sense, ontology))

            # Baseline: no sense
            _, iters_none, _ = rlm_run(task, meta.summary(), max_iters=10)

            # With sense card
            _, iters_card, _ = rlm_run(task, format_sense_card(sense['sense_card']), max_iters=10)

            # With sense card + recipes
            context = format_sense_card(sense['sense_card']) + get_core_recipes()
            _, iters_full, _ = rlm_run(task, context, max_iters=10)

            results['iteration_comparison'][task] = {
                'no_sense': len(iters_none),
                'sense_card': len(iters_card),
                'sense_plus_recipes': len(iters_full),
                'improvement_card': (len(iters_none) - len(iters_card)) / len(iters_none),
                'improvement_full': (len(iters_none) - len(iters_full)) / len(iters_none),
            }

    # Aggregate metrics
    improvements = [v['improvement_full'] for v in results['iteration_comparison'].values()]
    results['summary'] = {
        'mean_improvement': sum(improvements) / len(improvements),
        'grounding_valid': results['grounding']['valid'],
        'tasks_evaluated': len(improvements),
    }

    return results
```

---

## 7. Implementation Plan

### Phase 1: Schema Definition (Week 1)

**Deliverables**:
- [ ] Define JSON schema for sense_card
- [ ] Define JSON schema for sense_brief
- [ ] Create schema validation functions
- [ ] Document schema in this file

**Success Criteria**:
- Schemas are complete and validated
- All fields have clear types and bounds

### Phase 2: Grounded Generation (Week 2)

**Deliverables**:
- [ ] Update `build_sense()` prompt with grounding constraints
- [ ] Implement post-generation validation
- [ ] Add fallback for validation failures
- [ ] Test on PROV, SIO, DCAT

**Success Criteria**:
- 100% grounding accuracy on test ontologies
- No hallucinated URIs in output

### Phase 3: Two-Tier Output (Week 3)

**Deliverables**:
- [ ] Implement sense card generation
- [ ] Implement sense brief generation
- [ ] Create formatting functions
- [ ] Implement auto-detection for section selection

**Success Criteria**:
- Card fits in ~500 chars
- Brief sections are independently usable
- Auto-detection works for common query types

### Phase 4: Integration with RLM (Week 4)

**Deliverables**:
- [ ] Update `setup_ontology_context()` to generate structured sense
- [ ] Create `get_sense_context()` function
- [ ] Integrate with context building in `rlm_run()`
- [ ] Add sense to namespace for tool access

**Success Criteria**:
- Sense card automatically injected
- Brief sections retrievable when needed
- No regression on existing tests

### Phase 5: Evaluation Framework (Week 5)

**Deliverables**:
- [ ] Implement evaluation tasks
- [ ] Create evaluation protocol
- [ ] Run baseline comparisons
- [ ] Document results

**Success Criteria**:
- ≥15% iteration reduction with sense card
- ≥25% iteration reduction with sense + recipes
- 100% grounding accuracy maintained

---

## 8. Integration with ReasoningBank

### 8.1 Sense as Layer 0

Sense data forms the foundation that ReasoningBank recipes operate on:

```
Layer 0: Sense Data (computed once per ontology)
    │
    ├── sense_card (always injected)
    │   ├── domain_scope
    │   ├── key_classes
    │   ├── key_properties
    │   ├── available_indexes
    │   └── quick_hints
    │
    └── sense_brief (retrieved when needed)
        ├── patterns
        ├── hierarchy_overview
        ├── property_details
        ├── gotchas
        └── starter_queries

    ↓

Layer 1: Core Recipes (including Recipe 0: How to Use Sense)
    ↓
Layer 2: Task-Type Recipes
    ↓
Layer 3: Ontology-Specific Knowledge
```

### 8.2 Recipe 0: How to Use Sense Data

This recipe should be added to ReasoningBank core recipes:

```markdown
## Recipe 0: How to Use Sense Data

**When to use**: Always, before any other recipe

**Procedure**:
1. Read `sense.domain_scope` to understand ontology coverage
2. Scan `sense.key_classes` for likely starting points
3. Note `sense.key_properties` for relationship vocabulary
4. Check `sense.label_predicates` to adjust search strategy:
   - If rdfs:label present: standard label search works
   - If only skos:prefLabel: may need different approach
5. Review `sense.available_indexes`:
   - by_label > 0: prefer exact label lookups
   - hierarchy > 100: use hierarchy tools, not describe chains
   - domains > 10: use domain lookup for property discovery
6. Glance at `sense.quick_hints` for ontology-specific guidance

**Then proceed with task-specific recipe**

**Key principle**: Sense data is navigation, not the answer. Use it to select tools, not to answer directly.

**Anti-patterns**:
- Ignoring sense and discovering everything from scratch
- Treating sense.domain_scope as the answer
- Not checking available_indexes before tool selection
```

### 8.3 Sense-Aware Validation

Memory validation should verify sense was used appropriately:

```python
def validate_sense_usage(iterations: list, sense_card: dict) -> dict:
    """Validate that trajectory used sense data appropriately."""

    # Check if available indexes were used
    index_tools_used = {
        'by_label': any('get_by_label' in str(it) for it in iterations),
        'hierarchy': any('get_subclasses' in str(it) or 'get_superclasses' in str(it) for it in iterations),
        'domains': any('find_properties_by_domain' in str(it) for it in iterations),
    }

    # Check if sense-recommended tools were preferred
    recommendations = get_tool_recommendation(sense_card, 'general')
    preferred_used = sum(1 for tool in recommendations['prefer'] if any(tool in str(it) for it in iterations))
    avoided_used = sum(1 for tool in recommendations['avoid'] if any(tool in str(it) for it in iterations))

    return {
        'index_usage': index_tools_used,
        'preferred_tools_used': preferred_used,
        'avoided_tools_used': avoided_used,
        'sense_compliance_score': (preferred_used - avoided_used) / max(1, len(recommendations['prefer']))
    }
```

---

## 9. Example Outputs

### 9.1 SIO Sense Card Example

```json
{
  "sense_card": {
    "ontology_id": "sio",
    "domain_scope": "SIO (Semantic Science Integrated Ontology) models scientific entities, processes, attributes, and their relationships. It provides a comprehensive vocabulary for describing scientific investigations, measurements, and data.",
    "triple_count": 15734,
    "class_count": 1726,
    "property_count": 238,

    "key_classes": [
      {"uri": "SIO_000006", "label": "process", "why_important": "Central to modeling activities and transformations"},
      {"uri": "SIO_000015", "label": "information content entity", "why_important": "Covers data, documents, and representations"},
      {"uri": "SIO_000004", "label": "material entity", "why_important": "Physical objects and substances"}
    ],

    "key_properties": [
      {"uri": "SIO_000132", "label": "has participant", "domain": "process", "range": "entity", "role": "Links processes to participating entities"},
      {"uri": "SIO_000230", "label": "has input", "domain": "process", "range": "entity", "role": "Specialization of has participant for inputs"},
      {"uri": "SIO_000229", "label": "has output", "domain": "process", "range": "entity", "role": "Specialization of has participant for outputs"}
    ],

    "label_predicates": ["rdfs:label"],
    "description_predicates": ["dcterms:description"],

    "available_indexes": {
      "by_label": 1797,
      "hierarchy": 523,
      "domains": 30,
      "ranges": 29,
      "pred_freq": 60
    },

    "quick_hints": [
      "Use dc:identifier (2899 uses) for entity IDs, not URIs directly",
      "has_input/has_output are subproperties of has_participant",
      "Heavy OWL restriction usage (524) - use probe_relationships for structure"
    ],

    "uri_pattern": "http://semanticscience.org/resource/SIO_"
  }
}
```

### 9.2 SIO Sense Brief (Patterns Section) Example

```json
{
  "patterns": {
    "description": "SIO uses a process-centric pattern where activities are modeled as processes with participants, inputs, and outputs. Attributes are modeled separately and linked via has_attribute.",
    "detected_patterns": [
      {
        "name": "Process-Participant Pattern",
        "entities_involved": ["process", "entity"],
        "key_properties": ["has participant", "is participant in", "has input", "has output"],
        "description": "Processes link to participants via has_participant, with specialized sub-properties for inputs and outputs."
      },
      {
        "name": "Attribute Pattern",
        "entities_involved": ["entity", "attribute"],
        "key_properties": ["has attribute", "is attribute of", "has value"],
        "description": "Entities have attributes that can carry values. Attributes are first-class entities."
      }
    ]
  }
}
```

---

## 10. Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Schema completeness | All fields defined | Manual review |
| Grounding accuracy | 100% | Validation function |
| Card size | ≤600 chars | Character count |
| Brief size | ≤2500 chars | Character count |
| Iteration reduction (card only) | ≥15% | Evaluation protocol |
| Iteration reduction (card + recipes) | ≥30% | Evaluation protocol |
| Tool selection compliance | ≥70% | Validation function |
| Groundedness preservation | No degradation | Groundedness grader |

---

## Appendix A: Full JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OntologySense",
  "type": "object",
  "required": ["sense_card"],
  "properties": {
    "sense_card": {
      "type": "object",
      "required": ["ontology_id", "domain_scope", "triple_count", "class_count", "property_count", "key_classes", "key_properties", "label_predicates", "available_indexes", "quick_hints", "uri_pattern"],
      "properties": {
        "ontology_id": {"type": "string"},
        "domain_scope": {"type": "string", "maxLength": 500},
        "triple_count": {"type": "integer"},
        "class_count": {"type": "integer"},
        "property_count": {"type": "integer"},
        "key_classes": {
          "type": "array",
          "maxItems": 5,
          "items": {
            "type": "object",
            "required": ["uri", "label", "why_important"],
            "properties": {
              "uri": {"type": "string"},
              "label": {"type": "string"},
              "why_important": {"type": "string", "maxLength": 100}
            }
          }
        },
        "key_properties": {
          "type": "array",
          "maxItems": 5,
          "items": {
            "type": "object",
            "required": ["uri", "label", "role"],
            "properties": {
              "uri": {"type": "string"},
              "label": {"type": "string"},
              "domain": {"type": ["string", "null"]},
              "range": {"type": ["string", "null"]},
              "role": {"type": "string", "maxLength": 100}
            }
          }
        },
        "label_predicates": {"type": "array", "items": {"type": "string"}},
        "description_predicates": {"type": "array", "items": {"type": "string"}},
        "available_indexes": {
          "type": "object",
          "required": ["by_label", "hierarchy", "domains", "ranges", "pred_freq"],
          "properties": {
            "by_label": {"type": "integer"},
            "hierarchy": {"type": "integer"},
            "domains": {"type": "integer"},
            "ranges": {"type": "integer"},
            "pred_freq": {"type": "integer"}
          }
        },
        "quick_hints": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 150}},
        "uri_pattern": {"type": "string"}
      }
    },
    "sense_brief": {
      "type": "object",
      "properties": {
        "patterns": {"type": "object"},
        "hierarchy_overview": {"type": "object"},
        "property_details": {"type": "object"},
        "owl_complexity": {"type": "object"},
        "gotchas": {"type": "array", "maxItems": 5},
        "starter_queries": {"type": "array", "maxItems": 4},
        "metadata_first_guidance": {"type": "object"}
      }
    }
  }
}
```

---

## Appendix B: Migration from Current build_sense()

```python
def migrate_sense_output(old_sense: AttrDict) -> dict:
    """Migrate from old AttrDict format to new structured format."""

    # Extract key classes from roots + hierarchy
    key_classes = []
    for root in old_sense.roots[:5]:
        label = get_label(root, old_sense)
        key_classes.append({
            'uri': root,
            'label': label,
            'why_important': f"Root class in {old_sense.ont} hierarchy"
        })

    # Extract key properties from top_props
    key_properties = []
    for prop_label, domain, range_ in old_sense.top_props[:5]:
        # Find URI from label (reverse lookup)
        uri = find_uri_by_label(prop_label, old_sense)
        key_properties.append({
            'uri': uri,
            'label': prop_label,
            'domain': domain or None,
            'range': range_ or None,
            'role': f"Connects {domain} to {range_}" if domain and range_ else "Common property"
        })

    # Build new structure
    return {
        'sense_card': {
            'ontology_id': old_sense.ont,
            'domain_scope': extract_domain_scope(old_sense.summary),  # Parse from prose
            'triple_count': old_sense.stats.get('triples', 0),
            'class_count': old_sense.stats.get('cls', 0),
            'property_count': old_sense.stats.get('props', 0),
            'key_classes': key_classes,
            'key_properties': key_properties,
            'label_predicates': old_sense.label_properties,
            'description_predicates': old_sense.description_properties,
            'available_indexes': {
                'by_label': old_sense.stats.get('lbls', 0),
                'hierarchy': len(old_sense.hier),
                'domains': len([p for p in old_sense.top_props if p[1]]),
                'ranges': len([p for p in old_sense.top_props if p[2]]),
                'pred_freq': len(old_sense.ann_preds),
            },
            'quick_hints': extract_hints(old_sense),
            'uri_pattern': old_sense.uri_pattern,
        },
        'sense_brief': {
            # Generate from old data + new LLM call with grounding constraints
        }
    }
```
