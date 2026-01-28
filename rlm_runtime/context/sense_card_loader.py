"""Load rich sense cards (AGENT_GUIDE.md) for ontologies."""

from pathlib import Path


def load_rich_sense_card(
    ontology_path: Path,
    ontology_name: str,
    *,
    fallback_to_generated: bool = True,
) -> str:
    """Load AGENT_GUIDE.md or generate minimal sense card.

    Priority:
    1. ontology/[name]/AGENT_GUIDE.md (preferred - rich context ~10K+ chars)
    2. Generated sense card (fallback if allowed - minimal ~500 chars)
    3. Error if no guide and fallback disabled

    Args:
        ontology_path: Path to ontology file (e.g., ontology/prov/core.ttl)
        ontology_name: Ontology name (e.g., "prov")
        fallback_to_generated: Allow fallback to generated minimal sense card

    Returns:
        Rich context string (AGENT_GUIDE content or generated sense card)

    Raises:
        FileNotFoundError: If no AGENT_GUIDE.md and fallback disabled

    Examples:
        # Load rich guide (preferred)
        ctx = load_rich_sense_card(Path("ontology/prov/core.ttl"), "prov")

        # Require AGENT_GUIDE (error if missing)
        ctx = load_rich_sense_card(
            Path("ontology/prov/core.ttl"),
            "prov",
            fallback_to_generated=False
        )
    """
    # Check for AGENT_GUIDE.md in ontology directory
    # Handle both ontology/name/file.ttl and ontology/file.ttl patterns
    ontology_path = Path(ontology_path)

    # Try parent directory first (e.g., ontology/prov/AGENT_GUIDE.md)
    guide_path = ontology_path.parent / "AGENT_GUIDE.md"

    if guide_path.exists():
        return guide_path.read_text()

    # Try sibling in named directory (e.g., ontology/prov/AGENT_GUIDE.md when file is ontology/prov.ttl)
    if ontology_path.parent.name == "ontology":
        guide_path_alt = ontology_path.parent / ontology_name / "AGENT_GUIDE.md"
        if guide_path_alt.exists():
            return guide_path_alt.read_text()

    # No AGENT_GUIDE found - fallback or error
    if fallback_to_generated:
        # Generate minimal sense card (current behavior)
        from rlm_runtime.ontology import build_sense_card, format_sense_card

        sense = build_sense_card(str(ontology_path), ontology_name)
        return format_sense_card(sense, include_sparql_templates=True)

    raise FileNotFoundError(
        f"No AGENT_GUIDE.md found for {ontology_name}. "
        f"Create one at {guide_path} or set fallback_to_generated=True"
    )
