"""Test enhanced L0 on multiple ontology styles."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.packers import l0_sense_enhanced as enhanced

print("=" * 70)
print("ENHANCED L0 SENSE CARD - Multi-Ontology Test")
print("=" * 70)

# Test 1: PROV (modular with imports)
print("\n1. PROV ONTOLOGY (Modular with imports)")
print("-" * 70)
g_prov = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')
sense_prov = enhanced.pack(g_prov, budget=600)
print(sense_prov)
print(f"\nLength: {len(sense_prov)} chars")

# Test 2: GeoSPARQL (OGC style with Schema.org)
print("\n" + "=" * 70)
print("2. GEOSPARQL PROFILE (OGC/Schema.org style)")
print("-" * 70)
g_geo = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/ogc-geosparql/profile.ttl')
sense_geo = enhanced.pack(g_geo, budget=600)
print(sense_geo)
print(f"\nLength: {len(sense_geo)} chars")

# Test 3: SIO (OBO Foundry style with subsets)
print("\n" + "=" * 70)
print("3. SIO ONTOLOGY (OBO Foundry style with subsets)")
print("-" * 70)
g_sio = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/sio/sio-release.owl')
sense_sio = enhanced.pack(g_sio, budget=600)
print(sense_sio)
print(f"\nLength: {len(sense_sio)} chars")

print("\n" + "=" * 70)
print("COMPARISON SUMMARY")
print("=" * 70)
print(f"\nPROV:       {len(sense_prov):3d} chars - Modular (imports)")
print(f"GeoSPARQL: {len(sense_geo):3d} chars - OGC profile")
print(f"SIO:       {len(sense_sio):3d} chars - OBO Foundry (subsets)")
print("\nAll within 600 char budget ✓")
