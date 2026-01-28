"""Curriculum-aware memory retrieval for progressive disclosure.

This module implements heuristics-based complexity estimation and level-appropriate
exemplar retrieval, following the PDDL-INSTRUCT curriculum paradigm.

Complexity Levels:
- L1: Single entity retrieval by ID (URI construction, direct lookup)
- L2: Cross-reference between entities (joins, annotations)
- L3: Filtering and constraints (FILTER, OPTIONAL, property constraints)
- L4: Multi-hop paths (property paths, transitive relationships)
- L5: Aggregation and analytics (COUNT, GROUP BY, HAVING, complex FILTER)
"""

from __future__ import annotations

import re
from typing import Optional

from rlm_runtime.memory.backend import MemoryBackend, MemoryItem


def estimate_query_complexity(query: str) -> int:
    """Estimate complexity level of a query task using heuristics.

    Args:
        query: Natural language query or task description

    Returns:
        Complexity level 1-5

    Complexity indicators:
    - L1: "what is", "find the", "get", single entity, ID/accession mentioned
    - L2: "relationships", "connected", "annotations for", cross-references
    - L3: "filter", "where", "only", "with", constraints, conditions
    - L4: "path", "transitively", "all descendants", "hierarchy", multi-hop
    - L5: "count", "how many", "average", "group by", aggregation
    """
    query_lower = query.lower()

    # Count complexity indicators
    scores = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # L1 indicators (single entity lookup)
    l1_patterns = [
        r'\b(?:what is|get|find|retrieve)\s+(?:the\s+)?(?:protein|entity|class)',
        r'\b(?:accession|id|identifier|uri)\b',
        r'\b(?:P\d{5}|Q\d+)\b',  # Specific IDs (UniProt, Wikidata)
        r'\bwith\s+(?:accession|id)\b',
    ]
    for pattern in l1_patterns:
        if re.search(pattern, query_lower):
            scores[1] += 1

    # L2 indicators (cross-references, joins)
    l2_patterns = [
        r'\b(?:annotations?|cross-references?)\s+(?:for|of)\b',
        r'\b(?:related|connected|linked)\s+(?:to|with)\b',
        r'\b(?:go|ec|disease|pathway)\s+(?:terms?|annotations?)\b',
        r'\b(?:organism|taxon)\s+for\b',
    ]
    for pattern in l2_patterns:
        if re.search(pattern, query_lower):
            scores[2] += 2  # Weight L2 higher if present

    # L3 indicators (filtering, constraints)
    l3_patterns = [
        r'\b(?:filter|where|only|with|having)\b',
        r'\b(?:reviewed|curated|swiss-prot)\b',
        r'\b(?:contains?|matches?)\b',
        r'\b(?:between|range|from\s+\d+\s+to\s+\d+)\b',
        r'\b(?:in\s+humans?|in\s+\w+\s+organism)\b',
    ]
    for pattern in l3_patterns:
        if re.search(pattern, query_lower):
            scores[3] += 1.5

    # L4 indicators (multi-hop, paths, hierarchy)
    l4_patterns = [
        r'\b(?:path|paths?)\s+(?:from|to|between)\b',
        r'\b(?:transitively?|all\s+descendants?|all\s+ancestors?)\b',
        r'\b(?:hierarchy|subclass|superclass)\b',
        r'\b(?:indirect|derived\s+from)\b',
        r'\b(?:chain|sequence|lineage)\b',
    ]
    for pattern in l4_patterns:
        if re.search(pattern, query_lower):
            scores[4] += 2  # L4 is distinctive

    # L5 indicators (aggregation, analytics)
    l5_patterns = [
        r'\b(?:how\s+many|count|number\s+of)\b',
        r'\b(?:average|sum|max|min|total)\b',
        r'\b(?:group\s+by|grouped|distribution)\b',
        r'\b(?:statistics?|analytics?|summary)\b',
        r'\b(?:most|least|top|bottom)\s+\d*\s*(?:common|frequent|popular)\b',
    ]
    for pattern in l5_patterns:
        if re.search(pattern, query_lower):
            scores[5] += 2.5  # L5 is most distinctive

    # Determine level based on highest score
    # If tie, prefer higher level (more complex)
    max_score = max(scores.values())
    if max_score == 0:
        # No indicators found, assume L1 (simple lookup)
        return 1

    # Find highest level with max score
    for level in [5, 4, 3, 2, 1]:
        if scores[level] == max_score:
            return level

    return 1  # Fallback


def retrieve_with_curriculum(
    task: str,
    backend: MemoryBackend,
    k: int = 3,
    ontology_name: Optional[str] = None,
    level_tolerance: int = 1,
) -> list[MemoryItem]:
    """Retrieve memories with curriculum-aware prioritization.

    Prioritization order:
    1. Exemplars at exact curriculum level for this ontology
    2. Exemplars at adjacent levels (±level_tolerance) for this ontology
    3. Success memories for this ontology
    4. Exemplars for other ontologies (transferable)
    5. Success memories from other ontologies (transferable)

    Args:
        task: Natural language task query
        backend: Memory backend to retrieve from
        k: Total number of memories to retrieve
        ontology_name: Name of ontology (for filtering), optional
        level_tolerance: How many levels away to accept (default: 1)

    Returns:
        List of MemoryItems, prioritized by curriculum relevance
    """
    # Estimate task complexity
    estimated_level = estimate_query_complexity(task)

    # Retrieve candidates using BM25
    candidates = backend.retrieve(task, k=k * 5)  # Get more candidates for filtering

    # Separate exemplars and regular memories
    exemplars = [m for m in candidates if m.source_type == 'exemplar']
    success_memories = [m for m in candidates if m.source_type == 'success']

    # Filter and score exemplars
    scored_exemplars = []
    for exemplar in exemplars:
        score = 0

        # Get exemplar level
        exemplar_level = exemplar.scope.get('curriculum_level', 0)
        exemplar_ontology = exemplar.scope.get('ontology', [])

        if isinstance(exemplar_ontology, list):
            exemplar_ontology = exemplar_ontology[0] if exemplar_ontology else None

        # Level matching bonus
        level_diff = abs(exemplar_level - estimated_level)
        if level_diff == 0:
            score += 10  # Exact level match
        elif level_diff <= level_tolerance:
            score += 5 - level_diff  # Adjacent levels, decreasing bonus
        else:
            score += 0  # Too far, no bonus

        # Ontology matching bonus
        if ontology_name and exemplar_ontology == ontology_name:
            score += 5  # Same ontology
        elif ontology_name:
            score += 1  # Different ontology, but might be transferable

        scored_exemplars.append((score, exemplar))

    # Sort exemplars by score (descending)
    scored_exemplars.sort(key=lambda x: x[0], reverse=True)

    # Take top exemplars (at most k // 2, to leave room for success memories)
    max_exemplars = max(1, k // 2)
    selected_exemplars = [ex for score, ex in scored_exemplars[:max_exemplars]]

    # Fill remaining slots with success memories
    remaining_slots = k - len(selected_exemplars)
    selected_memories = success_memories[:remaining_slots]

    # Combine and return
    result = selected_exemplars + selected_memories

    return result[:k]  # Ensure we don't exceed k


def get_exemplars_for_level(
    backend: MemoryBackend,
    level: int,
    ontology_name: Optional[str] = None,
    limit: int = 10
) -> list[MemoryItem]:
    """Retrieve all exemplars for a specific curriculum level.

    Args:
        backend: Memory backend
        level: Curriculum level (1-5)
        ontology_name: Optional ontology filter
        limit: Maximum number to return

    Returns:
        List of exemplar MemoryItems
    """
    # Get all memories
    all_memories = backend.get_all_memories()

    # Filter for exemplars at this level
    exemplars = []
    for memory in all_memories:
        if memory.source_type != 'exemplar':
            continue

        if memory.scope.get('curriculum_level') != level:
            continue

        if ontology_name:
            mem_ontology = memory.scope.get('ontology', [])
            if isinstance(mem_ontology, list):
                if ontology_name not in mem_ontology:
                    continue
            elif mem_ontology != ontology_name:
                continue

        exemplars.append(memory)

    return exemplars[:limit]


def analyze_curriculum_coverage(backend: MemoryBackend, ontology_name: Optional[str] = None) -> dict:
    """Analyze curriculum coverage in memory backend.

    Args:
        backend: Memory backend
        ontology_name: Optional ontology filter

    Returns:
        dict with coverage statistics:
        - total_exemplars: int
        - by_level: dict[int, int] - count per level
        - by_ontology: dict[str, int] - count per ontology
        - missing_levels: list[int] - levels with no exemplars
    """
    all_memories = backend.get_all_memories()
    exemplars = [m for m in all_memories if m.source_type == 'exemplar']

    # Filter by ontology if specified
    if ontology_name:
        exemplars = [
            m for m in exemplars
            if ontology_name in m.scope.get('ontology', [])
        ]

    # Count by level
    by_level = {}
    for level in range(1, 6):
        count = sum(1 for m in exemplars if m.scope.get('curriculum_level') == level)
        by_level[level] = count

    # Count by ontology
    by_ontology = {}
    for exemplar in exemplars:
        ontologies = exemplar.scope.get('ontology', [])
        if isinstance(ontologies, list):
            for ont in ontologies:
                by_ontology[ont] = by_ontology.get(ont, 0) + 1
        else:
            by_ontology[ontologies] = by_ontology.get(ontologies, 0) + 1

    # Find missing levels
    missing_levels = [level for level in range(1, 6) if by_level.get(level, 0) == 0]

    return {
        'total_exemplars': len(exemplars),
        'by_level': by_level,
        'by_ontology': by_ontology,
        'missing_levels': missing_levels,
    }
