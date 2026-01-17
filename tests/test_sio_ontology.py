"""Test ontology module with SIO (Semanticscience Integrated Ontology)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.ontology import setup_ontology_context, ont_describe, ont_meta, ont_roots

# Setup namespace with SIO ontology (much larger than PROV)
ns = {}
setup_msg = setup_ontology_context('ontology/sio/sio-release.owl', ns, name='sio')
print(f"Setup: {setup_msg}")
print()

# Check meta structure
meta = ns['sio_meta']
print(f"SIO Ontology Structure:")
print(f"  Triple count: {meta.triple_count:,}")
print(f"  Classes: {len(meta.classes)}")
print(f"  Properties: {len(meta.properties)}")
print(f"  Individuals: {len(meta.individuals)}")
print(f"  Labels: {len(meta.labels)}")
print(f"  Inverted label index: {len(meta.by_label)} unique labels")
print(f"  Subclass relationships: {len(meta.subs)} superclasses with subclasses")
print(f"  Property domains: {len(meta.doms)}")
print(f"  Property ranges: {len(meta.rngs)}")
print()

# Test by_label search
measurement_uris = meta.by_label.get('measurement', [])
print(f"URIs with label 'measurement': {len(measurement_uris)}")
if measurement_uris:
    print(f"  First: {measurement_uris[0]}")
print()

# Test ont_roots
ont_roots('sio_meta', name='sio_roots', ns=ns)
print(f"Root classes: {len(ns['sio_roots'])}")
print(f"  Sample roots: {ns['sio_roots'][:3]}")
print()

# Test ont_meta
ont_meta('sio_meta', name='sio_metadata', ns=ns)
print(f"Metadata: {len(ns['sio_metadata'].prefixes)} prefixes, {len(ns['sio_metadata'].imports)} imports")
print()

# Test ont_describe with a specific SIO class
if measurement_uris:
    ont_describe('sio_meta', measurement_uris[0], name='measurement_desc', ns=ns)
    desc = ns['measurement_desc']
    print(f"Description of {measurement_uris[0]}:")
    print(f"  Subject triples: {len(desc['as_subject'])}")
    print(f"  Object triples: {len(desc['as_object'])}")

    # Show sample of subject triples
    if desc['as_subject']:
        print(f"  Sample subject triple:")
        s, p, o = desc['as_subject'][0]
        print(f"    {p}: {o[:80]}...")
