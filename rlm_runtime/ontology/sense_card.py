"""Sense card generation: Metadata profile and formalism detection for ontology navigation.

Sense cards describe HOW to read an ontology (metadata conventions, formalism level),
not WHAT is in it (specific classes/properties). The LLM discovers content via tools.
"""

from dataclasses import dataclass, field
from typing import Optional
from rdflib import Graph, RDF, RDFS, OWL, URIRef, Namespace
from rdflib.namespace import SKOS, DCTERMS, VOID, FOAF
from pathlib import Path

# Additional metadata vocabularies from Widoco guide
PAV = Namespace("http://purl.org/pav/")
PROV = Namespace("http://www.w3.org/ns/prov#")
VANN = Namespace("http://purl.org/vocab/vann/")
BIBO = Namespace("http://purl.org/ontology/bibo/")
VS = Namespace("http://www.w3.org/2003/06/sw-vocab-status/ns#")


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

    # NEW: Widoco metadata patterns
    # Imports (owl:imports)
    imports_count: int = 0
    imported_ontologies: list[str] = field(default_factory=list)

    # Version metadata
    has_version_info: bool = False
    version_string: Optional[str] = None
    has_version_iri: bool = False

    # Maturity/Status
    deprecated_term_count: int = 0
    status_value: Optional[str] = None

    # Provenance vocabularies
    uses_pav: bool = False
    uses_prov: bool = False
    uses_vann: bool = False

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
        if self.uses_pav:
            vocabs.append("PAV")
        if self.uses_prov:
            vocabs.append("PROV")
        if self.uses_vann:
            vocabs.append("VANN")

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


def detect_imports(graph: Graph) -> tuple[int, list[str]]:
    """Detect owl:imports declarations.

    Args:
        graph: RDF graph to analyze

    Returns:
        Tuple of (import_count, list of imported ontology names)
    """
    imports = list(graph.objects(predicate=OWL.imports))
    import_names = []
    for imp in imports:
        # Extract short name from URI
        uri_str = str(imp)
        if '/' in uri_str:
            name = uri_str.rsplit('/', 1)[-1]
        elif '#' in uri_str:
            name = uri_str.rsplit('#', 1)[-1]
        else:
            name = uri_str
        import_names.append(name)
    return len(imports), import_names


def detect_version_info(graph: Graph) -> tuple[bool, Optional[str], bool]:
    """Detect version metadata (owl:versionInfo, owl:versionIRI).

    Args:
        graph: RDF graph to analyze

    Returns:
        Tuple of (has_version_info, version_string, has_version_iri)
    """
    # Find ontology URI
    ont_uri = None
    for s in graph.subjects(RDF.type, OWL.Ontology):
        ont_uri = s
        break

    has_version_info = False
    version_string = None
    has_version_iri = False

    if ont_uri:
        # Check owl:versionInfo
        version_infos = list(graph.objects(ont_uri, OWL.versionInfo))
        if version_infos:
            has_version_info = True
            version_string = str(version_infos[0])

        # Check owl:versionIRI
        version_iris = list(graph.objects(ont_uri, OWL.versionIRI))
        has_version_iri = len(version_iris) > 0

    return has_version_info, version_string, has_version_iri


def count_deprecated_terms(graph: Graph) -> int:
    """Count terms marked with owl:deprecated true.

    Args:
        graph: RDF graph to analyze

    Returns:
        Count of deprecated terms
    """
    deprecated = list(graph.subjects(OWL.deprecated, URIRef("true")))
    # Also check for boolean literal True
    from rdflib import Literal
    deprecated += list(graph.subjects(OWL.deprecated, Literal(True)))
    return len(set(deprecated))


def detect_status(graph: Graph) -> Optional[str]:
    """Detect ontology status (bibo:status, vs:term_status).

    Args:
        graph: RDF graph to analyze

    Returns:
        Status string if found, None otherwise
    """
    # Find ontology URI
    ont_uri = None
    for s in graph.subjects(RDF.type, OWL.Ontology):
        ont_uri = s
        break

    if ont_uri:
        # Check bibo:status
        statuses = list(graph.objects(ont_uri, BIBO.status))
        if statuses:
            return str(statuses[0])

        # Check vs:term_status
        statuses = list(graph.objects(ont_uri, VS.term_status))
        if statuses:
            return str(statuses[0])

    return None


def detect_provenance_vocabs(graph: Graph) -> tuple[bool, bool, bool]:
    """Detect usage of PAV, PROV, and VANN provenance vocabularies.

    Args:
        graph: RDF graph to analyze

    Returns:
        Tuple of (uses_pav, uses_prov, uses_vann)
    """
    uses_pav = any("purl.org/pav" in str(s) or "purl.org/pav" in str(p)
                   for s, p, o in graph)
    uses_prov = any("www.w3.org/ns/prov" in str(s) or "www.w3.org/ns/prov" in str(p)
                    for s, p, o in graph)
    uses_vann = any("purl.org/vocab/vann" in str(s) or "purl.org/vocab/vann" in str(p)
                    for s, p, o in graph)

    return uses_pav, uses_prov, uses_vann


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

    # NEW: Detect Widoco metadata patterns
    imports_count, imported_ontologies = detect_imports(graph)
    has_version_info, version_string, has_version_iri = detect_version_info(graph)
    deprecated_count = count_deprecated_terms(graph)
    status = detect_status(graph)
    uses_pav, uses_prov, uses_vann = detect_provenance_vocabs(graph)

    return MetadataProfile(
        label_properties=label_props,
        description_properties=desc_props,
        uses_skos=uses_skos,
        uses_void=uses_void,
        uses_dcterms=uses_dcterms,
        uses_schema_org=uses_schema_org,
        uses_foaf=uses_foaf,
        skos_concept_count=len(skos_concepts),
        skos_scheme_count=len(skos_schemes),
        # NEW: Widoco metadata
        imports_count=imports_count,
        imported_ontologies=imported_ontologies,
        has_version_info=has_version_info,
        version_string=version_string,
        has_version_iri=has_version_iri,
        deprecated_term_count=deprecated_count,
        status_value=status,
        uses_pav=uses_pav,
        uses_prov=uses_prov,
        uses_vann=uses_vann
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
    """Format sense card as compact markdown (~600-700 chars with Widoco metadata).

    Focus on HOW to read the ontology: formalism level, metadata conventions,
    annotation properties to use for navigation, versioning, maturity, and dependencies.

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

    # NEW: Version and maturity indicators
    maturity_parts = []
    if card.metadata.has_version_info and card.metadata.version_string:
        maturity_parts.append(f"v{card.metadata.version_string}")
    if card.metadata.status_value:
        maturity_parts.append(f"status: {card.metadata.status_value}")
    if card.metadata.deprecated_term_count > 0:
        maturity_parts.append(f"{card.metadata.deprecated_term_count} deprecated terms")

    if maturity_parts:
        lines.append(f"**Maturity**: {', '.join(maturity_parts)}")

    # NEW: Imports/dependencies (highest priority for navigation)
    if card.metadata.imports_count > 0:
        import_summary = f"{card.metadata.imports_count} imported ontologies"
        if len(card.metadata.imported_ontologies) <= 3:
            import_names = ', '.join(card.metadata.imported_ontologies)
            import_summary = f"Imports: {import_names}"
        lines.append(f"**Dependencies**: {import_summary}")

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

    # NEW: Deprecation warning (if present)
    if card.metadata.deprecated_term_count > 0:
        lines.append(f"- ⚠️  Check `owl:deprecated` before using terms ({card.metadata.deprecated_term_count} marked)")

    return '\n'.join(lines)
