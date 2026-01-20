"""Unit tests for memory pack import/export.

Tests JSONL export, import, validation, and merging of memory packs.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone

from rlm_runtime.memory import (
    SQLiteMemoryBackend,
    MemoryItem,
    export_pack,
    import_pack,
    validate_pack,
    merge_packs,
)


@pytest.fixture
def backend():
    """Create in-memory backend for testing."""
    return SQLiteMemoryBackend(":memory:")


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    return [
        MemoryItem(
            memory_id="m-001",
            title="Search Entity Pattern",
            description="How to search for entities",
            content="1. Use search_entity()\n2. Check results",
            source_type="success",
            task_query="How to find entities?",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["search", "entity"],
            scope={"ontology": "prov"},
            provenance={"run_id": "r-001"}
        ),
        MemoryItem(
            memory_id="m-002",
            title="Describe Pattern",
            description="How to describe entities",
            content="1. Use describe_entity()\n2. Read properties",
            source_type="success",
            task_query="How to get details?",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["describe"],
            scope={"ontology": "prov"},
            provenance={"run_id": "r-001"}
        ),
        MemoryItem(
            memory_id="m-003",
            title="Failure Pattern",
            description="Common mistake",
            content="Don't do this",
            source_type="failure",
            task_query="Wrong approach",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["error"],
            scope={},
            provenance={"run_id": "r-002"}
        ),
    ]


class TestPackExport:
    """Test pack export functionality."""

    def test_export_pack_creates_file(self, backend, sample_memories):
        """export_pack creates JSONL file."""
        # Add memories
        for mem in sample_memories:
            backend.add_memory(mem)

        # Export to temp file
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            pack_path = f.name

        try:
            count = export_pack(backend, pack_path)
            assert count == 3
            assert Path(pack_path).exists()
        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_export_pack_jsonl_format(self, backend, sample_memories):
        """Exported pack is valid JSONL."""
        for mem in sample_memories:
            backend.add_memory(mem)

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            pack_path = f.name

        try:
            export_pack(backend, pack_path)

            # Read and parse JSONL
            with open(pack_path, "r") as f:
                lines = f.readlines()

            assert len(lines) == 3

            # Each line should be valid JSON
            for line in lines:
                data = json.loads(line)
                assert "memory_id" in data
                assert "title" in data
                assert "content" in data

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_export_pack_with_filter(self, backend, sample_memories):
        """export_pack filters by source_type."""
        for mem in sample_memories:
            backend.add_memory(mem)

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            pack_path = f.name

        try:
            # Export only success memories
            count = export_pack(
                backend,
                pack_path,
                filters={"source_type": "success"}
            )

            assert count == 2  # Only m-001 and m-002

            # Verify contents
            with open(pack_path, "r") as f:
                lines = f.readlines()
            assert len(lines) == 2

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_export_pack_creates_parent_dirs(self, backend, sample_memories):
        """export_pack creates parent directories."""
        for mem in sample_memories[:1]:
            backend.add_memory(mem)

        with tempfile.TemporaryDirectory() as tmpdir:
            pack_path = Path(tmpdir) / "subdir" / "nested" / "pack.jsonl"

            export_pack(backend, pack_path)

            assert pack_path.exists()
            assert pack_path.parent.exists()


class TestPackImport:
    """Test pack import functionality."""

    def test_import_pack_loads_memories(self, backend):
        """import_pack loads memories from JSONL."""
        # Create pack file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            for i in range(3):
                memory = MemoryItem(
                    memory_id=f"m-{i:03d}",
                    title=f"Memory {i}",
                    description="Desc",
                    content="Content",
                    source_type="pack",
                    task_query="q",
                    created_at=datetime.now(timezone.utc).isoformat()
                )
                f.write(json.dumps(memory.to_dict()) + "\n")

        try:
            result = import_pack(backend, pack_path)

            assert result["imported"] == 3
            assert result["skipped"] == 0
            assert result["total"] == 3

            # Verify memories were imported
            memories = backend.get_all_memories()
            assert len(memories) == 3

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_import_pack_skips_duplicates(self, backend):
        """import_pack skips existing memories."""
        # Add one memory directly
        memory = MemoryItem(
            memory_id="m-001",
            title="Existing",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(memory)

        # Create pack with duplicate
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            f.write(json.dumps(memory.to_dict()) + "\n")

            # Add a new one
            new_memory = MemoryItem(
                memory_id="m-002",
                title="New",
                description="Desc",
                content="Content",
                source_type="pack",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            f.write(json.dumps(new_memory.to_dict()) + "\n")

        try:
            result = import_pack(backend, pack_path, skip_duplicates=True)

            assert result["imported"] == 1  # Only m-002
            assert result["skipped"] == 1  # m-001 skipped
            assert result["total"] == 2

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_import_pack_raises_for_missing_file(self, backend):
        """import_pack raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            import_pack(backend, "nonexistent.jsonl")

    def test_import_pack_raises_for_invalid_json(self, backend):
        """import_pack raises ValueError for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            f.write("not valid json\n")

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                import_pack(backend, pack_path)
        finally:
            Path(pack_path).unlink(missing_ok=True)


class TestPackValidation:
    """Test pack validation."""

    def test_validate_pack_accepts_valid_pack(self):
        """validate_pack returns valid=True for valid pack."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            memory = MemoryItem(
                memory_id="m-001",
                title="Test",
                description="Desc",
                content="Content",
                source_type="success",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            f.write(json.dumps(memory.to_dict()) + "\n")

        try:
            result = validate_pack(pack_path)

            assert result["valid"] is True
            assert result["count"] == 1
            assert result["errors"] == []
            assert result["duplicates"] == 0

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_validate_pack_detects_duplicates(self):
        """validate_pack detects duplicate memory IDs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            memory = MemoryItem(
                memory_id="m-001",
                title="Test",
                description="Desc",
                content="Content",
                source_type="success",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            # Write same memory twice
            f.write(json.dumps(memory.to_dict()) + "\n")
            f.write(json.dumps(memory.to_dict()) + "\n")

        try:
            result = validate_pack(pack_path)

            assert result["valid"] is False
            assert result["count"] == 2
            assert result["duplicates"] == 1
            assert any("Duplicate memory_id" in err for err in result["errors"])

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_validate_pack_detects_missing_fields(self):
        """validate_pack detects missing required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            # Memory with empty title
            data = {
                "memory_id": "m-001",
                "title": "",  # Empty!
                "description": "Desc",
                "content": "Content",
                "source_type": "success",
                "task_query": "q",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            f.write(json.dumps(data) + "\n")

        try:
            result = validate_pack(pack_path)

            assert result["valid"] is False
            assert any("Missing title" in err for err in result["errors"])

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_validate_pack_detects_invalid_source_type(self):
        """validate_pack detects invalid source_type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            pack_path = f.name
            memory = MemoryItem(
                memory_id="m-001",
                title="Test",
                description="Desc",
                content="Content",
                source_type="invalid_type",  # Invalid!
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            f.write(json.dumps(memory.to_dict()) + "\n")

        try:
            result = validate_pack(pack_path)

            assert result["valid"] is False
            assert any("Invalid source_type" in err for err in result["errors"])

        finally:
            Path(pack_path).unlink(missing_ok=True)

    def test_validate_pack_for_missing_file(self):
        """validate_pack handles missing file gracefully."""
        result = validate_pack("nonexistent.jsonl")

        assert result["valid"] is False
        assert result["count"] == 0
        assert any("not found" in err for err in result["errors"])


class TestPackMerge:
    """Test pack merging."""

    def test_merge_packs_combines_files(self):
        """merge_packs combines multiple pack files."""
        # Create two pack files
        pack1 = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        pack2 = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)

        try:
            # Pack 1: 2 memories
            for i in range(2):
                memory = MemoryItem(
                    memory_id=f"m-{i:03d}",
                    title=f"Memory {i}",
                    description="Desc",
                    content="Content",
                    source_type="pack",
                    task_query="q",
                    created_at=datetime.now(timezone.utc).isoformat()
                )
                pack1.write(json.dumps(memory.to_dict()) + "\n")
            pack1.close()

            # Pack 2: 2 different memories
            for i in range(2, 4):
                memory = MemoryItem(
                    memory_id=f"m-{i:03d}",
                    title=f"Memory {i}",
                    description="Desc",
                    content="Content",
                    source_type="pack",
                    task_query="q",
                    created_at=datetime.now(timezone.utc).isoformat()
                )
                pack2.write(json.dumps(memory.to_dict()) + "\n")
            pack2.close()

            # Merge
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as out_f:
                output_path = out_f.name

            result = merge_packs(
                [pack1.name, pack2.name],
                output_path,
                deduplicate=False
            )

            assert result["total"] == 4
            assert result["unique"] == 4
            assert result["duplicates_removed"] == 0

            # Verify merged file
            with open(output_path, "r") as f:
                lines = f.readlines()
            assert len(lines) == 4

            Path(output_path).unlink(missing_ok=True)

        finally:
            Path(pack1.name).unlink(missing_ok=True)
            Path(pack2.name).unlink(missing_ok=True)

    def test_merge_packs_deduplicates(self):
        """merge_packs removes duplicates when deduplicate=True."""
        # Create two packs with overlap
        pack1 = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        pack2 = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)

        try:
            # Pack 1: m-001, m-002
            for i in range(2):
                memory = MemoryItem(
                    memory_id=f"m-{i:03d}",
                    title=f"Memory {i}",
                    description="Desc",
                    content="Content",
                    source_type="pack",
                    task_query="q",
                    created_at=datetime.now(timezone.utc).isoformat()
                )
                pack1.write(json.dumps(memory.to_dict()) + "\n")
            pack1.close()

            # Pack 2: m-001 (duplicate), m-003 (new)
            for i in [0, 3]:  # 0 is duplicate
                memory = MemoryItem(
                    memory_id=f"m-{i:03d}",
                    title=f"Memory {i}",
                    description="Desc",
                    content="Content",
                    source_type="pack",
                    task_query="q",
                    created_at=datetime.now(timezone.utc).isoformat()
                )
                pack2.write(json.dumps(memory.to_dict()) + "\n")
            pack2.close()

            # Merge with deduplication
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as out_f:
                output_path = out_f.name

            result = merge_packs(
                [pack1.name, pack2.name],
                output_path,
                deduplicate=True
            )

            assert result["total"] == 4
            assert result["unique"] == 3  # m-000, m-002, m-003
            assert result["duplicates_removed"] == 1

            Path(output_path).unlink(missing_ok=True)

        finally:
            Path(pack1.name).unlink(missing_ok=True)
            Path(pack2.name).unlink(missing_ok=True)

    def test_merge_packs_raises_for_missing_file(self):
        """merge_packs raises FileNotFoundError for missing input."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as out_f:
            output_path = out_f.name

        try:
            with pytest.raises(FileNotFoundError):
                merge_packs(
                    ["nonexistent1.jsonl", "nonexistent2.jsonl"],
                    output_path
                )
        finally:
            Path(output_path).unlink(missing_ok=True)


class TestPackRoundtrip:
    """Test export → import roundtrip."""

    def test_export_import_roundtrip(self, backend, sample_memories):
        """Memories survive export → import roundtrip."""
        # Add memories
        for mem in sample_memories:
            backend.add_memory(mem)

        # Export
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            pack_path = f.name

        try:
            export_pack(backend, pack_path)

            # Create new backend and import
            backend2 = SQLiteMemoryBackend(":memory:")
            result = import_pack(backend2, pack_path)

            assert result["imported"] == 3

            # Verify memories match
            original = backend.get_all_memories()
            imported = backend2.get_all_memories()

            assert len(imported) == len(original)

            # Sort by ID for comparison
            original.sort(key=lambda m: m.memory_id)
            imported.sort(key=lambda m: m.memory_id)

            for orig, imp in zip(original, imported):
                assert orig.memory_id == imp.memory_id
                assert orig.title == imp.title
                assert orig.content == imp.content
                assert orig.tags == imp.tags

        finally:
            Path(pack_path).unlink(missing_ok=True)
