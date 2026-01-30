"""Parser for UniProt SPARQL example queries.

UniProt examples are stored as Turtle (TTL) files with SHACL annotations.
Each example contains:
- rdfs:comment: The competency question (what the query answers)
- sh:select: The SPARQL query text
- schema:keywords: Tags/categories
- schema:target: The endpoint URL

Example structure:
```turtle
ex:121_proteins_and_diseases_linked a sh:SPARQLExecutable,
        sh:SPARQLSelectExecutable ;
    rdfs:comment "List all UniProtKB proteins and the diseases..." ;
    sh:prefixes _:sparql_examples_prefixes ;
    sh:select '''
PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?protein ?disease
WHERE { ... }''' ;
    schema:keywords "list" , "disease" ;
    schema:target <https://sparql.uniprot.org/sparql/> .
```

Usage:
    from experiments.reasoningbank.tools.uniprot_examples import (
        parse_example, load_examples
    )

    # Parse single file
    example = parse_example("ontology/uniprot/examples/UniProt/121_*.ttl")

    # Load all examples
    examples = load_examples("ontology/uniprot/examples/UniProt/")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import re


@dataclass
class SPARQLExample:
    """A SPARQL example query with metadata."""
    id: str                    # Filename without extension
    comment: str               # Competency question
    query: str                 # SPARQL query text
    keywords: list[str]        # Tags/categories
    target: str                # Endpoint URL
    file_path: str             # Source file path

    def __repr__(self):
        kw = ', '.join(self.keywords[:3])
        return f"SPARQLExample({self.id!r}, keywords=[{kw}], {len(self.query)} chars)"


def parse_example(file_path: str | Path) -> Optional[SPARQLExample]:
    """Parse a single UniProt SPARQL example TTL file.

    Args:
        file_path: Path to .ttl file

    Returns:
        SPARQLExample or None if parsing fails
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    content = file_path.read_text(encoding='utf-8')

    # Extract ID from filename
    example_id = file_path.stem

    # Extract rdfs:comment (competency question)
    # Pattern: rdfs:comment "text"@en or rdfs:comment "text"^^rdf:HTML
    comment_match = re.search(
        r'rdfs:comment\s+"([^"]+)"(?:@\w+|\^\^[\w:]+)?',
        content,
        re.DOTALL
    )
    comment = comment_match.group(1) if comment_match else ""

    # Clean HTML tags from comment if present
    comment = re.sub(r'<[^>]+>', '', comment)

    # Extract sh:select (SPARQL query)
    # Pattern: sh:select """...""" (triple quotes with content across lines)
    select_match = re.search(
        r'sh:select\s+"""(.*?)"""',
        content,
        re.DOTALL
    )
    query = select_match.group(1).strip() if select_match else ""

    # Extract schema:keywords
    # Pattern: schema:keywords "word1" , "word2" , "word3"
    keywords = []
    keyword_matches = re.findall(r'schema:keywords\s+"([^"]+)"', content)
    keywords = keyword_matches if keyword_matches else []

    # Also handle comma-separated keywords on same line
    keyword_line_match = re.search(
        r'schema:keywords\s+(.+?)\s*[;\.]',
        content,
        re.DOTALL
    )
    if keyword_line_match:
        keyword_line = keyword_line_match.group(1)
        # Extract all quoted strings
        keywords = re.findall(r'"([^"]+)"', keyword_line)

    # Extract schema:target (endpoint URL)
    target_match = re.search(r'schema:target\s+<([^>]+)>', content)
    target = target_match.group(1) if target_match else "https://sparql.uniprot.org/sparql/"

    return SPARQLExample(
        id=example_id,
        comment=comment,
        query=query,
        keywords=keywords,
        target=target,
        file_path=str(file_path)
    )


def load_examples(directory: str | Path, pattern: str = "*.ttl") -> list[SPARQLExample]:
    """Load all SPARQL examples from a directory.

    Args:
        directory: Path to directory containing .ttl files
        pattern: Glob pattern for files (default: "*.ttl")

    Returns:
        List of SPARQLExample objects
    """
    directory = Path(directory)
    if not directory.exists():
        return []

    examples = []
    for file_path in sorted(directory.glob(pattern)):
        example = parse_example(file_path)
        if example and example.query:  # Only include if query was found
            examples.append(example)

    return examples


def filter_examples(
    examples: list[SPARQLExample],
    keywords: Optional[list[str]] = None,
    max_query_length: Optional[int] = None,
    min_query_length: Optional[int] = None
) -> list[SPARQLExample]:
    """Filter examples by criteria.

    Args:
        examples: List of SPARQLExample objects
        keywords: Only include examples with these keywords
        max_query_length: Max query length in characters
        min_query_length: Min query length in characters

    Returns:
        Filtered list of examples
    """
    filtered = examples

    if keywords:
        filtered = [
            ex for ex in filtered
            if any(kw in ex.keywords for kw in keywords)
        ]

    if max_query_length:
        filtered = [ex for ex in filtered if len(ex.query) <= max_query_length]

    if min_query_length:
        filtered = [ex for ex in filtered if len(ex.query) >= min_query_length]

    return filtered


def get_query_complexity(example: SPARQLExample) -> dict:
    """Analyze query complexity.

    Returns dict with:
        - lines: Number of lines
        - clauses: Number of WHERE clauses
        - filters: Number of FILTER clauses
        - unions: Number of UNION clauses
        - optional: Number of OPTIONAL clauses
        - subqueries: Number of nested SELECT queries
    """
    query = example.query

    return {
        'lines': query.count('\n') + 1,
        'clauses': query.upper().count('WHERE'),
        'filters': query.upper().count('FILTER'),
        'unions': query.upper().count('UNION'),
        'optional': query.upper().count('OPTIONAL'),
        'subqueries': query.upper().count('SELECT') - 1,  # -1 for main SELECT
        'length': len(query),
    }


def categorize_by_complexity(examples: list[SPARQLExample]) -> dict[str, list[SPARQLExample]]:
    """Categorize examples by query complexity.

    Categories:
        - simple: < 200 chars, no UNION/OPTIONAL/subqueries
        - moderate: 200-500 chars or has UNION/OPTIONAL
        - complex: > 500 chars or has subqueries

    Returns:
        Dict mapping category names to lists of examples
    """
    simple, moderate, complex = [], [], []

    for ex in examples:
        comp = get_query_complexity(ex)

        if comp['length'] < 200 and comp['subqueries'] == 0 and comp['unions'] == 0 and comp['optional'] == 0:
            simple.append(ex)
        elif comp['length'] > 500 or comp['subqueries'] > 0:
            complex.append(ex)
        else:
            moderate.append(ex)

    return {
        'simple': simple,
        'moderate': moderate,
        'complex': complex,
    }


# Convenience function for quick testing
def test_parser(examples_dir: str = "ontology/uniprot/examples/UniProt"):
    """Quick test of the parser."""
    examples = load_examples(examples_dir)
    print(f"Loaded {len(examples)} examples")

    if examples:
        # Show first example
        ex = examples[0]
        print(f"\nFirst example: {ex.id}")
        print(f"Comment: {ex.comment[:80]}...")
        print(f"Keywords: {ex.keywords}")
        print(f"Query length: {len(ex.query)} chars")
        print(f"Query preview:\n{ex.query[:200]}...")

    # Categorize by complexity
    categories = categorize_by_complexity(examples)
    print(f"\nComplexity distribution:")
    for cat, exs in categories.items():
        print(f"  {cat}: {len(exs)} examples")

    return examples


if __name__ == '__main__':
    test_parser()
