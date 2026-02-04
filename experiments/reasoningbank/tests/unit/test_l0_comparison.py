"""Compare E5 sense card with ReasoningBank L0 sense card."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.packers import l0_sense

# Load PROV ontology
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

# Generate L0 sense card
sense_card = l0_sense.pack(g, budget=600)

print("=" * 70)
print("REASONINGBANK L0 SENSE CARD (Current)")
print("=" * 70)
print(sense_card)
print()
print("=" * 70)
print(f"Total length: {len(sense_card)} characters")
print("=" * 70)
print()
print()
print("=" * 70)
print("E5 SENSE CARD (Reference)")
print("=" * 70)
print("""UniProt Core Ontology: Defines the schema for UniProt protein knowledge base, including classes for proteins, genes, organisms, annotations, and their relationships

Core Classes: Protein, Gene, Taxon, Sequence, Molecule

Key Properties:
- organism: Connects a Protein to its Taxon (organism)
- encodedBy: Protein is encoded by Gene
- sequence: Connects Protein to its Sequence
- annotation: Connects entities to their annotations

Common Patterns: 2 templates available
- Find Proteins: Retrieve proteins with basic information
- Protein-Organism Relationship: Find organisms for proteins""")
print()
print("=" * 70)
print(f"Total length: 589 characters")
print("=" * 70)
