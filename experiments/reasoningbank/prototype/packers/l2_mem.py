"""L2 Procedural Memory - Format retrieved memories for context injection.

Separates success strategies from failure guardrails for clarity.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.core.mem import Item

def pack(items:list[Item], budget:int=2000) -> str:
    "Format memories with success/failure separation."
    success = [o for o in items if o.src == 'success']
    failure = [o for o in items if o.src == 'failure']
    seed = [o for o in items if o.src == 'seed']

    lines = []

    # Success strategies first (what to do)
    if success:
        lines.append('**Strategies** (what works):')
        for o in success:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    # Failure guardrails (what to avoid)
    if failure:
        lines.append('\n**Guardrails** (what to avoid):')
        for o in failure:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    # Seed items (general strategies)
    if seed:
        lines.append('\n**General Strategies**:')
        for o in seed:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    return '\n'.join(lines)[:budget]


def pack_separate(success:list[Item], failure:list[Item], budget:int=2000) -> str:
    "Pack pre-separated success/failure lists (for explicit k_success + k_failure retrieval)."
    lines = []

    if success:
        lines.append('**Strategies** (what works):')
        for o in success:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    if failure:
        lines.append('\n**Guardrails** (what to avoid):')
        for o in failure:
            lines.append(f"\n• **{o.title}**")
            lines.append(o.content)

    return '\n'.join(lines)[:budget]
