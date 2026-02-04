"""Post-trajectory memory augmentation tool.

Analyzes completed trajectories to augment procedural memories:
- Refine existing memories with new evidence
- Generalize task-specific memories
- Merge similar memories
- Create efficiency memories from iteration analysis
- Deprecate superseded memories

Usage:
    from experiments.reasoningbank.prototype.tools.memory_augment import MemoryAugmenter

    augmenter = MemoryAugmenter(mem_store)

    # Load trajectories
    augmenter.load_trajectories('results/test_api_fix/')

    # Analyze and suggest augmentations
    suggestions = augmenter.analyze()

    # Apply approved augmentations
    augmenter.apply(suggestions, approve_ids=['s1', 's2'])
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import dspy
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from experiments.reasoningbank.prototype.core.mem import MemStore, Item, title_similarity, content_jaccard


# === Data Structures ===

@dataclass
class Trajectory:
    """Parsed trajectory from JSONL log."""
    task: str
    endpoint: str
    iterations: int
    converged: bool
    answer: str
    sparql: str | None
    reasoning_steps: list[dict]  # [{iteration, reasoning, code, output}]
    tool_calls: list[dict]       # [{tool, result_preview}]
    lm_usage: dict
    timestamp: str
    log_path: str

    @property
    def total_tokens(self) -> int:
        return self.lm_usage.get('total_tokens', 0)

    @property
    def cost(self) -> float:
        return self.lm_usage.get('total_cost', 0.0)


@dataclass
class Suggestion:
    """A suggested memory augmentation."""
    id: str
    type: str  # 'refine', 'generalize', 'merge', 'efficiency', 'deprecate'
    title: str
    description: str
    evidence: dict  # Supporting data
    new_item: Item | None = None  # The proposed new/updated Item
    target_ids: list[str] = field(default_factory=list)  # IDs of affected memories
    confidence: float = 0.8


# === DSPy Signatures for Augmentation ===

class RefineMemory(dspy.Signature):
    """Refine an existing procedural memory based on new trajectory evidence.

    The refined memory should be more accurate, clearer, or more actionable
    while preserving the core strategy that made it successful.
    """
    original_memory: str = dspy.InputField(desc="The existing memory (title + content)")
    new_evidence: str = dspy.InputField(desc="New trajectory showing the memory being used")
    what_worked: str = dspy.InputField(desc="What aspects of the memory helped")
    what_could_improve: str = dspy.InputField(desc="What was unclear or could be better")

    refined_title: str = dspy.OutputField(desc="Improved title (≤10 words)")
    refined_content: str = dspy.OutputField(desc="Improved procedural content")
    changes_made: str = dspy.OutputField(desc="Brief summary of what was refined")


class GeneralizeMemory(dspy.Signature):
    """Generalize a task-specific memory to apply more broadly.

    Extract the underlying pattern that could help with similar tasks.
    """
    original_memory: str = dspy.InputField(desc="The task-specific memory")
    task_context: str = dspy.InputField(desc="The specific task it was created for")
    similar_tasks: str = dspy.InputField(desc="Other tasks where this pattern could apply")

    generalized_title: str = dspy.OutputField(desc="Broader title (≤10 words)")
    generalized_content: str = dspy.OutputField(desc="Generalized procedure")
    applicability: str = dspy.OutputField(desc="When this pattern applies")


class MergeMemories(dspy.Signature):
    """Merge multiple similar memories into one improved version.

    Combine the best aspects of each while removing redundancy.
    """
    memories: str = dspy.InputField(desc="Multiple memories to merge (separated by ---)")
    overlap_analysis: str = dspy.InputField(desc="What these memories have in common")

    merged_title: str = dspy.OutputField(desc="Combined title (≤10 words)")
    merged_content: str = dspy.OutputField(desc="Unified procedure combining best aspects")
    what_was_combined: str = dspy.OutputField(desc="How the memories were merged")


class CreateEfficiencyMemory(dspy.Signature):
    """Create a memory about avoiding inefficient patterns.

    Based on comparing trajectories that took different numbers of iterations
    for similar tasks.
    """
    task: str = dspy.InputField(desc="The task being analyzed")
    inefficient_traj: str = dspy.InputField(desc="Trajectory that took many iterations")
    efficient_traj: str = dspy.InputField(desc="Trajectory that completed quickly")
    iterations_saved: int = dspy.InputField(desc="How many iterations were saved")

    title: str = dspy.OutputField(desc="Title for efficiency tip (≤10 words)")
    tip: str = dspy.OutputField(desc="How to avoid the inefficient pattern")


# === Trajectory Loading ===

def load_trajectory(log_path: str) -> Trajectory | None:
    """Load and parse a trajectory from JSONL log file."""
    events = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        return None

    # Find run_start and run_complete events
    start_event = next((e for e in events if e['event_type'] == 'run_start'), None)
    complete_event = next((e for e in events if e['event_type'] == 'run_complete'), None)

    if not start_event or not complete_event:
        return None

    # Extract iteration events
    iterations = [e for e in events if e['event_type'] == 'iteration']
    reasoning_steps = []
    for it in iterations:
        d = it['data']
        reasoning_steps.append({
            'iteration': d.get('iteration'),
            'reasoning': d.get('reasoning', ''),
            'code': d.get('code', ''),
            'output': d.get('output', ''),
        })

    # Extract tool calls
    tool_calls = []
    for e in events:
        if e['event_type'] == 'tool_call':
            # Find matching result
            idx = events.index(e)
            result_event = events[idx + 1] if idx + 1 < len(events) else None
            tool_calls.append({
                'tool': e['data'].get('tool'),
                'result_preview': result_event['data'].get('result_preview', '') if result_event else '',
            })

    return Trajectory(
        task=start_event['data'].get('task', ''),
        endpoint=start_event['data'].get('endpoint', ''),
        iterations=complete_event['data'].get('iterations', 0),
        converged=complete_event['data'].get('converged', False),
        answer=complete_event['data'].get('answer_preview', ''),
        sparql=complete_event['data'].get('sparql'),
        reasoning_steps=reasoning_steps,
        tool_calls=tool_calls,
        lm_usage=complete_event['data'].get('lm_usage', {}),
        timestamp=start_event.get('timestamp', ''),
        log_path=log_path,
    )


def load_trajectories_from_dir(log_dir: str) -> list[Trajectory]:
    """Load all trajectories from a directory."""
    trajectories = []
    for path in Path(log_dir).glob('*.jsonl'):
        traj = load_trajectory(str(path))
        if traj:
            trajectories.append(traj)
    return trajectories


# === Memory Augmenter ===

class MemoryAugmenter:
    """Analyzes trajectories and suggests memory augmentations."""

    def __init__(self, mem: MemStore):
        self.mem = mem
        self.trajectories: list[Trajectory] = []
        self._suggestion_counter = 0

    def load_trajectories(self, log_dir: str) -> int:
        """Load trajectories from directory. Returns count loaded."""
        self.trajectories.extend(load_trajectories_from_dir(log_dir))
        return len(self.trajectories)

    def add_trajectory(self, traj: Trajectory):
        """Add a single trajectory."""
        self.trajectories.append(traj)

    def _make_suggestion_id(self) -> str:
        """Generate unique suggestion ID."""
        self._suggestion_counter += 1
        return f"s{self._suggestion_counter}"

    # === Analysis Methods ===

    def find_efficiency_opportunities(self, threshold: int = 3) -> list[Suggestion]:
        """Find tasks where iteration count varies significantly.

        Args:
            threshold: Minimum iteration difference to flag

        Returns:
            List of efficiency suggestions
        """
        suggestions = []

        # Group trajectories by task
        by_task = {}
        for traj in self.trajectories:
            key = traj.task[:100]  # Normalize task key
            if key not in by_task:
                by_task[key] = []
            by_task[key].append(traj)

        # Find tasks with iteration variance
        for task, trajs in by_task.items():
            if len(trajs) < 2:
                continue

            converged = [t for t in trajs if t.converged]
            if len(converged) < 2:
                continue

            iters = [t.iterations for t in converged]
            min_iter, max_iter = min(iters), max(iters)

            if max_iter - min_iter >= threshold:
                # Found efficiency opportunity
                efficient = min(converged, key=lambda t: t.iterations)
                inefficient = max(converged, key=lambda t: t.iterations)

                suggestions.append(Suggestion(
                    id=self._make_suggestion_id(),
                    type='efficiency',
                    title=f"Efficiency opportunity: {task[:40]}...",
                    description=f"Task took {min_iter}-{max_iter} iterations across runs. "
                               f"Potential to save {max_iter - min_iter} iterations.",
                    evidence={
                        'task': task,
                        'efficient_iterations': efficient.iterations,
                        'inefficient_iterations': inefficient.iterations,
                        'efficient_path': efficient.log_path,
                        'inefficient_path': inefficient.log_path,
                    },
                    confidence=0.7,
                ))

        return suggestions

    def find_memory_usage(self) -> dict[str, list[Trajectory]]:
        """Find which trajectories appear to use which memories.

        Returns dict mapping memory ID to list of trajectories that used it.
        """
        usage = {item.id: [] for item in self.mem.all()}

        for traj in self.trajectories:
            # Check if trajectory reasoning mentions memory patterns
            full_reasoning = ' '.join(
                step.get('reasoning', '') + step.get('code', '')
                for step in traj.reasoning_steps
            )

            for item in self.mem.all():
                # Simple heuristic: check if key terms from memory appear
                key_terms = set(item.title.lower().split())
                reasoning_terms = set(full_reasoning.lower().split())

                overlap = len(key_terms & reasoning_terms) / max(len(key_terms), 1)
                if overlap > 0.5:  # More than half the title terms appear
                    usage[item.id].append(traj)

        return usage

    def find_refinement_candidates(self) -> list[Suggestion]:
        """Find memories that could be refined based on usage patterns."""
        suggestions = []
        usage = self.find_memory_usage()

        for item in self.mem.all():
            trajs = usage.get(item.id, [])
            if not trajs:
                continue

            # Check if any trajectories took many iterations despite having memory
            high_iter_trajs = [t for t in trajs if t.iterations > 6]

            if high_iter_trajs:
                suggestions.append(Suggestion(
                    id=self._make_suggestion_id(),
                    type='refine',
                    title=f"Refine: {item.title[:40]}...",
                    description=f"Memory used in {len(trajs)} trajectories, but "
                               f"{len(high_iter_trajs)} still took >6 iterations. "
                               f"May need clarification.",
                    evidence={
                        'memory_id': item.id,
                        'memory_title': item.title,
                        'usage_count': len(trajs),
                        'high_iter_count': len(high_iter_trajs),
                        'avg_iterations': sum(t.iterations for t in trajs) / len(trajs),
                    },
                    target_ids=[item.id],
                    confidence=0.6,
                ))

        return suggestions

    def find_merge_candidates(self, title_thresh: float = 0.6,
                               content_thresh: float = 0.5) -> list[Suggestion]:
        """Find similar memories that could be merged."""
        suggestions = []
        items = self.mem.all()
        merged_sets = []  # Track which items we've already suggested merging

        for i, item1 in enumerate(items):
            for item2 in items[i+1:]:
                # Skip if either already in a merge suggestion
                if any(item1.id in s or item2.id in s for s in merged_sets):
                    continue

                # Check similarity
                title_sim = title_similarity(item1.title, item2.title)
                content_sim = content_jaccard(item1.content, item2.content)

                if title_sim > title_thresh or content_sim > content_thresh:
                    merged_sets.append({item1.id, item2.id})
                    suggestions.append(Suggestion(
                        id=self._make_suggestion_id(),
                        type='merge',
                        title=f"Merge similar memories",
                        description=f"'{item1.title[:30]}...' and '{item2.title[:30]}...' "
                                   f"have {title_sim:.0%} title / {content_sim:.0%} content similarity.",
                        evidence={
                            'title_similarity': title_sim,
                            'content_similarity': content_sim,
                            'memory1': {'id': item1.id, 'title': item1.title},
                            'memory2': {'id': item2.id, 'title': item2.title},
                        },
                        target_ids=[item1.id, item2.id],
                        confidence=max(title_sim, content_sim),
                    ))

        return suggestions

    def analyze(self) -> list[Suggestion]:
        """Run all analysis methods and return combined suggestions."""
        suggestions = []
        suggestions.extend(self.find_efficiency_opportunities())
        suggestions.extend(self.find_refinement_candidates())
        suggestions.extend(self.find_merge_candidates())

        # Sort by confidence
        suggestions.sort(key=lambda s: -s.confidence)
        return suggestions

    # === Augmentation Execution ===

    def execute_efficiency_suggestion(self, suggestion: Suggestion,
                                       verbose: bool = False) -> Item | None:
        """Execute an efficiency suggestion using LLM."""
        evidence = suggestion.evidence

        # Load the trajectories
        efficient = load_trajectory(evidence['efficient_path'])
        inefficient = load_trajectory(evidence['inefficient_path'])

        if not efficient or not inefficient:
            return None

        # Format trajectories for LLM
        def format_traj(t: Trajectory) -> str:
            lines = [f"Task: {t.task}", f"Iterations: {t.iterations}", "Steps:"]
            for step in t.reasoning_steps[:5]:  # First 5 steps
                lines.append(f"  [{step['iteration']}] {step['reasoning'][:200]}...")
            return '\n'.join(lines)

        if verbose:
            print(f"  [efficiency] Comparing {efficient.iterations} vs {inefficient.iterations} iterations")

        ext = dspy.Predict(CreateEfficiencyMemory, temperature=0.3)
        try:
            result = ext(
                task=evidence['task'],
                inefficient_traj=format_traj(inefficient),
                efficient_traj=format_traj(efficient),
                iterations_saved=inefficient.iterations - efficient.iterations,
            )

            item = Item(
                id=Item.make_id(result.title, result.tip),
                title=result.title[:100],
                desc=f"Efficiency tip for: {evidence['task'][:40]}",
                content=result.tip,
                src='pattern',
                tags=['efficiency', 'auto-augment'],
            )

            if verbose:
                print(f"  [efficiency] Created: {item.title}")

            return item
        except Exception as e:
            if verbose:
                print(f"  [efficiency] Failed: {e}")
            return None

    def execute_merge_suggestion(self, suggestion: Suggestion,
                                  verbose: bool = False) -> Item | None:
        """Execute a merge suggestion using LLM."""
        target_ids = suggestion.target_ids
        items = [self.mem._items[id] for id in target_ids if id in self.mem._items]

        if len(items) < 2:
            return None

        # Format memories for LLM
        memories_text = '\n---\n'.join(
            f"Title: {item.title}\nContent: {item.content}"
            for item in items
        )

        overlap = f"Both memories address {suggestion.evidence.get('task', 'similar patterns')}"

        if verbose:
            print(f"  [merge] Combining {len(items)} memories")

        ext = dspy.Predict(MergeMemories, temperature=0.3)
        try:
            result = ext(memories=memories_text, overlap_analysis=overlap)

            item = Item(
                id=Item.make_id(result.merged_title, result.merged_content),
                title=result.merged_title[:100],
                desc=f"Merged from: {', '.join(i.title[:20] for i in items)}",
                content=result.merged_content,
                src=items[0].src,  # Inherit source from first item
                tags=['merged', 'auto-augment'],
            )

            if verbose:
                print(f"  [merge] Created: {item.title}")

            return item
        except Exception as e:
            if verbose:
                print(f"  [merge] Failed: {e}")
            return None

    def execute_refine_suggestion(self, suggestion: Suggestion,
                                   verbose: bool = False) -> Item | None:
        """Execute a refinement suggestion using LLM."""
        target_id = suggestion.target_ids[0] if suggestion.target_ids else None
        if not target_id or target_id not in self.mem._items:
            return None

        original = self.mem._items[target_id]
        evidence = suggestion.evidence

        # Find a trajectory that used this memory
        usage = self.find_memory_usage()
        trajs = usage.get(target_id, [])

        if not trajs:
            return None

        # Pick a high-iteration trajectory as evidence of what could improve
        traj = max(trajs, key=lambda t: t.iterations)

        # Format for LLM
        original_text = f"Title: {original.title}\nContent: {original.content}"

        traj_text = f"Task: {traj.task}\nIterations: {traj.iterations}\n"
        for step in traj.reasoning_steps[:3]:
            traj_text += f"Step {step['iteration']}: {step['reasoning'][:150]}...\n"

        if verbose:
            print(f"  [refine] Analyzing {original.title[:40]}...")

        ext = dspy.Predict(RefineMemory, temperature=0.3)
        try:
            result = ext(
                original_memory=original_text,
                new_evidence=traj_text,
                what_worked="The core pattern was used correctly",
                what_could_improve=f"Still took {traj.iterations} iterations, may need clearer steps",
            )

            item = Item(
                id=Item.make_id(result.refined_title, result.refined_content),
                title=result.refined_title[:100],
                desc=f"Refined from: {original.title[:40]}",
                content=result.refined_content,
                src=original.src,
                tags=['refined', 'auto-augment', f'prev:{original.id}'],
            )

            if verbose:
                print(f"  [refine] Created: {item.title}")
                print(f"  [refine] Changes: {result.changes_made[:100]}")

            return item
        except Exception as e:
            if verbose:
                print(f"  [refine] Failed: {e}")
            return None

    def apply(self, suggestions: list[Suggestion],
              approve_ids: list[str] = None,
              verbose: bool = False) -> list[Item]:
        """Apply approved suggestions and return created items.

        Args:
            suggestions: List of suggestions to consider
            approve_ids: IDs of suggestions to apply (if None, apply all)
            verbose: Print progress

        Returns:
            List of newly created/updated Items
        """
        created = []

        for suggestion in suggestions:
            if approve_ids and suggestion.id not in approve_ids:
                continue

            if verbose:
                print(f"\nApplying {suggestion.type}: {suggestion.title[:50]}...")

            item = None
            if suggestion.type == 'efficiency':
                item = self.execute_efficiency_suggestion(suggestion, verbose)
            elif suggestion.type == 'merge':
                item = self.execute_merge_suggestion(suggestion, verbose)
            elif suggestion.type == 'refine':
                item = self.execute_refine_suggestion(suggestion, verbose)

            if item:
                self.mem.add(item)
                created.append(item)

                # If this was a merge or refine, optionally deprecate old items
                if suggestion.type in ('merge', 'refine') and suggestion.target_ids:
                    for old_id in suggestion.target_ids:
                        if old_id in self.mem._items:
                            old_item = self.mem._items[old_id]
                            old_item.tags.append(f'superseded_by:{item.id}')

        return created

    def summary(self) -> str:
        """Return a summary of loaded data and analysis."""
        lines = [
            f"=== Memory Augmenter Summary ===",
            f"Trajectories loaded: {len(self.trajectories)}",
            f"Memories in store: {len(self.mem.all())}",
            "",
        ]

        if self.trajectories:
            total_iters = sum(t.iterations for t in self.trajectories)
            avg_iters = total_iters / len(self.trajectories)
            converged = sum(1 for t in self.trajectories if t.converged)
            lines.append(f"Average iterations: {avg_iters:.1f}")
            lines.append(f"Convergence rate: {converged}/{len(self.trajectories)}")
            lines.append("")

        suggestions = self.analyze()
        by_type = {}
        for s in suggestions:
            by_type[s.type] = by_type.get(s.type, 0) + 1

        lines.append(f"Suggestions found: {len(suggestions)}")
        for stype, count in sorted(by_type.items()):
            lines.append(f"  - {stype}: {count}")

        return '\n'.join(lines)


# === CLI ===

def main():
    """CLI for memory augmentation."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description='Post-trajectory memory augmentation')
    parser.add_argument('--trajectories', '-t', required=True, help='Directory with trajectory logs')
    parser.add_argument('--memory', '-m', required=True, help='Memory store JSON file')
    parser.add_argument('--analyze', '-a', action='store_true', help='Analyze and show suggestions')
    parser.add_argument('--apply', nargs='*', help='Apply suggestions (IDs or "all")')
    parser.add_argument('--save', '-s', help='Save updated memory to file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Load memory
    mem = MemStore()
    if os.path.exists(args.memory):
        mem.load(args.memory)
        print(f"Loaded {len(mem.all())} memories from {args.memory}")

    # Create augmenter and load trajectories
    augmenter = MemoryAugmenter(mem)
    count = augmenter.load_trajectories(args.trajectories)
    print(f"Loaded {count} trajectories from {args.trajectories}")

    if args.analyze or args.apply is not None:
        print()
        print(augmenter.summary())

        suggestions = augmenter.analyze()

        if suggestions:
            print(f"\n=== Suggestions ===")
            for s in suggestions:
                print(f"\n[{s.id}] {s.type.upper()}: {s.title}")
                print(f"    {s.description}")
                print(f"    Confidence: {s.confidence:.0%}")

        if args.apply is not None:
            approve_ids = None if 'all' in args.apply else args.apply
            created = augmenter.apply(suggestions, approve_ids, verbose=args.verbose)
            print(f"\nApplied {len(created)} augmentations")

            if args.save:
                mem.save(args.save)
                print(f"Saved {len(mem.all())} memories to {args.save}")


if __name__ == '__main__':
    main()
