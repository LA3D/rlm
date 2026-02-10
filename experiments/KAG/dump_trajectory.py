#!/usr/bin/env python3
"""KAG trajectory dump utility.

Reads a trajectory JSONL (or run directory) and produces a structured
markdown report showing how the agent constructs the document graph.

Usage:
    python experiments/KAG/dump_trajectory.py <trajectory.jsonl or run_dir>
    python experiments/KAG/dump_trajectory.py <path> -o report.md
"""

import json, sys, argparse
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

# ── IRI shortening ───────────────────────────────────────────────────

PREFIXES = [
    ("http://la3d.local/kag/doc/", "ex:"),
    ("http://la3d.local/kag#", "kag:"),
    ("http://purl.org/spar/doco/", "doco:"),
    ("http://purl.org/spar/deo/", "deo:"),
    ("http://www.w3.org/2001/XMLSchema#", "xsd:"),
    ("http://www.w3.org/ns/shacl#", "sh:"),
]

def shorten(iri: str) -> str:
    """Shorten an IRI using known prefixes."""
    for base, prefix in PREFIXES:
        if iri.startswith(base):
            return prefix + iri[len(base):]
    return iri


# ── Event loading ────────────────────────────────────────────────────

def load_events(path: Path) -> list[dict]:
    """Load JSONL events from a trajectory file."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events

def load_summary(path: Path) -> dict | None:
    """Load summary.json if it exists."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


# ── Extraction functions ─────────────────────────────────────────────

def extract_run_meta(events: list[dict], summary: dict | None) -> dict:
    """Extract run metadata from run_start event and summary."""
    meta = {}
    for ev in events:
        if ev.get("event_type") == "run_start":
            meta.update(ev["data"])
            meta["timestamp"] = ev.get("timestamp", "")
            break
    if summary:
        meta["summary"] = summary
    return meta

def extract_l0_sense(events: list[dict]) -> dict | None:
    """Extract L0 sense result from ocr_sense tool_result."""
    for ev in events:
        if (ev.get("event_type") == "tool_result"
                and ev["data"].get("tool") == "ocr_sense"):
            preview = ev["data"].get("result_preview", "")
            try:
                return eval(preview)  # safe: dict literal from our own code
            except Exception:
                return {"raw": preview}
    return None

def extract_node_creations(events: list[dict]) -> list[dict]:
    """Group op_assert_type + subsequent op_set_single_literal calls into node records.

    Walks tool_call events in order. Each op_assert_type starts a new node.
    Subsequent op_set_single_literal calls targeting the same subject accumulate
    properties on that node, until a different subject or a non-literal op appears.
    """
    nodes = []
    current_node = None
    current_subject = None

    for ev in events:
        if ev.get("event_type") != "tool_call":
            continue
        data = ev["data"]
        tool = data.get("tool", "")
        args = data.get("args", [])

        if tool == "op_assert_type" and len(args) >= 2:
            # Flush previous node
            if current_node:
                nodes.append(current_node)
            current_subject = args[0]
            current_node = {
                "iri": current_subject,
                "type": shorten(args[1]),
                "props": {},
            }

        elif tool == "op_set_single_literal" and len(args) >= 3:
            subject, predicate, value = args[0], args[1], args[2]
            if current_node and subject == current_subject:
                prop_name = shorten(predicate)
                current_node["props"][prop_name] = value
            # If subject differs, this is a property set on a node we already
            # closed — skip attaching (rare in baseline runs).

    # Flush last node
    if current_node:
        nodes.append(current_node)

    return nodes

def extract_links(events: list[dict]) -> list[dict]:
    """Extract all op_add_iri_link tool_call events."""
    links = []
    for ev in events:
        if (ev.get("event_type") == "tool_call"
                and ev["data"].get("tool") == "op_add_iri_link"):
            args = ev["data"].get("args", [])
            if len(args) >= 3:
                links.append({
                    "subject": args[0],
                    "predicate": args[1],
                    "object": args[2],
                })
    return links

def build_section_tree(links: list[dict]) -> dict:
    """Build section tree from contains/containsAsHeader links.

    Returns {parent_iri: {"children": [child_iri, ...], "header": header_iri | None}}.
    """
    tree = defaultdict(lambda: {"children": [], "header": None})
    for lnk in links:
        pred = lnk["predicate"]
        if pred.endswith("#contains"):
            tree[lnk["subject"]]["children"].append(lnk["object"])
        elif pred.endswith("#containsAsHeader"):
            tree[lnk["subject"]]["header"] = lnk["object"]
    return dict(tree)

def extract_caption_links(links: list[dict]) -> list[dict]:
    """Filter links to kag:describes (caption→visual)."""
    out = []
    for lnk in links:
        if lnk["predicate"].endswith("#describes"):
            out.append({
                "caption": shorten(lnk["subject"]),
                "target": shorten(lnk["object"]),
            })
    return out

def extract_op_stats(events: list[dict]) -> Counter:
    """Count tool calls by tool name."""
    c = Counter()
    for ev in events:
        if ev.get("event_type") == "tool_call":
            c[ev["data"].get("tool", "unknown")] += 1
    return c

def extract_validation(events: list[dict], summary: dict | None) -> dict:
    """Extract validation results from validate_graph/finalize_graph tool_result or summary."""
    # Try summary first (richer data)
    if summary and "validation" in summary:
        return summary["validation"]
    # Fall back to tool_result (check both validate_graph and finalize_graph)
    for ev in events:
        if (ev.get("event_type") == "tool_result"
                and ev["data"].get("tool") in ("validate_graph", "finalize_graph")):
            preview = ev["data"].get("result_preview", "")
            try:
                return eval(preview)
            except Exception:
                return {"raw": preview}
    return {}

def extract_leakage(events: list[dict], summary: dict | None) -> dict:
    """Extract leakage metrics."""
    if summary and "leakage" in summary:
        return summary["leakage"]
    # Compute from run_complete
    for ev in events:
        if ev.get("event_type") == "run_complete":
            d = ev["data"]
            return {
                "large_returns": d.get("large_returns", 0),
                "triples": d.get("triples", 0),
            }
    return {}

def extract_rlm_iterations(events: list[dict]) -> list[dict]:
    """Extract RLM iteration events (have iteration number + reasoning/code)."""
    iters = []
    for ev in events:
        if ev.get("event_type") == "iteration":
            data = ev["data"]
            if "iteration" in data:  # RLM iteration (has iteration number)
                iters.append({
                    "iteration": data["iteration"],
                    "reasoning": data.get("reasoning", ""),
                    "code": data.get("code", ""),
                })
    return iters


# ── Markdown rendering ───────────────────────────────────────────────

def render_markdown(meta: dict, l0: dict | None, nodes: list[dict],
                    section_tree: dict, caption_links: list[dict],
                    op_stats: Counter, validation: dict,
                    leakage: dict, rlm_iters: list[dict],
                    node_lookup: dict[str, dict]) -> str:
    """Render the full markdown report."""
    lines = []
    w = lines.append

    # ── 1. Run Metadata ──
    w("# KAG Trajectory Report\n")
    w(f"**Run ID:** `{meta.get('run_id', '?')}`  ")
    w(f"**OCR Dir:** `{meta.get('ocr_dir', '?')}`  ")
    if meta.get("timestamp"):
        w(f"**Timestamp:** {meta['timestamp']}  ")
    if meta.get("model"):
        w(f"**Model:** `{meta['model']}`  ")
    if meta.get("sub_model"):
        w(f"**Sub-model:** `{meta['sub_model']}`  ")
    if meta.get("max_iters"):
        w(f"**Max iterations:** {meta['max_iters']}  ")
    w("")

    # ── 2. L0 Sense ──
    if l0:
        w("## L0 Sense\n")
        w(f"- **Pages:** {l0.get('page_count', '?')}")
        w(f"- **Total blocks:** {l0.get('block_count', '?')}")
        if l0.get("has_equations"):
            w("- **Has equations:** yes")
        counts = l0.get("counts_by_label", {})
        if counts:
            w(f"- **Blocks by label:** {', '.join(f'{k}: {v}' for k, v in sorted(counts.items(), key=lambda x: -x[1]))}")
        # Inferred type from summary
        summary = meta.get("summary", {})
        if summary.get("l0", {}).get("inferred_type"):
            w(f"- **Inferred type:** {summary['l0']['inferred_type']}")
        w("")

    # ── 3. Graph Construction Timeline ──
    w("## Graph Construction Timeline\n")
    w(f"**{len(nodes)} nodes created**\n")
    w("| # | Node | Type | Page | Label | Text (truncated) |")
    w("|---|------|------|------|-------|-------------------|")
    for i, nd in enumerate(nodes, 1):
        name = shorten(nd["iri"])
        typ = nd["type"]
        page = nd["props"].get("kag:pageNumber", "")
        label = nd["props"].get("kag:detectionLabel", "")
        text = nd["props"].get("kag:mainText", "")
        # Truncate text for table readability
        if len(text) > 60:
            text = text[:57] + "..."
        # Escape pipes in text
        text = text.replace("|", "\\|")
        w(f"| {i} | `{name}` | {typ} | {page} | {label} | {text} |")
    w("")

    # ── 4. Section Structure ──
    w("## Section Structure\n")
    # Find document root(s) — nodes with type doco:Document
    doc_roots = [nd["iri"] for nd in nodes if nd["type"] == "doco:Document"]
    if not doc_roots:
        # Fall back to any IRI that has children but is not a child itself
        all_children = set()
        for info in section_tree.values():
            all_children.update(info["children"])
        doc_roots = [iri for iri in section_tree if iri not in all_children]

    def render_tree(iri: str, indent: int = 0) -> None:
        info = section_tree.get(iri, {"children": [], "header": None})
        short = shorten(iri)
        # Get type from node_lookup
        nd = node_lookup.get(iri, {})
        typ = nd.get("type", "")
        header_text = ""
        if info["header"]:
            hnd = node_lookup.get(info["header"], {})
            header_text = hnd.get("props", {}).get("kag:mainText", "")
            if header_text:
                header_text = f' — "{header_text}"'
        prefix = "  " * indent + "- "
        type_badge = f" [{typ}]" if typ else ""
        w(f"{prefix}`{short}`{type_badge}{header_text}")
        for child in info["children"]:
            render_tree(child, indent + 1)

    for root in doc_roots:
        render_tree(root)
    w("")

    # ── 5. Caption Linking Summary ──
    if caption_links:
        w("## Caption Linking\n")
        w("| Caption | Describes | Target Type |")
        w("|---------|-----------|-------------|")
        for cl in caption_links:
            # Infer target type from IRI suffix
            target = cl["target"]
            if "figure_" in target:
                ttype = "Figure"
            elif "table_" in target:
                ttype = "Table"
            else:
                ttype = "Other"
            w(f"| `{cl['caption']}` | `{cl['target']}` | {ttype} |")
        w("")

    # ── 6. Operator Statistics ──
    w("## Operator Statistics\n")
    w("| Operator | Count |")
    w("|----------|-------|")
    for tool, count in op_stats.most_common():
        w(f"| `{tool}` | {count} |")
    w(f"\n**Total tool calls:** {sum(op_stats.values())}\n")

    # ── 7. Validation Result ──
    w("## Validation Result\n")
    conforms = validation.get("conforms", "?")
    w(f"- **Conforms:** {conforms}")
    vr = validation.get("total_violations", validation.get("validation_results", 0))
    w(f"- **Violation count:** {vr}")
    # New format: actionable violations list
    violations = validation.get("violations", [])
    if violations:
        w("- **Violations:**")
        for v in violations[:10]:
            node = shorten(v.get("node", ""))
            ntype = v.get("node_type", "?")
            msg = v.get("message", "")
            w(f"  - `{node}` ({ntype}): {msg[:120]}")
    # Legacy format: top_signatures
    sigs = validation.get("top_signatures", [])
    if sigs and not violations:
        w("- **Top violation signatures:**")
        for sig in sigs[:5]:
            path = shorten(sig.get("path", ""))
            comp = shorten(sig.get("constraint_component", ""))
            count = sig.get("count", 0)
            w(f"  - `{path}` / `{comp}` (count: {count})")
    w("")

    # ── 8. Leakage Metrics ──
    w("## Leakage Metrics\n")
    w(f"- **Large returns:** {leakage.get('large_returns', 0)}")
    w(f"- **Stdout chars:** {leakage.get('stdout_chars', 0)}")
    w(f"- **Tool calls:** {leakage.get('tool_calls', sum(op_stats.values()))}")
    triples = leakage.get("triples") or meta.get("summary", {}).get("graph_stats", {}).get("triples")
    if triples:
        w(f"- **Triples:** {triples}")
    w("")

    # ── 9. RLM Iterations (if present) ──
    if rlm_iters:
        w("## RLM Iterations\n")
        for it in rlm_iters:
            w(f"### Iteration {it['iteration']}\n")
            if it.get("reasoning"):
                w("**Reasoning:**\n")
                w(f"```\n{it['reasoning']}\n```\n")
            if it.get("code"):
                w("**Code:**\n")
                w(f"```python\n{it['code']}\n```\n")
            if it.get("output"):
                w("**Output:**\n")
                w(f"```\n{it['output']}\n```\n")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────

def resolve_paths(path_arg: str) -> tuple[Path, Path | None]:
    """Resolve trajectory.jsonl and optional summary.json from path argument."""
    p = Path(path_arg)
    if p.is_dir():
        traj = p / "trajectory.jsonl"
        summ = p / "summary.json"
        if not traj.exists():
            raise FileNotFoundError(f"No trajectory.jsonl in {p}")
        return traj, summ if summ.exists() else None
    elif p.is_file() and p.name == "trajectory.jsonl":
        summ = p.parent / "summary.json"
        return p, summ if summ.exists() else None
    elif p.is_file():
        return p, None
    else:
        raise FileNotFoundError(f"Path not found: {p}")


def main():
    parser = argparse.ArgumentParser(
        description="Dump KAG trajectory JSONL as a structured markdown report.")
    parser.add_argument("path", help="Trajectory JSONL file or run directory")
    parser.add_argument("-o", "--output", help="Write report to file (default: stdout)")
    args = parser.parse_args()

    traj_path, summ_path = resolve_paths(args.path)
    events = load_events(traj_path)
    summary = load_summary(summ_path) if summ_path else None

    meta = extract_run_meta(events, summary)
    l0 = extract_l0_sense(events)
    nodes = extract_node_creations(events)
    all_links = extract_links(events)
    section_tree = build_section_tree(all_links)
    caption_links = extract_caption_links(all_links)
    op_stats = extract_op_stats(events)
    validation = extract_validation(events, summary)
    leakage = extract_leakage(events, summary)
    rlm_iters = extract_rlm_iterations(events)

    # Build node lookup for tree rendering
    node_lookup = {nd["iri"]: nd for nd in nodes}

    report = render_markdown(meta, l0, nodes, section_tree, caption_links,
                             op_stats, validation, leakage, rlm_iters,
                             node_lookup)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
