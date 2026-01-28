"""Generate verification feedback for SPARQL queries using AGENT_GUIDE.md metadata.

This module provides domain/range constraint checking and anti-pattern detection
by parsing AGENT_GUIDE.md files generated for ontologies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class PropertyMetadata:
    """Metadata for a property extracted from AGENT_GUIDE.md."""
    uri: str
    label: Optional[str] = None
    domain: Optional[str] = None
    range: Optional[str] = None
    description: Optional[str] = None
    usage_pattern: Optional[str] = None


@dataclass
class AgentGuideMetadata:
    """Parsed metadata from an AGENT_GUIDE.md file."""
    ontology_name: str
    properties: dict[str, PropertyMetadata] = field(default_factory=dict)
    anti_patterns: list[str] = field(default_factory=list)
    considerations: list[str] = field(default_factory=list)


def parse_agent_guide(guide_path: Path) -> AgentGuideMetadata:
    """Parse AGENT_GUIDE.md file to extract metadata.

    Args:
        guide_path: Path to AGENT_GUIDE.md file

    Returns:
        AgentGuideMetadata with extracted property info and anti-patterns

    Raises:
        FileNotFoundError: If guide file doesn't exist
    """
    if not guide_path.exists():
        raise FileNotFoundError(f"Agent guide not found: {guide_path}")

    content = guide_path.read_text()

    # Determine ontology name from path (e.g., ontology/uniprot/AGENT_GUIDE.md -> uniprot)
    ontology_name = guide_path.parent.name

    metadata = AgentGuideMetadata(ontology_name=ontology_name)

    # Parse properties from "Key Properties" section
    properties_section_match = re.search(
        r'## Key Properties\n\n(.+?)(?=\n## |\Z)',
        content,
        re.DOTALL
    )

    if properties_section_match:
        properties_text = properties_section_match.group(1)
        metadata.properties = _parse_properties_section(properties_text)

    # Parse anti-patterns and considerations from various sections
    # Look for "Gotchas", "Anti-Patterns", "Common Mistakes", "Considerations", "Tips", etc.
    # Allow for extra words after keywords (e.g., "Anti-Patterns Avoided", "Tips for Performance")
    guidance_section_matches = re.finditer(
        r'(?:^|\n)(## (?:Key )?(?:Gotchas?|Anti-?Patterns?|Common Mistakes?|What Not to Do|Important (?:Query )?Considerations?|Performance Tips?|Tips?|Best Practices?|Troubleshooting)[^\n]*)\n+(.+?)(?=\n## |\Z)',
        content,
        re.DOTALL | re.IGNORECASE | re.MULTILINE
    )

    for match in guidance_section_matches:
        section_name = match.group(1).strip()  # Group 1 is now the section heading
        section_text = match.group(2)  # Group 2 is the section content

        # Determine if this is anti-patterns or considerations based on section name
        section_lower = section_name.lower()
        is_anti_pattern = any(term in section_lower for term in [
            'gotcha', 'anti-pattern', 'antipattern',
            'mistake', 'what not', 'avoided', 'what not to do'
        ])

        # Extract items from the section
        items = _extract_guidance_items(section_text)

        if is_anti_pattern:
            metadata.anti_patterns.extend(items)
        else:
            metadata.considerations.extend(items)

    return metadata


def _extract_guidance_items(section_text: str) -> list[str]:
    """Extract guidance items from a section (numbered or bulleted lists).

    Handles:
    - Numbered lists: 1., 2., 3.
    - Bullet lists: -, *, •
    - Items with bold headings: **Don't...**
    - Nested subsections: ### Subsection Title
    """
    items = []

    # Pattern 1: Numbered lists (1., 2., 3.)
    numbered = re.findall(
        r'(?:^|\n)\d+\.\s+\*?\*?([^\n]+(?:\n(?![\d\n])[^\n]+)*)',
        section_text,
        re.MULTILINE
    )
    items.extend([item.strip() for item in numbered if item.strip()])

    # Pattern 2: Bullet lists (-, *, •)
    bullets = re.findall(
        r'(?:^|\n)[-\*•]\s+([^\n]+(?:\n(?![-\*•\n#])[^\n]+)*)',
        section_text,
        re.MULTILINE
    )
    items.extend([item.strip() for item in bullets if item.strip() and item.strip() not in items])

    # Pattern 3: Bold statements (often anti-patterns)
    bold_statements = re.findall(
        r'\*\*([^*]+)\*\*\s*[-–—]?\s*([^\n]+)',
        section_text
    )
    for statement, description in bold_statements:
        combined = f"{statement.strip()}: {description.strip()}"
        if combined not in items and len(combined) > 20:  # Avoid duplicates and short fragments
            items.append(combined)

    return items


def _parse_properties_section(properties_text: str) -> dict[str, PropertyMetadata]:
    """Parse property metadata from Key Properties section.

    Handles various formats:
    - **up:property** - Description
    - ### property_name
      - **Domain**: X → **Range**: Y
    - Bullet lists with domain/range
    """
    properties = {}

    # Format 1: Heading-based (e.g., UniProt guide)
    # ### Protein Properties
    # - **up:organism** - Links to taxon
    property_matches = re.finditer(
        r'\*\*([^*]+)\*\*\s*[-–—]\s*(.+?)(?=\n\*\*|\n\n|\Z)',
        properties_text,
        re.DOTALL
    )

    for match in property_matches:
        prop_name = match.group(1).strip()
        description = match.group(2).strip()

        # Try to extract domain/range from description
        domain_match = re.search(r'(?:Domain|domain):\s*([^\n,;]+)', description)
        range_match = re.search(r'(?:Range|range):\s*([^\n,;]+)', description)

        properties[prop_name] = PropertyMetadata(
            uri=prop_name,
            label=prop_name.split(':')[-1] if ':' in prop_name else None,
            domain=domain_match.group(1).strip() if domain_match else None,
            range=range_match.group(1).strip() if range_match else None,
            description=description,
        )

    # Format 2: Detailed format with explicit domain/range (e.g., PROV guide)
    # ### 1. **generated**
    # - **Domain**: Activity → **Range**: Entity
    detailed_matches = re.finditer(
        r'###\s*\d*\.?\s*\*\*([^*]+)\*\*\s*\n(.+?)(?=\n### |\n## |\Z)',
        properties_text,
        re.DOTALL
    )

    for match in detailed_matches:
        prop_name = match.group(1).strip()
        details = match.group(2)

        domain_match = re.search(r'\*\*Domain\*\*:\s*([^→\n]+)', details)
        range_match = re.search(r'\*\*Range\*\*:\s*([^\n]+)', details)
        usage_match = re.search(r'\*\*Usage\*\*:\s*(.+?)(?=\n\*\*|\n\n|\Z)', details, re.DOTALL)

        properties[prop_name] = PropertyMetadata(
            uri=prop_name,
            label=prop_name.split(':')[-1] if ':' in prop_name else None,
            domain=domain_match.group(1).strip() if domain_match else None,
            range=range_match.group(1).strip() if range_match else None,
            description=details.strip(),
            usage_pattern=usage_match.group(1).strip() if usage_match else None,
        )

    return properties


def verify_sparql_query(
    query: str,
    results: list,
    guide_metadata: AgentGuideMetadata
) -> dict:
    """Verify a SPARQL query against ontology metadata.

    Args:
        query: SPARQL query string
        results: Query results (list of dicts)
        guide_metadata: Parsed AGENT_GUIDE.md metadata

    Returns:
        dict with keys:
        - has_issues: bool
        - constraint_violations: list of str
        - anti_pattern_matches: list of str
        - suggestions: list of str
    """
    verification = {
        'has_issues': False,
        'constraint_violations': [],
        'anti_pattern_matches': [],
        'suggestions': [],
    }

    # Check domain/range constraints
    constraint_violations = check_domain_range_constraints(query, guide_metadata)
    if constraint_violations:
        verification['has_issues'] = True
        verification['constraint_violations'] = constraint_violations

    # Detect anti-patterns
    anti_pattern_matches = detect_anti_patterns(query, guide_metadata)
    if anti_pattern_matches:
        verification['has_issues'] = True
        verification['anti_pattern_matches'] = anti_pattern_matches

    # Generate suggestions
    suggestions = generate_suggestions(query, results, guide_metadata)
    if suggestions:
        verification['suggestions'] = suggestions

    return verification


def check_domain_range_constraints(
    query: str,
    guide_metadata: AgentGuideMetadata
) -> list[str]:
    """Check if query respects domain/range constraints from guide.

    Args:
        query: SPARQL query string
        guide_metadata: Parsed metadata

    Returns:
        List of constraint violation messages
    """
    violations = []

    # Extract triple patterns from query
    # Pattern: ?subject property ?object
    triple_patterns = re.findall(
        r'(\?[\w]+)\s+([^\s?]+)\s+(\?[\w]+|<[^>]+>|"[^"]*")',
        query
    )

    for subject, predicate, obj in triple_patterns:
        # Skip if not a property we have metadata for
        if predicate not in guide_metadata.properties:
            continue

        prop_meta = guide_metadata.properties[predicate]

        # We can't verify domain/range without type information in query
        # This is a limitation - we'd need to track types from previous patterns
        # For now, just skip if no domain/range info
        if not prop_meta.domain and not prop_meta.range:
            continue

        # Note: Full verification would require tracking variable types through the query
        # This is a simplified check that just notes when metadata exists
        # A more sophisticated implementation would build a type inference system

    return violations


def detect_anti_patterns(
    query: str,
    guide_metadata: AgentGuideMetadata
) -> list[str]:
    """Detect anti-patterns in query based on guide metadata.

    Args:
        query: SPARQL query string
        guide_metadata: Parsed metadata

    Returns:
        List of detected anti-pattern descriptions
    """
    matches = []

    query_lower = query.lower()

    for anti_pattern in guide_metadata.anti_patterns:
        anti_pattern_lower = anti_pattern.lower()

        # Specific pattern detection rules

        # Pattern 1: "Don't reuse Entity URIs" or "Don't use X"
        if "don't" in anti_pattern_lower or "avoid" in anti_pattern_lower:
            # Extract what to avoid
            dont_match = re.search(r"don't\s+(?:reuse|use)\s+([^f]+?)(?:\s+for|\s+when|$)", anti_pattern_lower)
            avoid_match = re.search(r"avoid\s+(.+?)(?:\s*[-–—]|\.|$)", anti_pattern_lower)

            pattern_to_check = None
            if dont_match:
                pattern_to_check = dont_match.group(1).strip()
            elif avoid_match:
                pattern_to_check = avoid_match.group(1).strip()

            if pattern_to_check:
                # Check for keywords from the pattern in query
                keywords = [w for w in pattern_to_check.split() if len(w) > 3]
                if any(kw in query_lower for kw in keywords):
                    matches.append(f"⚠ Possible anti-pattern: {anti_pattern}")
                    continue

        # Pattern 2: Label filtering (common anti-pattern)
        if "label" in anti_pattern_lower and any(term in anti_pattern_lower for term in ["search", "filter", "known"]):
            if re.search(r'filter\s*\([^)]*label[^)]*\)', query_lower):
                matches.append(f"⚠ Label filtering detected: {anti_pattern}")
                continue

        # Pattern 3: Property paths on materialized hierarchies
        if "materialized" in anti_pattern_lower or ("rdfs:subclassof" in anti_pattern_lower and ("+" in anti_pattern_lower or "*" in anti_pattern_lower)):
            if re.search(r'rdfs:subclassof\s*[\+\*]', query_lower):
                matches.append(f"⚠ Property path on materialized hierarchy: {anti_pattern}")
                continue

        # Pattern 4: NOT operator usage (if mentioned)
        if "not" in anti_pattern_lower and "operator" in anti_pattern_lower:
            if re.search(r'\bnot\s+', query_lower):
                matches.append(f"⚠ NOT operator usage: {anti_pattern}")
                continue

        # Pattern 5: Generic keyword matching (if specific patterns didn't match)
        # Extract key technical terms from anti-pattern
        technical_terms = re.findall(r'(?:rdfs:|owl:|up:|prov:)[\w]+|filter|limit|offset', anti_pattern_lower)
        if len(technical_terms) >= 2:
            if all(term in query_lower for term in technical_terms):
                matches.append(f"⚠ Detected pattern: {anti_pattern}")

    return matches


def generate_suggestions(
    query: str,
    results: list,
    guide_metadata: AgentGuideMetadata
) -> list[str]:
    """Generate helpful suggestions based on query and results.

    Args:
        query: SPARQL query string
        results: Query results
        guide_metadata: Parsed metadata

    Returns:
        List of suggestion messages
    """
    suggestions = []

    query_upper = query.upper()

    # Check if LIMIT is present
    if 'LIMIT' not in query_upper:
        suggestions.append("💡 Consider adding LIMIT during development for faster iteration")

    # Check result count
    if len(results) > 1000:
        suggestions.append(f"💡 Query returned {len(results)} results - consider adding filters to narrow scope")
    elif len(results) == 0:
        suggestions.append("💡 No results returned - verify entity URIs and property paths are correct")

    # Check for considerations that might apply
    for consideration in guide_metadata.considerations:
        # If consideration mentions specific terms that appear in query, include it
        consideration_lower = consideration.lower()
        query_lower = query.lower()

        # Extract key terms from consideration
        if any(term in query_lower for term in ['reviewed', 'organism', 'filter', 'taxonomy']):
            if any(term in consideration_lower for term in ['reviewed', 'organism', 'filter', 'taxonomy']):
                suggestions.append(f"💡 Tip: {consideration}")

    return suggestions


def format_verification_feedback(verification: dict) -> str:
    """Format verification results as human-readable feedback.

    Args:
        verification: Output from verify_sparql_query()

    Returns:
        Formatted feedback string
    """
    if not verification['has_issues'] and not verification['suggestions']:
        return ""

    lines = ["\n## Verification Feedback\n"]

    # Constraint violations
    if verification['constraint_violations']:
        lines.append("### Constraint Violations\n")
        for violation in verification['constraint_violations']:
            lines.append(f"- ✗ {violation}")
        lines.append("")

    # Anti-patterns
    if verification['anti_pattern_matches']:
        lines.append("### Anti-Patterns Detected\n")
        for match in verification['anti_pattern_matches']:
            lines.append(f"- {match}")
        lines.append("")

    # Suggestions
    if verification['suggestions']:
        lines.append("### Suggestions\n")
        for suggestion in verification['suggestions'][:3]:  # Limit to top 3
            lines.append(f"- {suggestion}")
        lines.append("")

    return "\n".join(lines)


def load_agent_guide_for_ontology(ontology_path: Path) -> Optional[AgentGuideMetadata]:
    """Load AGENT_GUIDE.md for a given ontology file.

    Args:
        ontology_path: Path to ontology file (e.g., ontology/prov.ttl)

    Returns:
        AgentGuideMetadata if guide exists, None otherwise
    """
    ontology_path = Path(ontology_path)

    # Try multiple possible locations
    possible_paths = [
        # ontology/prov.ttl -> ontology/prov/AGENT_GUIDE.md
        ontology_path.parent / ontology_path.stem / "AGENT_GUIDE.md",
        # ontology/dul/DUL.ttl -> ontology/dul/AGENT_GUIDE.md
        ontology_path.parent / "AGENT_GUIDE.md",
    ]

    for guide_path in possible_paths:
        if guide_path.exists():
            return parse_agent_guide(guide_path)

    return None
