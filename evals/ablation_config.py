"""Ablation configuration for sense card feature experiments.

Enables systematic testing of which ontology affordances improve query construction.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AblationConfig:
    """Configuration for sense card feature ablation experiments.

    Controls which features are included in sense cards to measure their
    impact on query construction success rates.
    """

    name: str
    description: str

    # Basic features (always included in some form)
    basic_stats: bool = True  # Triple/class/property counts

    # Labeling and annotation metadata
    labeling_predicates: bool = False  # rdfs:label, skos:prefLabel, etc.
    description_predicates: bool = False  # rdfs:comment, skos:definition, etc.

    # Structural information
    hierarchy: bool = False  # rdfs:subClassOf relationships
    domain_range: bool = False  # rdfs:domain, rdfs:range

    # Semantic richness
    property_characteristics: bool = False  # Transitive, symmetric, functional
    materialization_hints: bool = False  # Whether hierarchies are materialized
    owl_constructs: bool = False  # Restrictions, unions, disjoints

    # Query construction guidance
    sparql_templates: bool = False  # Example query templates
    uri_patterns: bool = False  # URI structure examples

    # Memory integration
    enable_memory: bool = False  # ReasoningBank closed-loop
    memory_retrieval_k: int = 3  # Number of memories to retrieve

    @classmethod
    def from_preset(cls, preset_name: str) -> 'AblationConfig':
        """Create config from preset name.

        Available presets:
        - baseline: Only basic stats (minimal context)
        - minimal: + labeling predicates
        - structural: + domain_range, hierarchy
        - semantic: + property_characteristics, materialization_hints
        - full: All features except memory
        - full_with_memory: All features + memory

        Args:
            preset_name: Name of preset configuration

        Returns:
            AblationConfig instance

        Raises:
            ValueError: If preset name not recognized
        """
        presets = {
            'baseline': cls(
                name='baseline',
                description='Minimal context: basic stats only',
                basic_stats=True
            ),
            'minimal': cls(
                name='minimal',
                description='Basic + labeling predicates',
                basic_stats=True,
                labeling_predicates=True
            ),
            'structural': cls(
                name='structural',
                description='Minimal + structural information',
                basic_stats=True,
                labeling_predicates=True,
                hierarchy=True,
                domain_range=True
            ),
            'semantic': cls(
                name='semantic',
                description='Structural + semantic richness',
                basic_stats=True,
                labeling_predicates=True,
                description_predicates=True,
                hierarchy=True,
                domain_range=True,
                property_characteristics=True,
                materialization_hints=True,
                owl_constructs=True
            ),
            'full': cls(
                name='full',
                description='All sense card features',
                basic_stats=True,
                labeling_predicates=True,
                description_predicates=True,
                hierarchy=True,
                domain_range=True,
                property_characteristics=True,
                materialization_hints=True,
                owl_constructs=True,
                sparql_templates=True,
                uri_patterns=True
            ),
            'full_with_memory': cls(
                name='full_with_memory',
                description='Full features + ReasoningBank memory',
                basic_stats=True,
                labeling_predicates=True,
                description_predicates=True,
                hierarchy=True,
                domain_range=True,
                property_characteristics=True,
                materialization_hints=True,
                owl_constructs=True,
                sparql_templates=True,
                uri_patterns=True,
                enable_memory=True,
                memory_retrieval_k=3
            )
        }

        if preset_name not in presets:
            available = ', '.join(presets.keys())
            raise ValueError(f"Unknown preset '{preset_name}'. Available: {available}")

        return presets[preset_name]

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'features': {
                'basic_stats': self.basic_stats,
                'labeling_predicates': self.labeling_predicates,
                'description_predicates': self.description_predicates,
                'hierarchy': self.hierarchy,
                'domain_range': self.domain_range,
                'property_characteristics': self.property_characteristics,
                'materialization_hints': self.materialization_hints,
                'owl_constructs': self.owl_constructs,
                'sparql_templates': self.sparql_templates,
                'uri_patterns': self.uri_patterns
            },
            'memory': {
                'enabled': self.enable_memory,
                'retrieval_k': self.memory_retrieval_k
            }
        }

    def get_enabled_features(self) -> list[str]:
        """Get list of enabled feature names."""
        features = []
        if self.basic_stats:
            features.append('basic_stats')
        if self.labeling_predicates:
            features.append('labeling_predicates')
        if self.description_predicates:
            features.append('description_predicates')
        if self.hierarchy:
            features.append('hierarchy')
        if self.domain_range:
            features.append('domain_range')
        if self.property_characteristics:
            features.append('property_characteristics')
        if self.materialization_hints:
            features.append('materialization_hints')
        if self.owl_constructs:
            features.append('owl_constructs')
        if self.sparql_templates:
            features.append('sparql_templates')
        if self.uri_patterns:
            features.append('uri_patterns')
        return features
