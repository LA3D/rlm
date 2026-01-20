"""Memory pack import/export for ReasoningBank.

Packs are JSONL files (JSON Lines) with one MemoryItem per line.
They provide git-friendly durable storage for curated memories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union, Optional

from .backend import MemoryItem, MemoryBackend


def export_pack(
    backend: MemoryBackend,
    output_path: Union[str, Path],
    filters: Optional[dict] = None,
) -> int:
    """Export memories to a JSONL pack file.

    Args:
        backend: MemoryBackend to export from
        output_path: Path to output JSONL file
        filters: Optional filters (e.g., {"source_type": "success"})

    Returns:
        Number of memories exported

    Example:
        backend = SQLiteMemoryBackend("memory.db")
        count = export_pack(backend, "prov_memories.jsonl", {"source_type": "success"})
        print(f"Exported {count} memories")
    """
    memories = backend.get_all_memories(filters)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for memory in memories:
            # Convert to dict and write as single JSON line
            line = json.dumps(memory.to_dict(), ensure_ascii=False)
            f.write(line + "\n")

    return len(memories)


def import_pack(
    backend: MemoryBackend,
    pack_path: Union[str, Path],
    skip_duplicates: bool = True,
) -> dict[str, int]:
    """Import memories from a JSONL pack file.

    Args:
        backend: MemoryBackend to import into
        pack_path: Path to JSONL pack file
        skip_duplicates: If True, skip memories with existing IDs (default: True)

    Returns:
        Dict with counts: {"imported": N, "skipped": M, "total": N+M}

    Example:
        backend = SQLiteMemoryBackend("memory.db")
        result = import_pack(backend, "prov_memories.jsonl")
        print(f"Imported {result['imported']} memories, skipped {result['skipped']}")
    """
    pack_path = Path(pack_path)

    if not pack_path.exists():
        raise FileNotFoundError(f"Pack file not found: {pack_path}")

    imported = 0
    skipped = 0
    total = 0

    with open(pack_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue  # Skip empty lines

            try:
                data = json.loads(line)
                memory = MemoryItem.from_dict(data)

                # Check if already exists
                if skip_duplicates and backend.has_memory(memory.memory_id):
                    skipped += 1
                else:
                    backend.add_memory(memory)
                    imported += 1

                total += 1

            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}") from e
            except Exception as e:
                raise ValueError(f"Error processing memory at line {line_num}: {e}") from e

    return {"imported": imported, "skipped": skipped, "total": total}


def validate_pack(pack_path: Union[str, Path]) -> dict[str, any]:
    """Validate a memory pack file without importing.

    Args:
        pack_path: Path to JSONL pack file

    Returns:
        Dict with validation results:
            - valid: bool - Whether pack is valid
            - count: int - Number of memories
            - errors: list[str] - Validation errors if any
            - duplicates: int - Number of duplicate IDs within pack

    Example:
        result = validate_pack("prov_memories.jsonl")
        if not result["valid"]:
            print("Errors:", result["errors"])
    """
    pack_path = Path(pack_path)

    if not pack_path.exists():
        return {
            "valid": False,
            "count": 0,
            "errors": [f"Pack file not found: {pack_path}"],
            "duplicates": 0
        }

    errors = []
    seen_ids = set()
    duplicates = 0
    count = 0

    with open(pack_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                memory = MemoryItem.from_dict(data)

                # Check for duplicate IDs
                if memory.memory_id in seen_ids:
                    duplicates += 1
                    errors.append(f"Line {line_num}: Duplicate memory_id '{memory.memory_id}'")
                else:
                    seen_ids.add(memory.memory_id)

                # Validate required fields
                if not memory.title:
                    errors.append(f"Line {line_num}: Missing title")
                if not memory.content:
                    errors.append(f"Line {line_num}: Missing content")
                if memory.source_type not in ["success", "failure", "human", "pack"]:
                    errors.append(f"Line {line_num}: Invalid source_type '{memory.source_type}'")

                count += 1

            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
            except Exception as e:
                errors.append(f"Line {line_num}: Error - {e}")

    return {
        "valid": len(errors) == 0,
        "count": count,
        "errors": errors,
        "duplicates": duplicates
    }


def merge_packs(
    input_paths: list[Union[str, Path]],
    output_path: Union[str, Path],
    deduplicate: bool = True,
) -> dict[str, int]:
    """Merge multiple pack files into one, optionally deduplicating.

    Args:
        input_paths: List of pack files to merge
        output_path: Output pack file path
        deduplicate: If True, keep only first occurrence of each memory_id

    Returns:
        Dict with counts: {"total": N, "unique": M, "duplicates_removed": N-M}

    Example:
        result = merge_packs(
            ["pack1.jsonl", "pack2.jsonl"],
            "merged.jsonl",
            deduplicate=True
        )
        print(f"Merged {result['unique']} unique memories")
    """
    seen_ids = set()
    total = 0
    unique = 0

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as out_f:
        for pack_path in input_paths:
            pack_path = Path(pack_path)

            if not pack_path.exists():
                raise FileNotFoundError(f"Pack file not found: {pack_path}")

            with open(pack_path, "r") as in_f:
                for line in in_f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)
                    memory_id = data.get("memory_id")

                    total += 1

                    if deduplicate and memory_id in seen_ids:
                        continue

                    seen_ids.add(memory_id)
                    unique += 1
                    out_f.write(line + "\n")

    return {
        "total": total,
        "unique": unique,
        "duplicates_removed": total - unique
    }
