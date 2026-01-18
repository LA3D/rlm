#!/usr/bin/env python3
"""Test build_sense() with real LLM API call.

Requires ANTHROPIC_API_KEY environment variable.

Usage:
    python test_build_sense.py
"""

from rlm.ontology import build_sense

def main():
    print("="*70)
    print(" Testing build_sense() with PROV Ontology")
    print("="*70)
    print()

    ns = {}
    result = build_sense('ontology/prov.ttl', name='prov_sense', ns=ns)

    print(result)
    print()

    # Inspect the sense document
    sense = ns['prov_sense']

    print("="*70)
    print(" Sense Document Structure")
    print("="*70)
    print(f"Ontology: {sense.ont}")
    print(f"Ontology Metadata: {sense.ont_metadata}")
    print(f"Stats: {sense.stats}")
    print()

    print("="*70)
    print(" Detected Annotation Properties")
    print("="*70)
    print(f"Label properties: {sense.label_properties}")
    print(f"Description properties: {sense.description_properties}")
    print()

    print("="*70)
    print(" Structure")
    print("="*70)
    print(f"Roots: {sense.roots}")
    print(f"Root branches: {list(sense.hier.keys())}")
    print(f"Top properties (first 3): {sense.top_props[:3]}")
    print()

    print("="*70)
    print(" OWL Features Detected")
    print("="*70)
    print(f"Property characteristics: {sense.prop_chars}")
    print(f"OWL constructs: {sense.owl_constructs}")
    print(f"URI pattern: {sense.uri_pattern}")
    print()

    print("="*70)
    print(" LLM-Generated Summary")
    print("="*70)
    print(sense.summary)
    print()

    print("="*70)
    print(" ✓ SUCCESS: build_sense() works with real LLM!")
    print("="*70)

    return True


if __name__ == '__main__':
    import sys
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
