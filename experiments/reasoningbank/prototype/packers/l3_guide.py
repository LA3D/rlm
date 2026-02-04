"""L3 Guide Compression - Compress materialized guides to summaries.

E4-style: A full ontology guide (expensive to create) is compressed to
~1000 chars for repeated use. Amortizes creation cost over many queries.
"""

def pack(guide:str, budget:int=1000) -> str:
    "Compress guide to summary (extractive)."
    # Simple: take first `budget` chars, break at sentence
    if len(guide) <= budget: return guide
    cut = guide[:budget]
    # Find last sentence boundary
    for end in ['. ', '.\n', '! ', '? ']:
        i = cut.rfind(end)
        if i > budget//2: return cut[:i+1]
    return cut
