#!/usr/bin/env python3
"""Inject hand-crafted seed heuristics into ReasoningBank.

Based on cross-trajectory analysis showing common inefficiencies,
these heuristics provide expert guidance that single-trajectory
extraction misses.

Usage:
    python scripts/seed_memory_heuristics.py [--db-path evals/memory.db] [--clear]
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm_runtime.memory import SQLiteMemoryBackend, MemoryItem


def create_seed_heuristics() -> list[MemoryItem]:
    """Create seed heuristics based on tool usage analysis."""

    now = datetime.now(timezone.utc).isoformat()

    heuristics = []

    # Heuristic 1: Phase Transition After Remote Success
    h1 = MemoryItem(
        memory_id=MemoryItem.compute_id(
            "Phase Transition After Remote Success",
            "Stop exploring after remote query succeeds"
        ),
        title="Phase Transition After Remote Success",
        description="Transition from exploration to execution phase once remote connectivity is validated",
        content="""1. Use query(local) to find target class and properties (1-2 iterations)
2. Test remote connection with simple query
3. **Once remote returns results, STOP exploration**
4. Switch to hierarchical query construction
5. Test rdfs:subClassOf+, skos:narrower+, etc.
6. Refine and submit

❌ Do NOT after remote works:
- describe_entity() on individual instances
- Exploratory queries for random samples
- Deep dives into single entities

✅ DO instead:
- Test hierarchical predicates systematically
- Build query incrementally
- Focus on completeness, not examples""",
        source_type="human",
        task_query="General SPARQL query construction guidance",
        created_at=now,
        tags=["meta-strategy", "efficiency", "phase-transition", "sparql", "exploration"],
        scope={"transferable": True, "task_types": ["sparql", "taxonomy", "hierarchy"]},
        provenance={
            "source": "cross-trajectory-analysis",
            "analyst": "human",
            "trials_analyzed": 3,
            "document": "docs/analysis/tool-usage-inefficiency-analysis.md"
        }
    )
    heuristics.append(h1)

    # Heuristic 2: Systematic Property Testing
    h2 = MemoryItem(
        memory_id=MemoryItem.compute_id(
            "Systematic Hierarchical Property Testing",
            "Test hierarchy properties systematically without repetition"
        ),
        title="Systematic Hierarchical Property Testing",
        description="When finding hierarchical relationships, test candidate properties systematically without repeating failures",
        content="""When building hierarchical queries:

1. List candidate properties first:
   - rdfs:subClassOf / rdfs:subClassOf+ (OWL/RDFS)
   - skos:narrower / skos:narrowerTransitive+ (SKOS)
   - skos:broader / skos:broaderTransitive+
   - up:partOfLineage (domain-specific)

2. Test each systematically:
   - Try property with sample query
   - If returns 0 results, move to next
   - Don't repeat failed property more than once

3. If all standard properties fail:
   - Use probe_relationships() to discover actual properties
   - Use query(local) to check property definitions
   - Check domain-specific documentation

Common mistakes:
❌ Trying up:partOfLineage 3 times (returns nothing)
✅ Try once, move to rdfs:subClassOf or skos:narrower""",
        source_type="human",
        task_query="Finding hierarchical relationships in SPARQL",
        created_at=now,
        tags=["property-testing", "hierarchy", "sparql", "systematic", "efficiency"],
        scope={"transferable": True, "task_types": ["sparql", "hierarchy", "taxonomy"]},
        provenance={
            "source": "cross-trajectory-analysis",
            "analyst": "human",
            "pattern": "repeated-failed-property-attempts"
        }
    )
    heuristics.append(h2)

    # Heuristic 3: Task Scope Recognition
    h3 = MemoryItem(
        memory_id=MemoryItem.compute_id(
            "Task Scope Recognition: All vs One",
            "Distinguish between finding all instances vs finding one example"
        ),
        title="Task Scope Recognition: All vs One",
        description="Choose strategy based on whether task requires all instances or just one example",
        content="""Recognize task scope and adjust strategy:

**Find ALL instances** (e.g., "all bacterial taxa"):
✓ Use transitive hierarchy queries (?taxon subClassOf+ bacteria)
✓ Avoid LIMIT clauses in final query
✓ Test hierarchy predicates (rdfs:subClassOf+, skos:narrower+)
✗ Don't inspect individual entity lineages
✗ Don't use describe_entity on samples

**Find ONE example** (e.g., "give example of activity"):
✓ Use describe_entity to inspect structure
✓ Check sample instance properties
✓ Validate one case thoroughly
✗ Don't construct exhaustive queries

**Explore structure** (e.g., "what properties relate taxa"):
✓ Use probe_relationships
✓ Query for property patterns
✓ Use describe_entity on key classes
✗ Don't try to get all instances

Match your iteration strategy to task scope.""",
        source_type="human",
        task_query="Strategy selection based on task requirements",
        created_at=now,
        tags=["task-scope", "strategy-selection", "all-vs-one", "meta-strategy"],
        scope={"transferable": True, "task_types": ["sparql", "discovery", "taxonomy"]},
        provenance={
            "source": "cross-trajectory-analysis",
            "analyst": "human",
            "pattern": "scope-mismatch"
        }
    )
    heuristics.append(h3)

    # Heuristic 4: Minimal Code Pattern
    h4 = MemoryItem(
        memory_id=MemoryItem.compute_id(
            "Minimal Code Pattern for Tool Use",
            "Write minimal code focused on tool calls, not display"
        ),
        title="Minimal Code Pattern for Tool Use",
        description="Keep code minimal and focused on tool calls; avoid unnecessary printing and boilerplate",
        content="""Write concise code focused on tool calls:

✓ GOOD pattern:
```python
query = "SELECT ..."
sparql_query(query, "result")
sample = res_head("result", 10)
```

✗ BAD pattern:
```python
query = "SELECT ..."
result = sparql_query(query, "result")
sample = res_head("result", 10)
print("Results:")
for i, row in enumerate(sample):
    print(f"  {i+1}. {row['field']}")
```

Key principles:
1. Tool outputs are logged automatically - don't print()
2. Don't use for-loops just to display results
3. Trust tool outputs without manual inspection
4. Keep iterations to 5-15 lines, not 30-50

Focus on:
- Query construction
- Tool invocation
- Logic and decisions

Not on:
- Display formatting
- Manual result inspection
- Verbose output""",
        source_type="human",
        task_query="Code efficiency and style for RLM tool use",
        created_at=now,
        tags=["code-style", "efficiency", "boilerplate", "minimal"],
        scope={"transferable": True, "applies_to": ["all-tool-use"]},
        provenance={
            "source": "cross-trajectory-analysis",
            "analyst": "human",
            "pattern": "excessive-boilerplate"
        }
    )
    heuristics.append(h4)

    return heuristics


def main():
    parser = argparse.ArgumentParser(
        description="Inject seed heuristics into ReasoningBank"
    )
    parser.add_argument(
        '--db-path',
        default='evals/memory.db',
        help='Path to memory database (default: evals/memory.db)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing human-sourced memories before adding'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be added without modifying database'
    )

    args = parser.parse_args()

    # Create seed heuristics
    heuristics = create_seed_heuristics()

    print(f"Created {len(heuristics)} seed heuristics:")
    for i, h in enumerate(heuristics, 1):
        print(f"\n{i}. {h.title}")
        print(f"   {h.description}")
        print(f"   Tags: {', '.join(h.tags)}")

    if args.dry_run:
        print("\n[DRY RUN] Would add these to database, but not actually modifying.")
        return

    # Connect to database
    backend = SQLiteMemoryBackend(args.db_path)

    # Clear existing human memories if requested
    if args.clear:
        # Note: SQLiteMemoryBackend doesn't have delete_by_source_type method
        # Would need to add this or do manual SQL
        print("\n[WARNING] --clear not yet implemented. Skipping.")

    # Add heuristics
    print(f"\nAdding to {args.db_path}...")
    added = 0
    skipped = 0

    for h in heuristics:
        if backend.has_memory(h.memory_id):
            print(f"  SKIP: {h.title} (already exists)")
            skipped += 1
        else:
            backend.add_memory(h)
            print(f"  ADD:  {h.title}")
            added += 1

    print(f"\nSummary: Added {added}, Skipped {skipped}")

    # Show stats
    all_memories = backend.get_all_memories()
    by_source = {}
    for m in all_memories:
        by_source[m.source_type] = by_source.get(m.source_type, 0) + 1

    print(f"\nTotal memories in database: {len(all_memories)}")
    for source, count in sorted(by_source.items()):
        print(f"  {source}: {count}")


if __name__ == "__main__":
    main()
