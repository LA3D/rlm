# PROV Ontology Agent Guide

## Overview
The W3C PROV ontology is a standardized framework for representing provenance information - the origins, derivations, and history of data and processes. Its main purpose is to enable interoperable documentation of how entities (data, documents, artifacts) were generated, modified, or influenced by activities and agents (people, organizations, software) over time. This ontology provides a common vocabulary for tracking and sharing the "who, what, when, where, and how" of data lineage and computational workflows across different systems and domains.

## Core Classes
The PROV ontology is built around three fundamental classes that form the backbone of provenance modeling:

**prov:Entity** - Things in the world (physical, digital, conceptual) that have fixed aspects during a time interval. Use for data files, documents, people, organizations, or any object whose provenance you want to track.

**prov:Activity** - Processes, actions, or events that occur over time and act upon or with entities. Use for computations, workflows, meetings, or any process that transforms, uses, or generates entities.

**prov:Agent** - Entities that bear responsibility for activities. Use for people, organizations, software systems, or any entity that can be assigned responsibility for an activity.

## Key Properties
Looking at the provided PROV properties, I can identify several important ones for provenance modeling, though some key core properties appear to be missing from your list. Let me explain the most important ones present and fill in the gaps:

## Core PROV Properties Present in Your List

### 1. **generated** 
- **Domain**: Activity → **Range**: Entity
- **Usage**: Indicates that an Activity produced/created an Entity
- **Connection**: Links Activities to the Entities they create
- **Example**: A data processing activity generated a cleaned dataset

### 2. **agent**
- **Domain**: AgentInfluence → **Range**: Agent  
- **Usage**: References the Agent involved in an influence relationship
- **Connection**: Part of the mechanism to link Agents to Activities or Entities through influence classes

### 3. **activity**
- **Domain**: ActivityInfluence → **Range**: Activity
- **Usage**: References the Activity involved in an influence relationship
- **Connection**: Part of qualified influence patterns

### 4. **entity**
- **Domain**: EntityInfluence → **Range**: Entity
- **Usage**: References the Entity involved in an influence relationship
- **Connection**: Part of qualified influence patterns

## Missing Core Properties (Essential for Complete Provenance)

Your list is missing some fundamental PROV properties:

### **wasGeneratedBy** (inverse of generated)
- **Domain**: Entity → **Range**: Activity
- **Usage**: Shows which Activity created an Entity
- **When to use**: When you want to trace back from an Entity to its creating Activity

### **used**
- **Domain**: Activity → **Range**: Entity  
- **Usage**: Indicates an Activity consumed/used an Entity as input
- **When to use**: To show input-output relationships

### **wasAssociatedWith**
- **Domain**: Activity → **Range**: Agent
- **Usage**: Shows which Agent was responsible for an Activity
- **When to use**: To attribute Activities to responsible parties

## Secondary Properties in Your List

### **actedOnBehalfOf**
- **Domain**: Agent → **Range**: Agent
- **Usage**: Shows delegation relationships between Agents
- **When to use**: When one Agent acts as a representative of another

### **alternateOf** 
- **Domain**: Entity → **Range**: Entity
- **Usage**: Shows two Entities are alternate versions of the same thing
- **When to use**: For different representations of the same conceptual entity

## How They Connect the Core Classes

```
Agent --wasAssociatedWith--> Activity --generated--> Entity
  ↑                            ↑                        ↓
  |                            |                   wasGeneratedBy
  |                         used                       ↓
actedOnBehalfOf              ↓                      Entity
  |                       Entity                       ↓
Agent                                              alternateOf
                                                      ↓
                                                   Entity
```

## Recommendation

To build complete provenance models, you'll need the missing core properties (wasGeneratedBy, used, wasAssociatedWith) in addition to those in your list. These form the backbone of PROV's ability to trace the flow from data sources through processing steps to final outputs, with clear attribution to responsible agents.

## Query Patterns
Here are 4 practical SPARQL query patterns for the W3C PROV ontology:

## 1. Finding what generated an entity

```sparql
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?activity ?agent ?time
WHERE {
    <http://example.org/entity1> prov:wasGeneratedBy ?activity .
    OPTIONAL { ?activity prov:wasAssociatedWith ?agent }
    OPTIONAL { ?activity prov:endedAtTime ?time }
}
```

## 2. Finding what activities an agent was associated with

```sparql
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?activity ?role ?label
WHERE {
    ?activity prov:wasAssociatedWith <http://example.org/agent1> .
    OPTIONAL { 
        ?activity prov:qualifiedAssociation ?assoc .
        ?assoc prov:agent <http://example.org/agent1> ;
               prov:hadRole ?role 
    }
    OPTIONAL { ?activity rdfs:label ?label }
}
ORDER BY ?activity
```

## 3. Tracing derivation chains

```sparql
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?entity ?derivedEntity ?depth
WHERE {
    <http://example.org/startEntity> prov:wasDerivedFrom* ?entity .
    ?derivedEntity prov:wasDerivedFrom+ <http://example.org/startEntity> .
    
    # Calculate derivation depth using property path with counting
    {
        SELECT ?entity (COUNT(?intermediate) as ?depth) WHERE {
            <http://example.org/startEntity> prov:wasDerivedFrom* ?intermediate .
            ?intermediate prov:wasDerivedFrom* ?entity .
        }
        GROUP BY ?entity
    }
}
ORDER BY ?depth ?entity
```

## 4. Finding all entities used by an activity

```sparql
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?entity ?role ?usage_time ?entity_label
WHERE {
    <http://example.org/activity1> prov:used ?entity .
    
    OPTIONAL {
        <http://example.org/activity1> prov:qualifiedUsage ?usage .
        ?usage prov:entity ?entity ;
               prov:hadRole ?role .
        OPTIONAL { ?usage prov:atTime ?usage_time }
    }
    
    OPTIONAL { ?entity rdfs:label ?entity_label }
}
ORDER BY ?usage_time ?entity
```

These queries demonstrate common provenance patterns:
- **Query 1** traces backward from an entity to find its generating activity and associated agents
- **Query 2** finds all activities an agent participated in, including their roles
- **Query 3** follows derivation chains using property paths to trace data lineage
- **Query 4** finds all input entities for a given activity, with optional usage details

Each query includes relevant OPTIONAL clauses to capture additional metadata when available, making them robust for real-world provenance graphs with varying levels of detail.

## Important Considerations
# W3C PROV Ontology: Practical Guide

## 1. Common Modeling Mistakes

### Over-granular Provenance
```turtle
# ❌ Too granular - tracking every variable assignment
:step1 a prov:Activity ;
    prov:used :variable_x .
:step2 a prov:Activity ;
    prov:used :variable_y .

# ✅ Right level - meaningful computational steps
:dataProcessing a prov:Activity ;
    prov:used :rawDataset ;
    prov:generated :cleanedDataset .
```

### Confusing Entity States
```turtle
# ❌ Wrong - same URI for different states
:dataset prov:wasDerivedFrom :dataset .

# ✅ Correct - distinct URIs for different versions
:dataset_v2 prov:wasDerivedFrom :dataset_v1 .
```

### Misusing Agent Types
```turtle
# ❌ Wrong - software as Person
:algorithm a prov:Person .

# ✅ Correct - use appropriate agent types
:algorithm a prov:SoftwareAgent .
:researcher a prov:Person .
:organization a prov:Organization .
```

## 2. Qualified vs Unqualified Relations

### Use Unqualified When:
- Simple, direct relationships
- No additional metadata needed
- Performance is critical

```turtle
:output prov:wasDerivedFrom :input .
:activity prov:wasAssociatedWith :agent .
```

### Use Qualified When:
- Need to add attributes (time, role, plan)
- Multiple relationships of same type
- Complex attribution scenarios

```turtle
# Qualified for additional context
:output prov:qualifiedDerivation [
    a prov:Derivation ;
    prov:entity :input ;
    prov:hadActivity :transformation ;
    prov:atTime "2024-01-15T10:30:00Z"^^xsd:dateTime ;
    :confidence 0.95
] .

# Multiple roles require qualification
:analysis prov:qualifiedAssociation [
    a prov:Association ;
    prov:agent :researcher ;
    prov:hadRole :dataAnalyst
] , [
    a prov:Association ;
    prov:agent :supervisor ;
    prov:hadRole :reviewer
] .
```

## 3. Time and Attribution Handling

### Time Best Practices
```turtle
# ✅ Use specific time properties
:activity prov:startedAtTime "2024-01-15T09:00:00Z"^^xsd:dateTime ;
         prov:endedAtTime "2024-01-15T10:30:00Z"^^xsd:dateTime .

# ✅ Entity generation time
:dataset prov:generatedAtTime "2024-01-15T10:30:00Z"^^xsd:dateTime .

# ✅ For instantaneous events
:event prov:atTime "2024-01-15T10:30:00Z"^^xsd:dateTime .
```

### Attribution Patterns
```turtle
# Direct attribution
:dataset prov:wasAttributedTo :researcher .

# Detailed attribution with roles
:dataset prov:qualifiedAttribution [
    a prov:Attribution ;
    prov:agent :researcher ;
    prov:hadRole :dataCollector ;
    prov:atTime "2024-01-15T10:30:00Z"^^xsd:dateTime
] .

# Delegation chains
:juniorResearcher prov:actedOnBehalfOf :seniorResearcher .
```

## 4. Integration with Other Ontologies

### FOAF Integration
```turtle
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

:researcher a prov:Person, foaf:Person ;
    foaf:name "Dr. Jane Smith" ;
    foaf:mbox <mailto:jane@example.org> .
```

### Dublin Core Integration
```turtle
@prefix dc: <http://purl.org/dc/terms/> .

:dataset a prov:Entity ;
    dc:title "Climate Data 2024" ;
    dc:creator :researcher ;
    prov:wasAttributedTo :researcher .
```

### Domain-Specific Extensions
```turtle
# Extend PROV for your domain
:ScientificExperiment rdfs:subClassOf prov:Activity .
:Dataset rdfs:subClassOf prov:Entity .
:Researcher rdfs:subClassOf prov:Person .

:experiment a :ScientificExperiment ;
    prov:used :equipment ;
    :hasHypothesis :hypothesis .
```

## 5. Performance Considerations

### Minimize Qualified Relations
```turtle
# ❌ Unnecessary qualification
:output prov:qualifiedDerivation [
    a prov:Derivation ;
    prov:entity :input
] .

# ✅ Use unqualified when sufficient
:output prov:wasDerivedFrom :input .
```

### Batch Time Assertions
```turtle
# ✅ Group related temporal information
:activity prov:startedAtTime "2024-01-15T09:00:00Z"^^xsd:dateTime ;
         prov:endedAtTime "2024-01-15T10:30:00Z"^^xsd:dateTime ;
         prov:used :input1, :input2, :input3 ;
         prov:generated :output1, :output2 .
```

### Indexing Strategy
- Index frequently queried properties: `prov:wasGeneratedBy`, `prov:used`
- Consider temporal indexes for time-based queries
- Use SPARQL property paths efficiently

### Query Optimization
```sparql
# ✅ Efficient - specific property paths
SELECT ?derived WHERE {
    ?derived prov:wasDerivedFrom+ :original .
}

# ❌ Avoid - overly complex property paths
SELECT ?entity WHERE {
    ?entity (prov:wasDerivedFrom|prov:wasGeneratedBy|prov:used)* ?root .
}
```

## Key Gotchas

1. **Don't reuse Entity URIs** for different states/versions
2. **Time zones matter** - always use UTC with explicit timezone
3. **Qualified relations create blank nodes** - impacts query performance
4. **PROV-O is descriptive** - doesn't enforce temporal consistency
5. **Bundle carefully** - large bundles can impact performance
6. **Agent types matter** - choose Person/SoftwareAgent/Organization correctly

## Quick Decision Tree

**Need additional metadata?** → Use qualified relations  
**Simple relationship?** → Use unqualified relations  
**Tracking versions?** → Use distinct URIs + derivation  
**Multiple agents/roles?** → Use qualified associations  
**Time-sensitive?** → Always include temporal properties  
**Performance critical?** → Minimize qualifications, optimize queries

## Quick Reference
# PROV Ontology Quick Reference

## Common Prefixes
```turtle
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
```

## Core Classes

| Class | URI | Description |
|-------|-----|-------------|
| **Entity** | `prov:Entity` | Physical/digital/conceptual things |
| **Activity** | `prov:Activity` | Actions that occur over time |
| **Agent** | `prov:Agent` | Responsible for activities |

### Agent Subclasses
- `prov:Person` - Human agents
- `prov:Organization` - Organizational agents  
- `prov:SoftwareAgent` - Software/systems

## Essential Properties

### Core Relations
| Property | Domain → Range | Description |
|----------|----------------|-------------|
| `prov:wasGeneratedBy` | Entity → Activity | Entity created by activity |
| `prov:used` | Activity → Entity | Activity consumed entity |
| `prov:wasAssociatedWith` | Activity → Agent | Agent responsible for activity |
| `prov:wasAttributedTo` | Entity → Agent | Entity credited to agent |
| `prov:wasDerivedFrom` | Entity → Entity | Entity derived from another |

### Temporal Properties
- `prov:startedAtTime` - Activity start (xsd:dateTime)
- `prov:endedAtTime` - Activity end (xsd:dateTime)
- `prov:generatedAtTime` - Entity generation time

### Influence Relations
- `prov:wasInformedBy` - Activity → Activity (communication)
- `prov:actedOnBehalfOf` - Agent → Agent (delegation)
- `prov:wasInfluencedBy` - Any → Any (general influence)

## Key Patterns

### 1. Basic Generation
```turtle
:dataset prov:wasGeneratedBy :analysis ;
         prov:generatedAtTime "2024-01-15T10:30:00Z"^^xsd:dateTime .
```

### 2. Activity with Agent
```turtle
:analysis prov:wasAssociatedWith :researcher ;
          prov:used :rawData ;
          prov:startedAtTime "2024-01-15T09:00:00Z"^^xsd:dateTime .
```

### 3. Derivation Chain
```turtle
:report prov:wasDerivedFrom :dataset ;
        prov:wasAttributedTo :analyst .
```

### 4. Agent Hierarchy
```turtle
:researcher a prov:Person ;
           prov:actedOnBehalfOf :university .
:university a prov:Organization .
```

## Quick Validation Checklist
- ✓ Activities have temporal bounds
- ✓ Entities link to generating activities
- ✓ Agents are associated with activities
- ✓ Use specific agent types when possible
- ✓ Include timestamps for traceability

## Common URI Pattern
`http://example.org/prov/{type}/{id}`
