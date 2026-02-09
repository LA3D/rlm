"""Judge Working Memory - Format principles + episodes for judge context injection.

Dual-memory packing: semantic (principles) always included, episodic (cases) retrieved.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.core.mem import Item


def pack_working_memory(
    principles: list[Item],
    episodes: list[Item],
    budget: int = 3000,
) -> tuple[str, str]:
    """Format judge working memory for context injection.

    Returns two strings (principles_text, episodes_text) for separate
    injection into the AlignedTrajectoryJudge signature fields.

    Args:
        principles: All principles (semantic memory) - always included
        episodes: Retrieved episodes (episodic memory) - top-k relevant
        budget: Max characters per section

    Returns:
        Tuple of (principles_text, episodes_text)
    """
    # Principles section (semantic memory - always all)
    p_lines = []
    if principles:
        for i, p in enumerate(principles, 1):
            prefix = "[EXCEPTION - overrides general rules when applicable] " if getattr(p, 'scope', '') == 'exception' else ""
            p_lines.append(f"{i}. **{p.title}**: {prefix}{p.content}")
    principles_text = '\n\n'.join(p_lines)[:budget] if p_lines else "(no principles)"

    # Episodes section (episodic memory - retrieved)
    e_lines = []
    if episodes:
        for i, e in enumerate(episodes, 1):
            e_lines.append(f"Case {i}: **{e.title}**\n{e.content}")
    episodes_text = '\n\n'.join(e_lines)[:budget] if e_lines else "(no past cases)"

    return principles_text, episodes_text


def pack_combined(
    principles: list[Item],
    episodes: list[Item],
    budget: int = 3000,
) -> str:
    """Pack principles + episodes into a single working memory string.

    Useful for signatures that take a single context field.

    Args:
        principles: All principles (semantic memory)
        episodes: Retrieved episodes (episodic memory)
        budget: Max characters total

    Returns:
        Combined working memory string
    """
    parts = []

    if principles:
        parts.append("## Evaluation Principles\n")
        for i, p in enumerate(principles, 1):
            parts.append(f"{i}. **{p.title}**: {p.content}")

    if episodes:
        parts.append("\n## Relevant Past Cases\n")
        for i, e in enumerate(episodes, 1):
            parts.append(f"Case {i}: **{e.title}**\n{e.content}")

    return '\n\n'.join(parts)[:budget]
