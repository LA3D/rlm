"""Load reasoning chain exemplars from markdown files into memory backend.

This module parses PDDL-INSTRUCT style reasoning chain exemplars (markdown format)
and converts them to MemoryItems that can be stored in a MemoryBackend.

Exemplar format:
```markdown
# Reasoning Chain Exemplar: Level N - Title

**Question**: "..."

**Complexity**: LN (description)

---

## Reasoning Chain
[State-Action-State steps]

## Final Query
[SPARQL query]

## Anti-Patterns Avoided
[List of anti-patterns]

## Key Learnings
[List of learnings]
```
"""

from __future__ import annotations

import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from rlm_runtime.memory.backend import MemoryItem, MemoryBackend


def parse_markdown_exemplar(md_content: str) -> dict:
    """Extract structured data from a markdown exemplar.

    Args:
        md_content: Raw markdown content of exemplar file

    Returns:
        dict with keys: question, level, title, reasoning_chain, query,
        anti_patterns, key_learnings

    Raises:
        ValueError: If exemplar format is invalid
    """
    lines = md_content.split('\n')

    # Extract title from first heading
    title_match = re.search(r'^# Reasoning Chain Exemplar: (.+)$', md_content, re.MULTILINE)
    if not title_match:
        raise ValueError("Missing title heading (# Reasoning Chain Exemplar: ...)")
    title = title_match.group(1).strip()

    # Extract question
    question_match = re.search(r'\*\*Question\*\*:\s*"([^"]+)"', md_content)
    if not question_match:
        raise ValueError("Missing **Question**: field")
    question = question_match.group(1).strip()

    # Extract complexity level
    complexity_match = re.search(r'\*\*Complexity\*\*:\s*(L\d+)', md_content)
    if not complexity_match:
        raise ValueError("Missing **Complexity**: field")
    level_str = complexity_match.group(1)  # e.g., "L1"
    level = int(level_str[1:])  # Extract number

    # Extract reasoning chain section
    reasoning_match = re.search(
        r'## Reasoning Chain\n\n(.+?)(?=\n## |\Z)',
        md_content,
        re.DOTALL
    )
    reasoning_chain = reasoning_match.group(1).strip() if reasoning_match else ""

    # Extract final query
    query_match = re.search(
        r'## Final Query\n\n```sparql\n(.+?)\n```',
        md_content,
        re.DOTALL
    )
    query = query_match.group(1).strip() if query_match else ""

    # Extract anti-patterns
    anti_patterns_match = re.search(
        r'## Anti-Patterns Avoided\n\n(.+?)(?=\n## |\Z)',
        md_content,
        re.DOTALL
    )
    anti_patterns = anti_patterns_match.group(1).strip() if anti_patterns_match else ""

    # Extract key learnings
    learnings_match = re.search(
        r'## Key Learnings\n\n(.+?)(?=\Z)',
        md_content,
        re.DOTALL
    )
    key_learnings = learnings_match.group(1).strip() if learnings_match else ""

    return {
        'title': title,
        'question': question,
        'level': level,
        'reasoning_chain': reasoning_chain,
        'query': query,
        'anti_patterns': anti_patterns,
        'key_learnings': key_learnings,
    }


def exemplar_to_memory_item(
    exemplar_dict: dict,
    ontology_name: str,
    source_file: Optional[str] = None
) -> MemoryItem:
    """Convert parsed exemplar dict to MemoryItem.

    Args:
        exemplar_dict: Output from parse_markdown_exemplar()
        ontology_name: Name of ontology (e.g., 'uniprot', 'prov')
        source_file: Optional path to source .md file

    Returns:
        MemoryItem with source_type='exemplar' and appropriate tags
    """
    level = exemplar_dict['level']
    question = exemplar_dict['question']
    title = exemplar_dict['title']

    # Build content as formatted markdown
    content_parts = [
        f"# {title}",
        "",
        f"**Question**: \"{question}\"",
        "",
        "## Reasoning Chain",
        exemplar_dict['reasoning_chain'],
        "",
        "## Final Query",
        "```sparql",
        exemplar_dict['query'],
        "```",
    ]

    if exemplar_dict['anti_patterns']:
        content_parts.extend([
            "",
            "## Anti-Patterns Avoided",
            exemplar_dict['anti_patterns'],
        ])

    if exemplar_dict['key_learnings']:
        content_parts.extend([
            "",
            "## Key Learnings",
            exemplar_dict['key_learnings'],
        ])

    content = "\n".join(content_parts)

    # Generate stable ID
    memory_id = MemoryItem.compute_id(title, content)

    # Build tags
    tags = [
        f'level-{level}',
        ontology_name,
        'exemplar',
        'reasoning-chain',
    ]

    # Build scope
    scope = {
        'ontology': [ontology_name],
        'curriculum_level': level,
        'transferable': False,  # Exemplars are ontology-specific
    }

    # Build provenance
    provenance = {
        'source': 'curriculum',
        'exemplar_level': level,
    }
    if source_file:
        provenance['source_file'] = source_file

    # Create MemoryItem
    return MemoryItem(
        memory_id=memory_id,
        title=title,
        description=f"Level {level} reasoning chain exemplar: {question}",
        content=content,
        source_type='exemplar',
        task_query=question,
        created_at=datetime.now(timezone.utc).isoformat(),
        tags=tags,
        scope=scope,
        provenance=provenance,
    )


def load_exemplars_from_directory(
    exemplar_dir: Path,
    backend: MemoryBackend,
    ontology_name: str,
    pattern: str = "*.md"
) -> list[str]:
    """Load all exemplar markdown files from a directory into memory backend.

    Args:
        exemplar_dir: Directory containing exemplar .md files
        backend: MemoryBackend to store exemplars in
        ontology_name: Name of ontology (e.g., 'uniprot')
        pattern: Glob pattern for files (default: "*.md")

    Returns:
        List of loaded memory IDs

    Raises:
        FileNotFoundError: If exemplar_dir doesn't exist
        ValueError: If any exemplar file is malformed
    """
    exemplar_dir = Path(exemplar_dir)
    if not exemplar_dir.exists():
        raise FileNotFoundError(f"Exemplar directory not found: {exemplar_dir}")

    exemplar_files = sorted(exemplar_dir.glob(pattern))
    if not exemplar_files:
        raise ValueError(f"No exemplar files found matching {pattern} in {exemplar_dir}")

    loaded_ids = []

    for file_path in exemplar_files:
        print(f"Loading exemplar: {file_path.name}")

        # Read and parse
        md_content = file_path.read_text()
        try:
            exemplar_dict = parse_markdown_exemplar(md_content)
        except ValueError as e:
            raise ValueError(f"Error parsing {file_path.name}: {e}") from e

        # Convert to MemoryItem
        memory_item = exemplar_to_memory_item(
            exemplar_dict,
            ontology_name=ontology_name,
            source_file=str(file_path)
        )

        # Check for duplicates (same memory_id)
        existing = backend.get_memory(memory_item.memory_id)
        if existing:
            print(f"  ⚠ Skipping duplicate: {memory_item.memory_id}")
            continue

        # Add to backend
        backend.add_memory(memory_item)
        loaded_ids.append(memory_item.memory_id)
        print(f"  ✓ Loaded as {memory_item.memory_id} (Level {exemplar_dict['level']})")

    print(f"\n✓ Loaded {len(loaded_ids)} exemplars from {exemplar_dir}")
    return loaded_ids


def load_exemplar_from_file(
    file_path: Path,
    backend: MemoryBackend,
    ontology_name: str
) -> str:
    """Load a single exemplar file into memory backend.

    Args:
        file_path: Path to exemplar .md file
        backend: MemoryBackend to store exemplar in
        ontology_name: Name of ontology

    Returns:
        Memory ID of loaded exemplar

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If exemplar format is invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Exemplar file not found: {file_path}")

    # Read and parse
    md_content = file_path.read_text()
    exemplar_dict = parse_markdown_exemplar(md_content)

    # Convert to MemoryItem
    memory_item = exemplar_to_memory_item(
        exemplar_dict,
        ontology_name=ontology_name,
        source_file=str(file_path)
    )

    # Add to backend
    backend.add_memory(memory_item)

    return memory_item.memory_id
