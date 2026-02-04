"""Debug script to see which L2 memories are retrieved for UniProt tasks."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from pathlib import Path
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.packers import l2_mem
import json

# Load seed memories
mem = MemStore()
seed_path = 'experiments/reasoningbank/seed/strategies.json'
mem.load(seed_path)

print(f"Loaded {len(mem.all())} seed strategies\n")

# UniProt test tasks
tasks = [
    {"id": "protein_lookup", "query": "What is a Protein in the UniProt ontology?"},
    {"id": "protein_properties", "query": "What properties does the Protein class have in UniProt?"},
    {"id": "annotation_types", "query": "What are the different types of Annotations in UniProt?"},
]

for t in tasks:
    print(f"{'='*70}")
    print(f"Task: {t['id']}")
    print(f"Query: {t['query']}")
    print(f"{'='*70}\n")

    # Retrieve memories (same as rlm_uniprot.py)
    k_success, k_failure = 2, 1
    success_hits = mem.search(t['query'], k=k_success, polarity='success')
    failure_hits = mem.search(t['query'], k=k_failure, polarity='failure')
    seed_hits = mem.search(t['query'], k=1, polarity='seed')

    print(f"Success memories retrieved: {len(success_hits)}")
    for hit in success_hits:
        print(f"  - {hit['id']}: {hit['title']} (score: {hit.get('score', 'N/A')})")

    print(f"\nFailure memories retrieved: {len(failure_hits)}")
    for hit in failure_hits:
        print(f"  - {hit['id']}: {hit['title']} (score: {hit.get('score', 'N/A')})")

    print(f"\nSeed memories retrieved: {len(seed_hits)}")
    for hit in seed_hits:
        print(f"  - {hit['id']}: {hit['title']} (score: {hit.get('score', 'N/A')})")

    # Get full items and pack
    all_ids = [h['id'] for h in success_hits + failure_hits + seed_hits]
    if all_ids:
        items = mem.get(all_ids, max_n=len(all_ids))
        mem_text = l2_mem.pack(items, budget=2000)
        print(f"\nPacked memory context ({len(mem_text)} chars):")
        print("-" * 70)
        print(mem_text)
        print("-" * 70)

    print("\n")
