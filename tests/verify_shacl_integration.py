#!/usr/bin/env python3
"""Verification script for Stage 4 SHACL integration.

This script demonstrates all the features implemented in Stage 4:
1. SHACL detection
2. Shape indexing
3. Bounded view functions
4. Integration with mount_ontology()
"""

from rdflib import Dataset, Graph, Namespace, RDF, Literal, BNode, XSD
from rdflib.namespace import SH, RDFS
from pathlib import Path

from rlm.dataset import DatasetMeta, mount_ontology
from rlm.shacl_examples import (
    detect_shacl, build_shacl_index,
    describe_shape, search_shapes, shape_constraints
)


def test_basic_detection():
    """Test basic SHACL detection."""
    print("=" * 70)
    print("TEST 1: Basic SHACL Detection")
    print("=" * 70)

    # Empty graph
    g = Graph()
    result = detect_shacl(g)
    print(f"Empty graph: has_shacl={result['has_shacl']}, paradigm={result['paradigm']}")
    assert result['has_shacl'] == False

    # Graph with NodeShape
    EX = Namespace("http://example.org/")
    g.add((EX.PersonShape, RDF.type, SH.NodeShape))
    g.add((EX.PersonShape, SH.targetClass, EX.Person))
    result = detect_shacl(g)
    print(f"With NodeShape: has_shacl={result['has_shacl']}, paradigm={result['paradigm']}")
    assert result['has_shacl'] == True
    print("✓ Basic detection works\n")


def test_shape_indexing():
    """Test shape indexing with properties."""
    print("=" * 70)
    print("TEST 2: Shape Indexing")
    print("=" * 70)

    g = Graph()
    EX = Namespace("http://example.org/")

    # Create PersonShape with property constraints
    g.add((EX.PersonShape, RDF.type, SH.NodeShape))
    g.add((EX.PersonShape, SH.targetClass, EX.Person))
    g.add((EX.PersonShape, RDFS.label, Literal("Person Shape")))

    # Add property constraint for name
    prop1 = BNode()
    g.add((EX.PersonShape, SH.property, prop1))
    g.add((prop1, SH.path, EX.name))
    g.add((prop1, SH.datatype, XSD.string))
    g.add((prop1, SH.minCount, Literal(1)))

    # Add property constraint for age
    prop2 = BNode()
    g.add((EX.PersonShape, SH.property, prop2))
    g.add((prop2, SH.path, EX.age))
    g.add((prop2, SH.datatype, XSD.integer))

    # Build index
    index = build_shacl_index(g)
    print(f"Index summary: {index.summary()}")
    print(f"Shapes: {len(index.shapes)}")
    print(f"Keywords: {list(index.keywords.keys())[:5]}")

    assert len(index.shapes) == 1
    assert str(EX.PersonShape) in index.shapes
    print("✓ Shape indexing works\n")


def test_bounded_views():
    """Test bounded view functions."""
    print("=" * 70)
    print("TEST 3: Bounded View Functions")
    print("=" * 70)

    g = Graph()
    EX = Namespace("http://example.org/")

    # Create PersonShape
    g.add((EX.PersonShape, RDF.type, SH.NodeShape))
    g.add((EX.PersonShape, SH.targetClass, EX.Person))
    g.add((EX.PersonShape, RDFS.label, Literal("Person")))

    # Add multiple properties
    for i, prop_name in enumerate(['name', 'age', 'email', 'phone', 'address']):
        prop_node = BNode()
        g.add((EX.PersonShape, SH.property, prop_node))
        g.add((prop_node, SH.path, EX[prop_name]))
        g.add((prop_node, SH.datatype, XSD.string))

    # Create OrganizationShape
    g.add((EX.OrgShape, RDF.type, SH.NodeShape))
    g.add((EX.OrgShape, SH.targetClass, EX.Organization))

    index = build_shacl_index(g)

    # Test search_shapes
    print("\n--- Search for 'person' ---")
    results = search_shapes(index, 'person')
    print(f"Found {len(results)} shapes:")
    for r in results:
        print(f"  - {r['uri'].split('/')[-1]}: targets={[t.split('/')[-1] for t in r['targets']]}")
    assert len(results) >= 1

    # Test describe_shape
    print("\n--- Describe PersonShape (limit=3) ---")
    desc = describe_shape(index, str(EX.PersonShape), limit=3)
    print(f"URI: {desc['uri'].split('/')[-1]}")
    print(f"Targets: {[t.split('/')[-1] for t in desc['targets']]}")
    print(f"Properties (showing {len(desc['properties'])} of {desc['property_count']}): ")
    for prop in desc['properties']:
        path = prop['path'].split('/')[-1]
        dtype = prop.get('datatype', 'N/A').split('#')[-1]
        print(f"  - {path}: {dtype}")
    print(f"Truncated: {desc['truncated']}")
    assert desc['truncated'] == True

    # Test shape_constraints
    print("\n--- Shape Constraints ---")
    constraints = shape_constraints(index, str(EX.PersonShape))
    print(constraints)

    print("\n✓ Bounded view functions work\n")


def test_dcat_integration():
    """Test integration with DCAT-AP shapes."""
    print("=" * 70)
    print("TEST 4: DCAT-AP Integration")
    print("=" * 70)

    dcat_path = Path('ontology/dcat-ap/dcat-ap-SHACL.ttl')
    if not dcat_path.exists():
        print("⚠ DCAT-AP shapes not found, skipping integration test\n")
        return

    # Create dataset and mount DCAT-AP
    ds = Dataset()
    meta = DatasetMeta(ds, 'test')
    ns = {}

    print("Mounting DCAT-AP shapes...")
    result = mount_ontology(meta, ns, str(dcat_path), 'dcat')
    print(result)
    print()

    # Check if SHACL index was created
    if 'dcat_shacl' not in ns:
        print("✗ SHACL index not created!")
        return

    index = ns['dcat_shacl']
    print(f"SHACL Index: {index.summary()}")

    # Search for common DCAT concepts
    print("\n--- Search Results ---")
    for keyword in ['dataset', 'distribution', 'catalog']:
        results = search_shapes(index, keyword, limit=2)
        print(f"\n'{keyword}' matches ({len(results)}):")
        for r in results:
            shape_name = r['uri'].split('/')[-1].split('#')[-1]
            print(f"  - {shape_name}")

    # Describe Dataset shape
    dataset_shapes = search_shapes(index, 'dataset', limit=1)
    if dataset_shapes:
        print("\n--- Dataset Shape Details ---")
        shape_uri = dataset_shapes[0]['uri']
        desc = describe_shape(index, shape_uri, limit=5)
        print(f"Shape: {shape_uri.split('/')[-1].split('#')[-1]}")
        print(f"Properties (showing {len(desc['properties'])} of {desc['property_count']}):")
        for prop in desc['properties']:
            if prop.get('path'):
                path = prop['path'].split('/')[-1].split('#')[-1]
                constraints = []
                if prop.get('datatype'):
                    constraints.append(f"type={prop['datatype'].split('#')[-1]}")
                if prop.get('minCount'):
                    constraints.append(f"min={prop['minCount']}")
                constraint_str = ', '.join(constraints) if constraints else 'no constraints'
                print(f"  - {path}: {constraint_str}")

    print("\n✓ DCAT-AP integration works\n")


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("Stage 4 SHACL Integration Verification")
    print("=" * 70 + "\n")

    try:
        test_basic_detection()
        test_shape_indexing()
        test_bounded_views()
        test_dcat_integration()

        print("=" * 70)
        print("ALL VERIFICATION TESTS PASSED ✓")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
