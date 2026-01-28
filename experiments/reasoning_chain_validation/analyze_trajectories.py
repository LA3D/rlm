#!/usr/bin/env python3
"""Analyze saved trajectories from reasoning chain experiments.

This script loads trajectory markdown files and runs behavior analysis,
generating a report comparing different conditions.

Usage:
    python analyze_trajectories.py results/trajectories
    python analyze_trajectories.py results/trajectories --condition exemplar5
    python analyze_trajectories.py results/trajectories --task L2-crossref
"""

import argparse
import json
from pathlib import Path
from collections import defaultdict
from behavior_analysis import analyze_reasoning_trace, BehaviorAnalysis


def load_trajectory(trace_file: Path) -> dict:
    """Load a trajectory markdown file and extract key components."""
    content = trace_file.read_text()

    # Extract metadata from filename: {task_id}_{condition}_{timestamp}.md
    parts = trace_file.stem.split("_")
    if len(parts) >= 2:
        task_id = parts[0]
        condition = parts[1]
        timestamp = "_".join(parts[2:]) if len(parts) > 2 else "unknown"
    else:
        task_id = "unknown"
        condition = "unknown"
        timestamp = "unknown"

    # Extract sections
    sections = {}
    current_section = None
    section_content = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(section_content).strip()
            current_section = line[3:].strip()
            section_content = []
        else:
            section_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(section_content).strip()

    return {
        "file": trace_file.name,
        "task_id": task_id,
        "condition": condition,
        "timestamp": timestamp,
        "question": sections.get("Question", "").split("**Question**:")[-1].strip() if "Question" in sections.get("", "") else "",
        "response": sections.get("Response", ""),
        "prompt": sections.get("Prompt", ""),
        "metrics": sections.get("Metrics", "")
    }


def analyze_trajectory_file(trace_file: Path) -> tuple[dict, BehaviorAnalysis]:
    """Load and analyze a single trajectory file."""
    traj = load_trajectory(trace_file)
    analysis = analyze_reasoning_trace(traj["response"])
    return traj, analysis


def generate_report(trajectories: list[tuple[dict, BehaviorAnalysis]], output_file: Path = None):
    """Generate comparison report from analyzed trajectories."""

    # Group by condition
    by_condition = defaultdict(list)
    for traj, analysis in trajectories:
        by_condition[traj["condition"]].append((traj, analysis))

    # Compute statistics per condition
    stats = {}
    for condition, items in by_condition.items():
        analyses = [a for _, a in items]

        stats[condition] = {
            "count": len(items),
            "avg_overall_score": sum(a.overall_score for a in analyses) / len(analyses),
            "avg_state_tracking": sum(a.state_tracking_score for a in analyses) / len(analyses),
            "avg_verification": sum(a.verification_score for a in analyses) / len(analyses),
            "avg_reasoning_quality": sum(a.reasoning_quality_score for a in analyses) / len(analyses),
            "good_count": sum(1 for a in analyses if a.classification == "good"),
            "adequate_count": sum(1 for a in analyses if a.classification == "adequate"),
            "poor_count": sum(1 for a in analyses if a.classification == "poor"),
        }

    # Print report
    print("\n" + "="*60)
    print("TRAJECTORY BEHAVIOR ANALYSIS")
    print("="*60)

    print(f"\nTotal trajectories analyzed: {len(trajectories)}")
    print(f"Conditions: {', '.join(by_condition.keys())}")

    print("\n" + "-"*60)
    print("SUMMARY BY CONDITION")
    print("-"*60)

    print(f"\n{'Condition':<12} {'Count':<8} {'Overall':<10} {'State':<10} {'Verify':<10} {'Quality':<10}")
    print("-"*70)

    for condition in sorted(stats.keys()):
        s = stats[condition]
        print(f"{condition:<12} {s['count']:<8} "
              f"{s['avg_overall_score']:<10.2f} "
              f"{s['avg_state_tracking']:<10.2f} "
              f"{s['avg_verification']:<10.2f} "
              f"{s['avg_reasoning_quality']:<10.2f}")

    print("\n" + "-"*60)
    print("CLASSIFICATION BREAKDOWN")
    print("-"*60)

    print(f"\n{'Condition':<12} {'Good':<8} {'Adequate':<10} {'Poor':<8}")
    print("-"*40)

    for condition in sorted(stats.keys()):
        s = stats[condition]
        print(f"{condition:<12} {s['good_count']:<8} {s['adequate_count']:<10} {s['poor_count']:<8}")

    # Individual trajectory details
    print("\n" + "-"*60)
    print("INDIVIDUAL TRAJECTORIES")
    print("-"*60)

    for traj, analysis in sorted(trajectories, key=lambda x: (x[0]["condition"], x[0]["task_id"])):
        print(f"\n{traj['file']}")
        print(f"  Task: {traj['task_id']}, Condition: {traj['condition']}")
        print(f"  Overall: {analysis.overall_score:.2f} ({analysis.classification})")
        print(f"  State tracking: {analysis.state_tracking_score:.2f}")
        print(f"  Verification: {analysis.verification_score:.2f}")
        print(f"  Quality: {analysis.reasoning_quality_score:.2f}")
        print(f"  Indicators:")
        print(f"    - State refs: {analysis.explicit_state_references}")
        print(f"    - Preconditions: {analysis.precondition_checking}")
        print(f"    - Verification: {analysis.postcondition_verification}")
        print(f"    - Anti-patterns: {analysis.anti_pattern_awareness}")

    # Save to file if requested
    if output_file:
        report_data = {
            "timestamp": Path(trajectories[0][0]["timestamp"]).name if trajectories else "unknown",
            "total_trajectories": len(trajectories),
            "conditions": list(by_condition.keys()),
            "statistics": stats,
            "trajectories": [
                {
                    "file": traj["file"],
                    "task_id": traj["task_id"],
                    "condition": traj["condition"],
                    "analysis": {
                        "overall_score": analysis.overall_score,
                        "state_tracking_score": analysis.state_tracking_score,
                        "verification_score": analysis.verification_score,
                        "reasoning_quality_score": analysis.reasoning_quality_score,
                        "classification": analysis.classification,
                        "indicators": {
                            "explicit_state_references": analysis.explicit_state_references,
                            "state_progression": analysis.state_progression,
                            "precondition_checking": analysis.precondition_checking,
                            "postcondition_verification": analysis.postcondition_verification,
                            "domain_range_checking": analysis.domain_range_checking,
                            "step_by_step_structure": analysis.step_by_step_structure,
                            "explicit_reasoning": analysis.explicit_reasoning,
                            "anti_pattern_awareness": analysis.anti_pattern_awareness,
                        }
                    }
                }
                for traj, analysis in trajectories
            ]
        }

        with output_file.open("w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\nReport saved: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Analyze reasoning chain experiment trajectories")
    parser.add_argument("trajectory_dir", type=Path, help="Directory containing trajectory files")
    parser.add_argument("--condition", help="Filter to specific condition")
    parser.add_argument("--task", help="Filter to specific task ID")
    parser.add_argument("--output", type=Path, help="Save report to JSON file")

    args = parser.parse_args()

    if not args.trajectory_dir.exists():
        print(f"Error: Directory not found: {args.trajectory_dir}")
        return

    # Find all trajectory markdown files
    trace_files = list(args.trajectory_dir.glob("*.md"))

    if not trace_files:
        print(f"No trajectory files found in {args.trajectory_dir}")
        return

    print(f"Found {len(trace_files)} trajectory files")

    # Load and analyze
    trajectories = []
    for trace_file in trace_files:
        traj, analysis = analyze_trajectory_file(trace_file)

        # Apply filters
        if args.condition and traj["condition"] != args.condition:
            continue
        if args.task and traj["task_id"] != args.task:
            continue

        trajectories.append((traj, analysis))

    if not trajectories:
        print("No trajectories match the filters")
        return

    # Generate report
    generate_report(trajectories, output_file=args.output)


if __name__ == "__main__":
    main()
