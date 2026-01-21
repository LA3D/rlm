"""Sense card generation: Metadata profile and formalism detection for ontology navigation.

Sense cards describe HOW to read an ontology (metadata conventions, formalism level),
not WHAT is in it (specific classes/properties). The LLM discovers content via tools.
"""

from dataclasses import dataclass
from typing import Optional
from rdflib import Graph, RDF, RDFS, OWL, URIRef
from rdflib.namespace import SKOS, DCTERMS, VOID, FOAF
from pathlib import Path


@dataclass
class FormalismProfile:
    """Detected formalism level and OWL/RDFS constructs used."""

    level: str  # "OWL-DL", "OWL-Lite", "RDFS", "RDF"
    owl_class_count: int = 0
    owl_objprop_count: int = 0
    owl_dataprop_count: int = 0
    owl_restriction_count: int = 0
    owl_disjoint_count: int = 0
    owl_equivalent_count: int = 0
    owl_functional_count: int = 0
    owl_transitive_count: int = 0
    owl_inverse_count: int = 0
    rdfs_subclass_count: int = 0
    rdfs_subprop_count: int = 0
    rdfs_domain_count: int = 0
    rdfs_range_count: int = 0

    def description(self) -> str:
        """Human-readable formalism description."""
        if self.level == "OWL-DL":
            features = []
            if self.owl_restriction_count > 0:
                features.append(f"{self.owl_restriction_count} restrictions")
            if self.owl_disjoint_count > 0:
                features.append(f"{self.owl_disjoint_count} disjointness axioms")
            if self.owl_functional_count > 0:
                features.append("functional properties")
            if self.owl_transitive_count > 0:
                features.append("transitive properties")
            return f"OWL-DL ({', '.join(features)})" if features else "OWL-DL"
        elif self.level == "OWL-Lite":
            return f"OWL-Lite ({self.owl_class_count} classes, {self.owl_objprop_count} properties)"
        elif self.level == "RDFS":
            return f"RDFS ({self.rdfs_subclass_count} subClassOf assertions)"
        else:
            return "RDF (minimal ontological structure)"


@dataclass
class MetadataProfile:
    """Detected metadata vocabularies and annotation properties."""

    # Annotation properties
    label_properties: list[str]
    description_properties: list[str]

    # Vocabulary usage
    uses_skos: bool = False
    uses_void: bool = False
    uses_dcterms: bool = False
    uses_schema_org: bool = False
    uses_foaf: bool = False

    skos_concept_count: int = 0
    skos_scheme_count: int = 0

    def primary_label_prop(self) -> str:
        """Get short name of primary label property."""
        if not self.label_properties:
            return "none"
        prop = self.label_properties[0]
        return prop.split('/')[-1].split('#')[-1]

    def primary_desc_prop(self) -> str:
        """Get short name of primary description property."""
        if not self.description_properties:
            return "none"
        prop = self.description_properties[0]
        return prop.split('/')[-1].split('#')[-1]

    def vocabulary_summary(self) -> str:
        """Summary of metadata vocabularies used."""
        vocabs = []
        if self.uses_skos:
            vocabs.append(f"SKOS ({self.skos_concept_count} concepts)")
        if self.uses_dcterms:
            vocabs.append("DCTERMS")
        if self.uses_foaf:
            vocabs.append("FOAF")
        if self.uses_schema_org:
            vocabs.append("schema.org")
        if self.uses_void:
            vocabs.append("VOID")

        if not vocabs:
            return "Basic RDFS annotations"
        return ", ".join(vocabs)


@dataclass
class SenseCard:
    """Sense card: How to read and navigate this ontology."""

    ontology_name: str
    domain_description: str
    triple_count: int
    class_count: int
    property_count: int
    formalism: FormalismProfile
    metadata: MetadataProfile
    uri_namespace: Optional[str] = None


def detect_formalism(graph: Graph) -> FormalismProfile:
    """Detect OWL/RDFS formalism level and constructs used.

    Args:
        graph: RDF graph to analyze

    Returns:
        FormalismProfile with detected constructs
    """
    # Count OWL constructs
    owl_classes = list(graph.subjects(RDF.type, OWL.Class))
    owl_objprops = list(graph.subjects(RDF.type, OWL.ObjectProperty))
    owl_dataprops = list(graph.subjects(RDF.type, OWL.DatatypeProperty))
    owl_restrictions = list(graph.subjects(RDF.type, OWL.Restriction))
    owl_disjoints = list(graph.triples((None, OWL.disjointWith, None)))
    owl_equivalents = list(graph.triples((None, OWL.equivalentClass, None)))
    owl_inverseof = list(graph.triples((None, OWL.inverseOf, None)))
    owl_functional = list(graph.subjects(RDF.type, OWL.FunctionalProperty))
    owl_transitive = list(graph.subjects(RDF.type, OWL.TransitiveProperty))

    # Count RDFS constructs
    rdfs_subclassof = list(graph.triples((None, RDFS.subClassOf, None)))
    rdfs_subpropof = list(graph.triples((None, RDFS.subPropertyOf, None)))
    rdfs_domain = list(graph.triples((None, RDFS.domain, None)))
    rdfs_range = list(graph.triples((None, RDFS.range, None)))

    # Determine formalism level
    level = "RDF"
    if len(owl_restrictions) > 0 or len(owl_disjoints) > 0 or len(owl_functional) > 0 or len(owl_transitive) > 0:
        level = "OWL-DL"
    elif len(owl_classes) > 0 and len(owl_objprops) > 0:
        level = "OWL-Lite"
    elif len(rdfs_subclassof) > 0 or len(rdfs_domain) > 0:
        level = "RDFS"

    return FormalismProfile(
        level=level,
        owl_class_count=len(owl_classes),
        owl_objprop_count=len(owl_objprops),
        owl_dataprop_count=len(owl_dataprops),
        owl_restriction_count=len(owl_restrictions),
        owl_disjoint_count=len(owl_disjoints),
        owl_equivalent_count=len(owl_equivalents),
        owl_functional_count=len(owl_functional),
        owl_transitive_count=len(owl_transitive),
        owl_inverse_count=len(owl_inverseof),
        rdfs_subclass_count=len(rdfs_subclassof),
        rdfs_subprop_count=len(rdfs_subpropof),
        rdfs_domain_count=len(rdfs_domain),
        rdfs_range_count=len(rdfs_range)
    )


def detect_metadata_profile(graph: Graph) -> MetadataProfile:
    """Detect metadata vocabularies and annotation properties used.

    Args:
        graph: RDF graph to analyze

    Returns:
        MetadataProfile with detected vocabularies
    """
    # Detect label properties
    label_props = []
    for prop in [RDFS.label, SKOS.prefLabel, SKOS.altLabel, DCTERMS.title]:
        if list(graph.triples((None, prop, None))):
            label_props.append(str(prop))

    # Detect description properties
    desc_props = []
    for prop in [RDFS.comment, SKOS.definition, SKOS.note, DCTERMS.description]:
        if list(graph.triples((None, prop, None))):
            desc_props.append(str(prop))

    # Detect SKOS usage
    skos_concepts = list(graph.subjects(RDF.type, SKOS.Concept))
    skos_schemes = list(graph.subjects(RDF.type, SKOS.ConceptScheme))
    uses_skos = len(skos_concepts) > 0 or len(skos_schemes) > 0 or len(label_props) > 1

    # Detect other vocabularies
    uses_dcterms = any("purl.org/dc/terms" in str(s) or "purl.org/dc/terms" in str(p)
                       for s, p, o in graph)
    uses_foaf = any("xmlns.com/foaf" in str(s) or "xmlns.com/foaf" in str(p)
                    for s, p, o in graph)
    uses_schema_org = any("schema.org" in str(s) or "schema.org" in str(p)
                          for s, p, o in graph)
    uses_void = any("rdfs.org/ns/void" in str(s) or "rdfs.org/ns/void" in str(p)
                    for s, p, o in graph)

    return MetadataProfile(
        label_properties=label_props,
        description_properties=desc_props,
        uses_skos=uses_skos,
        uses_void=uses_void,
        uses_dcterms=uses_dcterms,
        uses_schema_org=uses_schema_org,
        uses_foaf=uses_foaf,
        skos_concept_count=len(skos_concepts),
        skos_scheme_count=len(skos_schemes)
    )


def build_sense_card(ontology_path: str, ontology_name: Optional[str] = None) -> SenseCard:
    """Build sense card from ontology file.

    Args:
        ontology_path: Path to ontology file (TTL, RDF/XML, etc.)
        ontology_name: Optional short name (derived from filename if not provided)

    Returns:
        SenseCard describing how to read the ontology
    """
    # Load graph
    graph = Graph()
    graph.parse(ontology_path)

    # Derive ontology name if not provided
    if ontology_name is None:
        ontology_name = Path(ontology_path).stem

    # Get ontology-level metadata
    ont_uri = None
    domain_description = "No description available"

    for s in graph.subjects(RDF.type, OWL.Ontology):
        ont_uri = s
        break

    if ont_uri:
        for desc_prop in [DCTERMS.description, RDFS.comment]:
            descs = list(graph.objects(ont_uri, desc_prop))
            if descs:
                domain_description = str(descs[0])[:200]
                break

    # Get URI namespace
    uri_namespace = None
    classes = list(graph.subjects(RDF.type, OWL.Class))
    if classes:
        sample_uri = str(classes[0])
        if '/' in sample_uri:
            uri_namespace = sample_uri.rsplit('/', 1)[0]
        elif '#' in sample_uri:
            uri_namespace = sample_uri.rsplit('#', 1)[0]

    # Detect formalism and metadata
    formalism = detect_formalism(graph)
    metadata = detect_metadata_profile(graph)

    # Count classes and properties
    class_count = len(list(graph.subjects(RDF.type, OWL.Class)))
    if class_count == 0:
        class_count = len(list(graph.subjects(RDF.type, RDFS.Class)))

    property_count = (
        len(list(graph.subjects(RDF.type, OWL.ObjectProperty))) +
        len(list(graph.subjects(RDF.type, OWL.DatatypeProperty))) +
        len(list(graph.subjects(RDF.type, RDF.Property)))
    )

    return SenseCard(
        ontology_name=ontology_name,
        domain_description=domain_description,
        triple_count=len(graph),
        class_count=class_count,
        property_count=property_count,
        formalism=formalism,
        metadata=metadata,
        uri_namespace=uri_namespace
    )


def format_sense_card(card: SenseCard) -> str:
    """Format sense card as compact markdown (~500 chars).

    Focus on HOW to read the ontology: formalism level, metadata conventions,
    annotation properties to use for navigation.

    Args:
        card: SenseCard to format

    Returns:
        Markdown string for context injection
    """
    lines = [
        f"# Ontology: {card.ontology_name}",
        "",
        f"**Domain**: {card.domain_description}",
        "",
        f"**Size**: {card.triple_count:,} triples, {card.class_count} classes, {card.property_count} properties",
        "",
        f"**Formalism**: {card.formalism.description()}",
        ""
    ]

    # Metadata profile
    lines.append(f"**Metadata**: {card.metadata.vocabulary_summary()}")

    # Annotation guidance
    lines.append("")
    lines.append("**Navigation:**")
    lines.append(f"- Labels: Use `{card.metadata.primary_label_prop()}` property")
    lines.append(f"- Descriptions: Use `{card.metadata.primary_desc_prop()}` property")

    # Formalism-specific hints
    if card.formalism.level == "OWL-DL":
        if card.formalism.owl_disjoint_count > 0:
            lines.append(f"- Check `owl:disjointWith` for class exclusions ({card.formalism.owl_disjoint_count} axioms)")
        if card.formalism.owl_restriction_count > 0:
            lines.append(f"- Uses OWL restrictions ({card.formalism.owl_restriction_count} found)")

    if card.formalism.rdfs_subclass_count > 20:
        lines.append(f"- Rich hierarchy: {card.formalism.rdfs_subclass_count} subclass relationships")

    return '\n'.join(lines)
