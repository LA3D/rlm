"""Memory reflection tool for human-guided procedural memory creation.

Takes a trajectory + human hint and proposes a memory Item for review.

Usage:
    # Propose a new memory from trajectory with hint
    python memory_reflect.py \
        --trajectory results/protein_properties.jsonl \
        --memory memories.json \
        --hint "The key insight is checking result count before iterating"

    # Review and approve interactively
    python memory_reflect.py \
        --trajectory results/protein_properties.jsonl \
        --memory memories.json \
        --hint "Focus on the efficient API usage pattern" \
        --interactive

    # Compare two trajectories (before/after)
    python memory_reflect.py \
        --trajectory results/after_fix.jsonl \
        --compare results/before_fix.jsonl \
        --memory memories.json \
        --hint "What made the second run more efficient?"
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import json
import dspy
from pathlib import Path
from dataclasses import dataclass
from experiments.reasoningbank.prototype.core.mem import MemStore, Item

# Configure DSPy if not already configured
if not os.environ.get('ANTHROPIC_API_KEY'):
    print("Warning: ANTHROPIC_API_KEY not set")
else:
    if not hasattr(dspy.settings, 'lm') or dspy.settings.lm is None:
        lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
        dspy.configure(lm=lm)


# === Trajectory Loading ===

@dataclass
class TrajectoryData:
    """Parsed trajectory for reflection."""
    task: str
    iterations: int
    converged: bool
    answer: str
    sparql: str | None
    reasoning_steps: list[dict]
    tool_calls: list[dict]
    log_path: str

    def format_summary(self, max_steps: int = 5) -> str:
        """Format trajectory as text for LLM."""
        lines = [
            f"Task: {self.task}",
            f"Iterations: {self.iterations}",
            f"Converged: {self.converged}",
            f"",
            f"SPARQL produced:",
            f"```sparql",
            f"{self.sparql or '(none)'}",
            f"```",
            f"",
            f"Answer: {self.answer[:300]}{'...' if len(self.answer) > 300 else ''}",
            f"",
            f"Reasoning steps:",
        ]

        for step in self.reasoning_steps[:max_steps]:
            lines.append(f"\n--- Step {step.get('iteration', '?')} ---")
            reasoning = step.get('reasoning', '')[:400]
            lines.append(f"Reasoning: {reasoning}{'...' if len(step.get('reasoning', '')) > 400 else ''}")
            code = step.get('code', '')[:300]
            lines.append(f"Code: {code}{'...' if len(step.get('code', '')) > 300 else ''}")

        if len(self.reasoning_steps) > max_steps:
            lines.append(f"\n... ({len(self.reasoning_steps) - max_steps} more steps)")

        return '\n'.join(lines)


def load_trajectory(log_path: str) -> TrajectoryData | None:
    """Load trajectory from JSONL log file."""
    events = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        return None

    start = next((e for e in events if e['event_type'] == 'run_start'), None)
    complete = next((e for e in events if e['event_type'] == 'run_complete'), None)

    if not start or not complete:
        return None

    iterations = [e for e in events if e['event_type'] == 'iteration']
    reasoning_steps = [{
        'iteration': it['data'].get('iteration'),
        'reasoning': it['data'].get('reasoning', ''),
        'code': it['data'].get('code', ''),
        'output': it['data'].get('output', ''),
    } for it in iterations]

    tool_calls = [{
        'tool': e['data'].get('tool'),
    } for e in events if e['event_type'] == 'tool_call']

    return TrajectoryData(
        task=start['data'].get('task', ''),
        iterations=complete['data'].get('iterations', 0),
        converged=complete['data'].get('converged', False),
        answer=complete['data'].get('answer_preview', ''),
        sparql=complete['data'].get('sparql'),
        reasoning_steps=reasoning_steps,
        tool_calls=tool_calls,
        log_path=log_path,
    )


# === DSPy Signatures ===

class ReflectOnTrajectory(dspy.Signature):
    """Reflect on a trajectory to extract a procedural memory based on a human hint.

    The human provides guidance about what insight to capture. Your job is to
    formalize that insight into a reusable procedure that could help future agents.
    """
    trajectory: str = dspy.InputField(desc="The execution trajectory showing task, reasoning, code, and results")
    human_hint: str = dspy.InputField(desc="Human guidance about what insight to capture from this trajectory")
    existing_memories: str = dspy.InputField(desc="Titles of existing memories (to avoid duplication)")

    title: str = dspy.OutputField(desc="Short, descriptive title for this procedure (≤10 words)")
    procedure: str = dspy.OutputField(desc="The reusable procedure, written as clear steps that future agents can follow")
    rationale: str = dspy.OutputField(desc="Why this procedure is useful (1-2 sentences)")


class ReflectOnComparison(dspy.Signature):
    """Compare two trajectories to extract a procedural memory about what made one better.

    The human provides guidance about the comparison. Your job is to identify
    the key difference and formalize it as a reusable procedure.
    """
    trajectory_a: str = dspy.InputField(desc="First trajectory (typically the 'after' or 'better' version)")
    trajectory_b: str = dspy.InputField(desc="Second trajectory (typically the 'before' or 'worse' version)")
    human_hint: str = dspy.InputField(desc="Human guidance about what to compare or learn")
    existing_memories: str = dspy.InputField(desc="Titles of existing memories (to avoid duplication)")

    title: str = dspy.OutputField(desc="Short, descriptive title for this procedure (≤10 words)")
    procedure: str = dspy.OutputField(desc="The reusable procedure based on what made trajectory A better")
    rationale: str = dspy.OutputField(desc="What specifically made the difference (1-2 sentences)")


class RefineMemory(dspy.Signature):
    """Refine an existing memory based on new evidence and human guidance."""
    existing_memory: str = dspy.InputField(desc="The current memory (title + content)")
    trajectory: str = dspy.InputField(desc="New trajectory showing this memory in use")
    human_hint: str = dspy.InputField(desc="Human guidance about how to improve the memory")

    title: str = dspy.OutputField(desc="Refined title (≤10 words)")
    procedure: str = dspy.OutputField(desc="Refined procedure with improvements")
    changes: str = dspy.OutputField(desc="What was changed and why")


# === Reflection Functions ===

def reflect_single(
    traj: TrajectoryData,
    hint: str,
    mem: MemStore,
    verbose: bool = False
) -> Item | None:
    """Reflect on a single trajectory with human hint."""

    # Format existing memory titles
    existing = '\n'.join(f"- {item.title}" for item in mem.all()) or "(no existing memories)"

    if verbose:
        print(f"\n[reflect] Task: {traj.task[:60]}...")
        print(f"[reflect] Hint: {hint}")
        print(f"[reflect] Existing memories: {len(mem.all())}")

    predictor = dspy.Predict(ReflectOnTrajectory, temperature=0.3)

    try:
        result = predictor(
            trajectory=traj.format_summary(),
            human_hint=hint,
            existing_memories=existing,
        )

        item = Item(
            id=Item.make_id(result.title, result.procedure),
            title=result.title[:100],
            desc=f"From reflection: {hint[:50]}",
            content=result.procedure,
            src='success',  # Human-guided = success polarity
            tags=['reflected', 'human-guided'],
        )

        if verbose:
            print(f"\n[reflect] Proposed: {result.title}")
            print(f"[reflect] Rationale: {result.rationale}")

        return item

    except Exception as e:
        print(f"[reflect] Error: {e}")
        return None


def reflect_comparison(
    traj_a: TrajectoryData,
    traj_b: TrajectoryData,
    hint: str,
    mem: MemStore,
    verbose: bool = False
) -> Item | None:
    """Reflect on comparison between two trajectories."""

    existing = '\n'.join(f"- {item.title}" for item in mem.all()) or "(no existing memories)"

    if verbose:
        print(f"\n[compare] Trajectory A: {traj_a.iterations} iterations")
        print(f"[compare] Trajectory B: {traj_b.iterations} iterations")
        print(f"[compare] Hint: {hint}")

    predictor = dspy.Predict(ReflectOnComparison, temperature=0.3)

    try:
        result = predictor(
            trajectory_a=traj_a.format_summary(),
            trajectory_b=traj_b.format_summary(),
            human_hint=hint,
            existing_memories=existing,
        )

        item = Item(
            id=Item.make_id(result.title, result.procedure),
            title=result.title[:100],
            desc=f"From comparison: {hint[:50]}",
            content=result.procedure,
            src='contrastive',
            tags=['reflected', 'comparison', 'human-guided'],
        )

        if verbose:
            print(f"\n[compare] Proposed: {result.title}")
            print(f"[compare] Rationale: {result.rationale}")

        return item

    except Exception as e:
        print(f"[compare] Error: {e}")
        return None


def refine_existing(
    memory_id: str,
    traj: TrajectoryData,
    hint: str,
    mem: MemStore,
    verbose: bool = False
) -> Item | None:
    """Refine an existing memory based on new evidence."""

    if memory_id not in mem._items:
        print(f"[refine] Memory not found: {memory_id}")
        return None

    original = mem._items[memory_id]
    original_text = f"Title: {original.title}\n\nContent:\n{original.content}"

    if verbose:
        print(f"\n[refine] Original: {original.title}")
        print(f"[refine] Hint: {hint}")

    predictor = dspy.Predict(RefineMemory, temperature=0.3)

    try:
        result = predictor(
            existing_memory=original_text,
            trajectory=traj.format_summary(),
            human_hint=hint,
        )

        item = Item(
            id=Item.make_id(result.title, result.procedure),
            title=result.title[:100],
            desc=f"Refined from: {original.title[:30]}",
            content=result.procedure,
            src=original.src,
            tags=['refined', 'human-guided', f'prev:{original.id}'],
        )

        if verbose:
            print(f"\n[refine] Proposed: {result.title}")
            print(f"[refine] Changes: {result.changes}")

        return item

    except Exception as e:
        print(f"[refine] Error: {e}")
        return None


# === Interactive Review ===

def review_proposal(item: Item) -> tuple[bool, Item]:
    """Interactive review of proposed memory item.

    Returns (approved, possibly_edited_item).
    """
    print("\n" + "="*60)
    print("PROPOSED MEMORY")
    print("="*60)
    print(f"\nTitle: {item.title}")
    print(f"Source: {item.src}")
    print(f"Tags: {', '.join(item.tags)}")
    print(f"\nContent:\n{item.content}")
    print("\n" + "="*60)

    while True:
        response = input("\n[A]pprove, [E]dit title, [C]ontent edit, [R]eject? ").strip().lower()

        if response == 'a':
            return True, item
        elif response == 'r':
            return False, item
        elif response == 'e':
            new_title = input(f"New title [{item.title}]: ").strip()
            if new_title:
                item.title = new_title[:100]
                item.id = Item.make_id(item.title, item.content)
            print(f"Updated title: {item.title}")
        elif response == 'c':
            print("Enter new content (end with empty line):")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            if lines:
                item.content = '\n'.join(lines)
                item.id = Item.make_id(item.title, item.content)
            print("Content updated.")
        else:
            print("Unknown option. Use A/E/C/R.")


# === CLI ===

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Memory reflection tool for human-guided procedural memory creation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Propose memory from trajectory
  python memory_reflect.py -t results/task.jsonl -m memories.json \\
      --hint "Focus on the rdfs:domain pattern"

  # Compare two trajectories
  python memory_reflect.py -t results/after.jsonl --compare results/before.jsonl \\
      -m memories.json --hint "What made the second run faster?"

  # Refine existing memory
  python memory_reflect.py -t results/task.jsonl -m memories.json \\
      --refine 2de422c4e0bc --hint "Add note about checking result count"

  # Interactive mode with approval
  python memory_reflect.py -t results/task.jsonl -m memories.json \\
      --hint "..." --interactive --save memories.json
        """
    )

    parser.add_argument('--trajectory', '-t', required=True,
                        help='Path to trajectory JSONL log')
    parser.add_argument('--memory', '-m', required=True,
                        help='Path to memory store JSON')
    parser.add_argument('--hint', required=True,
                        help='Human hint about what to extract/learn')

    parser.add_argument('--compare', metavar='PATH',
                        help='Second trajectory to compare against')
    parser.add_argument('--refine', metavar='ID',
                        help='ID of existing memory to refine')

    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Interactive review before saving')
    parser.add_argument('--save', '-s', metavar='PATH',
                        help='Save updated memory store to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Load memory store
    mem = MemStore()
    if os.path.exists(args.memory):
        mem.load(args.memory)
        print(f"Loaded {len(mem.all())} memories from {args.memory}")
    else:
        print(f"Starting with empty memory store")

    # Load primary trajectory
    traj = load_trajectory(args.trajectory)
    if not traj:
        print(f"Error: Could not load trajectory from {args.trajectory}")
        sys.exit(1)
    print(f"Loaded trajectory: {traj.task[:50]}... ({traj.iterations} iterations)")

    # Perform reflection
    item = None

    if args.compare:
        # Comparison mode
        traj_b = load_trajectory(args.compare)
        if not traj_b:
            print(f"Error: Could not load comparison trajectory from {args.compare}")
            sys.exit(1)
        print(f"Loaded comparison: {traj_b.task[:50]}... ({traj_b.iterations} iterations)")
        item = reflect_comparison(traj, traj_b, args.hint, mem, verbose=args.verbose)

    elif args.refine:
        # Refinement mode
        item = refine_existing(args.refine, traj, args.hint, mem, verbose=args.verbose)

    else:
        # Single trajectory reflection
        item = reflect_single(traj, args.hint, mem, verbose=args.verbose)

    if not item:
        print("\nNo memory item was generated.")
        sys.exit(1)

    # Review
    approved = True
    if args.interactive:
        approved, item = review_proposal(item)

    if not approved:
        print("\nMemory rejected.")
        sys.exit(0)

    # Show final item if not interactive
    if not args.interactive:
        print("\n" + "="*60)
        print("PROPOSED MEMORY")
        print("="*60)
        print(f"\nTitle: {item.title}")
        print(f"ID: {item.id}")
        print(f"Source: {item.src}")
        print(f"Tags: {', '.join(item.tags)}")
        print(f"\nContent:\n{item.content}")
        print("="*60)

    # Save if requested
    if args.save:
        # Check for duplicates
        existing = mem.find_similar(item)
        if existing:
            print(f"\nWarning: Similar memory exists: {existing.title}")
            if args.interactive:
                confirm = input("Add anyway? [y/N] ").strip().lower()
                if confirm != 'y':
                    print("Skipped.")
                    sys.exit(0)

        mem.add(item)
        mem.save(args.save)
        print(f"\nSaved {len(mem.all())} memories to {args.save}")
    else:
        print("\n(Use --save to persist this memory)")


if __name__ == '__main__':
    main()
