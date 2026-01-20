"""Memory Integration Demo (no API required).

Demonstrates the complete memory workflow:
1. Create SQLite backend
2. Store memories with provenance
3. Retrieve and format for context
4. Export to JSONL pack
5. Import from pack

This example doesn't require ANTHROPIC_API_KEY.
"""

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from rlm_runtime.memory import (
    SQLiteMemoryBackend,
    MemoryItem,
    format_memories_for_context,
    export_pack,
    import_pack,
    validate_pack,
)


def main():
    print("=" * 60)
    print("Memory Integration Demo")
    print("=" * 60)

    # Step 1: Create SQLite backend
    print("\n1. Creating SQLite backend...")
    backend = SQLiteMemoryBackend(":memory:")
    print("   ✓ Backend created")

    # Step 2: Add a run and trajectory
    print("\n2. Recording run and trajectory...")
    run_id = backend.add_run(
        "demo-run-001",
        model="claude-sonnet-4-5",
        ontology_name="prov",
        ontology_path="/path/to/prov.ttl",
        notes="Demo run"
    )
    print(f"   ✓ Run recorded: {run_id}")

    trajectory_id = backend.add_trajectory(
        "demo-traj-001",
        run_id,
        "What is prov:Activity?",
        "Activity is a class representing things that happen over time.",
        iteration_count=3,
        converged=True,
        artifact={"iterations": [{"code": "search('Activity')", "output": "Found"}]}
    )
    print(f"   ✓ Trajectory recorded: {trajectory_id}")

    # Step 3: Add judgment
    print("\n3. Adding trajectory judgment...")
    backend.add_judgment(
        trajectory_id,
        is_success=True,
        reason="Answer correctly describes Activity class",
        confidence="high",
        missing=[]
    )
    print("   ✓ Judgment recorded")

    # Step 4: Create and store memories
    print("\n4. Creating procedural memories...")
    memories = [
        MemoryItem(
            memory_id=MemoryItem.compute_id(
                "Entity Search Pattern",
                "1. Use search_entity()\n2. Check results\n3. Use describe_entity()"
            ),
            title="Entity Search Pattern",
            description="Standard workflow for finding and describing ontology entities",
            content="1. Use search_entity() to find candidates\n2. Check if results are empty\n3. Use describe_entity() on the URI to get details\n4. Extract label, types, and comment",
            source_type="success",
            task_query="What is prov:Activity?",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["search", "entity", "describe", "workflow"],
            scope={
                "ontology": "prov",
                "task_types": ["entity_description", "class_lookup"],
                "transferable": True
            },
            provenance={
                "run_id": run_id,
                "trajectory_id": trajectory_id,
                "source": "successful_trajectory"
            }
        ),
        MemoryItem(
            memory_id=MemoryItem.compute_id(
                "Empty Result Handling",
                "1. Check if results empty\n2. Try alternate names\n3. Use broader search"
            ),
            title="Empty Result Handling",
            description="What to do when search returns no results",
            content="1. Check if results are empty before proceeding\n2. Try alternate names or spellings\n3. Use broader search terms\n4. Check if entity exists in different namespace",
            source_type="success",
            task_query="What is prov:Activity?",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["error_handling", "search", "troubleshooting"],
            scope={"transferable": True},
            provenance={"run_id": run_id, "trajectory_id": trajectory_id}
        ),
        MemoryItem(
            memory_id=MemoryItem.compute_id(
                "Label Extraction",
                "1. Get rdfs:label\n2. Fall back to local name\n3. Display with namespace"
            ),
            title="Label Extraction",
            description="How to get human-readable labels from URIs",
            content="1. Try rdfs:label property first\n2. Fall back to skos:prefLabel if no rdfs:label\n3. If no labels, extract local name from URI\n4. Always display with namespace prefix for clarity",
            source_type="success",
            task_query="What is prov:Activity?",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["labels", "display", "uri"],
            scope={"ontology": "prov"},
            provenance={"run_id": run_id, "trajectory_id": trajectory_id}
        )
    ]

    for mem in memories:
        backend.add_memory(mem)
        print(f"   ✓ Stored: {mem.title}")

    # Step 5: Record memory usage
    print("\n5. Recording memory usage...")
    for i, mem in enumerate(memories, 1):
        backend.record_usage(trajectory_id, mem.memory_id, rank=i, score=0.9 - i*0.1)
        backend.update_memory_stats(mem.memory_id, accessed=True, success=True)
    print(f"   ✓ Usage recorded for {len(memories)} memories")

    # Step 6: Retrieve memories
    print("\n6. Retrieving memories for similar task...")
    retrieved = backend.retrieve("How to find prov:Entity?", k=2)
    print(f"   ✓ Retrieved {len(retrieved)} relevant memories:")
    for i, mem in enumerate(retrieved, 1):
        print(f"     {i}. {mem.title}")

    # Step 7: Format for context
    print("\n7. Formatting memories for context injection...")
    formatted = format_memories_for_context(retrieved)
    print("   ✓ Formatted context (first 200 chars):")
    print("   " + formatted[:200].replace("\n", "\n   "))
    print("   ...")

    # Step 8: Export to pack
    print("\n8. Exporting memories to JSONL pack...")
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        pack_path = Path(f.name)

    count = export_pack(backend, pack_path, filters={"source_type": "success"})
    print(f"   ✓ Exported {count} memories to {pack_path.name}")

    # Step 9: Validate pack
    print("\n9. Validating pack...")
    validation = validate_pack(pack_path)
    if validation["valid"]:
        print(f"   ✓ Pack valid: {validation['count']} memories")
    else:
        print(f"   ✗ Pack invalid: {validation['errors']}")

    # Step 10: Import to new backend
    print("\n10. Importing pack to new backend...")
    backend2 = SQLiteMemoryBackend(":memory:")
    result = import_pack(backend2, pack_path)
    print(f"   ✓ Imported: {result['imported']} memories")
    print(f"   ✓ Skipped: {result['skipped']} duplicates")
    print(f"   ✓ Total: {result['total']} entries")

    # Step 11: Verify import
    print("\n11. Verifying imported memories...")
    imported_memories = backend2.get_all_memories()
    print(f"   ✓ Found {len(imported_memories)} memories in new backend")
    for mem in imported_memories:
        print(f"     - {mem.title} (ID: {mem.memory_id[:8]}...)")

    # Step 12: Stats
    print("\n12. Database statistics...")
    stats = backend.get_stats()
    print(f"   - Runs: {stats['runs']}")
    print(f"   - Trajectories: {stats['trajectories']}")
    print(f"   - Judgments: {stats['judgments']}")
    print(f"   - Memories: {stats['memory_items']}")
    print(f"   - Usage records: {stats['memory_usage']}")

    # Cleanup
    pack_path.unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
