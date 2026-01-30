"""L2 Procedural Memory - Format retrieved memories for context injection.

Strategies: Include k_success + k_failure, truncate to budget.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.core.mem import Item

def pack(items:list[Item], budget:int=2000) -> str:
    "Format memories for context injection."
    lines = ['**Relevant Procedures**:']
    for o in items:
        lines.append(f"\n### {o.title}")
        lines.append(o.content)
    return '\n'.join(lines)[:budget]
