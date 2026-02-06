"""Test query guard enforcement on a simple trajectory.

This script runs a single query with all enforcement layers enabled:
- Query guard (hard rejection)
- L0 endpoint scale warning
- L1 endpoint-aware anti-patterns
- L2 seed memories
- L3 UniProt guide

Compares behavior with guard enabled vs disabled.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import json
from pathlib import Path
from experiments.reasoningbank.prototype.run.rlm_uniprot import run_uniprot
from experiments.reasoningbank.prototype.ctx.builder import Cfg, Layer
from experiments.reasoningbank.prototype.core.mem import MemStore, Item

# Ensure API key is set
if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

# Load seed memories
seed_file = Path(__file__).parent / 'seed' / 'strategies.json'
with open(seed_file) as f:
    seeds = json.load(f)

mem = MemStore()
for s in seeds:
    mem.add(Item(
        id=s['id'], title=s['title'], desc=s['desc'],
        content=s['content'], src=s['src'], tags=s.get('tags', [])
    ))

# Load UniProt guide
guide_file = Path(__file__).parent / 'seed' / 'guides' / 'uniprot.md'
guide_text = guide_file.read_text()

# Task: bacteria taxa (Task 2 from experiments)
task = "List bacterial taxa (direct subclasses of taxon:2 'Bacteria'). Return their scientific names."

# Configuration with all layers enabled
cfg = Cfg(
    l0=Layer(on=True, budget=800),
    l1=Layer(on=True, budget=1500),
    l2=Layer(on=True, budget=2000),
    l3=Layer(on=True, budget=1000),
    guide_text=guide_text,
    endpoint_meta={
        'name': 'UniProt',
        'triple_count': 232_000_000_000,
        'has_text_index': False,
        'has_spo_index': False,
    }
)

ontology_path = '/Users/cvardema/dev/git/LA3D/rlm/ontology/uniprot'

print("=" * 80)
print("QUERY GUARD ENFORCEMENT TEST")
print("=" * 80)
print(f"Task: {task}")
print()
print("Configuration:")
print(f"  L0 (sense + endpoint scale): {cfg.l0.on}")
print(f"  L1 (schema + anti-patterns): {cfg.l1.on}")
print(f"  L2 (seed memories): {cfg.l2.on} ({len(seeds)} seeds)")
print(f"  L3 (UniProt guide): {cfg.l3.on}")
print(f"  Query guard: ENABLED (via V2 tools)")
print()

# Create output directory
output_dir = Path(__file__).parent / 'results' / 'guard_test'
output_dir.mkdir(parents=True, exist_ok=True)

# Run with V2 tools (guard enabled by default)
print("Running with V2 tools (guard enabled)...")
log_path = output_dir / 'guard_enabled.jsonl'
if log_path.exists():
    log_path.unlink()

result = run_uniprot(
    task=task,
    ont_path=ontology_path,
    cfg=cfg,
    mem=mem,
    endpoint='uniprot',
    max_iters=8,
    temperature=0.0,
    verbose=True,
    log_path=str(log_path),
    use_local_interpreter=True,
    use_v2_tools=True,
    rollout_id=1,
)

print()
print("=" * 80)
print("RESULTS")
print("=" * 80)
print(f"Converged: {result.converged}")
print(f"Iterations: {result.iters}")
print(f"Answer length: {len(result.answer)} chars")
print(f"SPARQL: {result.sparql[:200] if result.sparql else 'None'}...")
print()

# Analyze trajectory for guard rejections and tool failures
with open(log_path) as f:
    events = [json.loads(line) for line in f]

print("Trajectory Analysis:")
print(f"  Total events: {len(events)}")

# Count event types
event_counts = {}
for e in events:
    event_type = e.get('event_type', 'unknown')
    event_counts[event_type] = event_counts.get(event_type, 0) + 1

for event_type, count in sorted(event_counts.items()):
    print(f"  {event_type}: {count}")

# Check for guard rejections
guard_rejections = [e for e in events if e.get('event_type') == 'tool_result'
                    and isinstance(e.get('data', {}).get('result'), dict)
                    and 'Query rejected' in str(e.get('data', {}).get('result', {}).get('error', ''))]

if guard_rejections:
    print(f"\n  Guard rejections: {len(guard_rejections)}")
    for i, e in enumerate(guard_rejections[:3], 1):
        result_data = e['data']['result']
        print(f"    #{i}: {result_data.get('pattern', 'unknown')}")
        print(f"        {result_data.get('error', '')[:100]}...")

# Check for timeouts
timeouts = [e for e in events if 'timeout' in str(e.get('data', {})).lower()
            or 'timed out' in str(e.get('data', {})).lower()]

if timeouts:
    print(f"\n  Timeouts: {len(timeouts)}")
    for i, e in enumerate(timeouts[:2], 1):
        print(f"    #{i}: {e.get('event_type', '?')} - {str(e.get('data', {}))[:100]}...")
else:
    print(f"\n  Timeouts: 0 (SUCCESS)")

print()
print(f"Full trajectory: {log_path}")
print()
print("=" * 80)
