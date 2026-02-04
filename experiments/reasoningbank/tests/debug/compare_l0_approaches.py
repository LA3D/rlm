"""Compare current vs enhanced L0 with metadata."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.packers import l0_sense

# Load PROV
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

# Current L0
current_l0 = l0_sense.pack(g, budget=600)

print("=" * 70)
print("CURRENT L0 (137 chars)")
print("=" * 70)
print(current_l0)
print()

print("=" * 70)
print("ENHANCED L0 WITH IMPORTS/NAMESPACES (220 chars)")
print("=" * 70)
print("""**Size**: 1664 triples, 59 classes, 60 properties
**Namespaces**: `brick`, `csvw`, `dc`, `dcat`, `dcmitype`
**Imports**: prov-aq, prov-dc, prov-dictionary, prov-links, prov-o, prov-o-inverses
**Labels**: use `rdfs:label`""")
print()

print("=" * 70)
print("KEY DIFFERENCES")
print("=" * 70)
print()
print("ADDED in Enhanced:")
print("  + Namespaces: Shows available prefixes for queries")
print("  + Imports: Critical for understanding modular ontologies")
print()
print("REMOVED in Enhanced:")
print("  - Formalism: OWL-DL level less relevant for SPARQL")
print("  - Description property: Can add back if needed")
print()
print("SIZE IMPACT:")
print(f"  Current: 137 chars (23% of budget)")
print(f"  Enhanced: 220 chars (37% of budget)")
print(f"  Increase: +83 chars (+60%)")
print()
print("=" * 70)
print("RECOMMENDATION")
print("=" * 70)
print()
print("Enhanced L0 should include:")
print("  1. Size stats (triples, classes, properties)")
print("  2. Key namespaces (excluding standard RDF/OWL/XSD)")
print("  3. Imports (critical for modular ontologies like PROV)")
print("  4. Label/description conventions")
print()
print("Enhanced L0 should SKIP:")
print("  - Title/description (ontologies often lack these)")
print("  - Creators/contributors (not query-relevant)")
print("  - License (not query-relevant)")
print("  - Version (useful for docs, not queries)")
print()
print("This keeps L0 focused on query construction needs while")
print("capturing critical structural information (imports, namespaces).")
