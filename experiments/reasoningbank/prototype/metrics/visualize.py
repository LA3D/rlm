#!/usr/bin/env python
"""Visualization tools for trajectory diversity metrics.

Generates plots to interpret diversity analysis results.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle
from typing import Optional

from experiments.reasoningbank.metrics.diversity import (
    compute_diversity_report,
    _extract_operations,
    trajectory_jaccard,
    trajectory_edit_distance,
    find_divergence_point,
    iteration_diversity,
    diversity_convergence,
)


def plot_similarity_heatmap(
    trajectories: list[list[dict]],
    metric: str = 'jaccard',
    labels: Optional[list[str]] = None,
    save_path: Optional[str] = None
):
    """Plot pairwise similarity heatmap.

    Args:
        trajectories: List of trajectories
        metric: 'jaccard' or 'edit_distance'
        labels: Optional trajectory labels (default: T1, T2, ...)
        save_path: Optional path to save figure
    """
    n = len(trajectories)
    if labels is None:
        labels = [f"T{i+1}" for i in range(n)]

    # Compute pairwise matrix
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if metric == 'jaccard':
                matrix[i, j] = trajectory_jaccard(trajectories[i], trajectories[j])
            elif metric == 'edit_distance':
                matrix[i, j] = trajectory_edit_distance(trajectories[i], trajectories[j])

    # Create heatmap
    fig, ax = plt.subplots(figsize=(8, 6))

    if metric == 'jaccard':
        # Jaccard: 1.0 = identical (green), 0.0 = different (red)
        sns.heatmap(matrix, annot=True, fmt='.2f', cmap='RdYlGn',
                   xticklabels=labels, yticklabels=labels,
                   vmin=0, vmax=1, ax=ax, cbar_kws={'label': 'Jaccard Similarity'})
        ax.set_title('Trajectory Similarity Heatmap\n(Higher = More Similar)', fontsize=14, fontweight='bold')
    else:
        # Edit distance: 0 = identical (green), high = different (red)
        sns.heatmap(matrix, annot=True, fmt='.0f', cmap='RdYlGn_r',
                   xticklabels=labels, yticklabels=labels,
                   ax=ax, cbar_kws={'label': 'Edit Distance'})
        ax.set_title('Trajectory Edit Distance Heatmap\n(Lower = More Similar)', fontsize=14, fontweight='bold')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved heatmap to {save_path}")

    return fig


def plot_iteration_diversity(
    trajectories: list[list[dict]],
    save_path: Optional[str] = None
):
    """Plot diversity at each iteration.

    Shows where trajectories diverge.
    """
    max_len = max(len(t) for t in trajectories)
    diversities = [iteration_diversity(trajectories, i) for i in range(max_len)]

    fig, ax = plt.subplots(figsize=(10, 5))

    # Bar plot with color gradient
    colors = plt.cm.RdYlGn(diversities)
    bars = ax.bar(range(max_len), diversities, color=colors, edgecolor='black', linewidth=1)

    # Threshold line for "forking point"
    ax.axhline(y=0.5, color='red', linestyle='--', linewidth=2, alpha=0.7,
              label='Forking Threshold (0.5)')

    # Annotations
    ax.set_xlabel('Iteration', fontsize=12, fontweight='bold')
    ax.set_ylabel('Diversity Score', fontsize=12, fontweight='bold')
    ax.set_title('Per-Iteration Diversity\n(Higher = More Variation at That Step)',
                fontsize=14, fontweight='bold')
    ax.set_ylim(0, 1.1)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for i, (bar, div) in enumerate(zip(bars, diversities)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
               f'{div:.2f}', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved iteration diversity plot to {save_path}")

    return fig


def plot_trajectory_flows(
    trajectories: list[list[dict]],
    labels: Optional[list[str]] = None,
    save_path: Optional[str] = None
):
    """Plot trajectory flows showing operations at each step.

    Visualizes where trajectories diverge.
    """
    n = len(trajectories)
    max_len = max(len(t) for t in trajectories)

    if labels is None:
        labels = [f"T{i+1}" for i in range(n)]

    # Extract primary operation per step for each trajectory
    def get_primary_op(step: dict) -> str:
        import re
        if not step:
            return ''
        data = step.get('data', step)
        if isinstance(data, dict) and 'code' in data:
            code = data['code']
            if code:
                func_calls = re.findall(r'([a-zA-Z_]\w*)\s*\(', code)
                if func_calls:
                    return func_calls[0][:15]  # Limit length
        return step.get('tool', '')[:15]

    # Build operation matrix
    ops_matrix = []
    for traj in trajectories:
        ops = [get_primary_op(step) for step in traj]
        # Pad to max length
        ops += [''] * (max_len - len(ops))
        ops_matrix.append(ops)

    # Create figure
    fig, ax = plt.subplots(figsize=(max(12, max_len * 2), max(6, n * 0.8)))

    # Color map for highlighting differences
    colors_list = plt.cm.Set3(range(n))

    # Draw flow diagram
    for i, (ops, label) in enumerate(zip(ops_matrix, labels)):
        y = n - i - 1  # Reverse order for plotting
        color = colors_list[i]

        # Draw trajectory line
        ax.plot([0, max_len], [y, y], color=color, linewidth=3, alpha=0.3)

        # Draw operation boxes
        for j, op in enumerate(ops):
            if op:
                # Check if this operation is unique at this step
                ops_at_step = [ops_matrix[k][j] for k in range(n) if ops_matrix[k][j]]
                is_unique = len(set(ops_at_step)) > 1

                box_color = 'lightcoral' if is_unique else 'lightgreen'
                rect = Rectangle((j - 0.3, y - 0.3), 0.6, 0.6,
                               facecolor=box_color, edgecolor='black', linewidth=2)
                ax.add_patch(rect)

                # Add text
                ax.text(j, y, op, ha='center', va='center',
                       fontsize=9, fontweight='bold')

        # Add trajectory label
        ax.text(-0.5, y, label, ha='right', va='center',
               fontsize=12, fontweight='bold', color=color)

    # Styling
    ax.set_xlim(-1, max_len)
    ax.set_ylim(-1, n)
    ax.set_xlabel('Iteration', fontsize=12, fontweight='bold')
    ax.set_title('Trajectory Flow Diagram\n(Green=Shared Operation, Red=Divergent)',
                fontsize=14, fontweight='bold')
    ax.set_xticks(range(max_len))
    ax.set_yticks([])
    ax.grid(axis='x', alpha=0.3)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='lightgreen', edgecolor='black', label='Shared Operation'),
        Patch(facecolor='lightcoral', edgecolor='black', label='Divergent Operation')
    ]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved trajectory flow diagram to {save_path}")

    return fig


def plot_diversity_convergence(
    trajectories: list[list[dict]],
    save_path: Optional[str] = None
):
    """Plot how diversity changes as we add more trajectories.

    Shows if we have enough samples (k) for stable diversity estimate.
    """
    if len(trajectories) < 3:
        print("Need at least 3 trajectories for convergence plot")
        return None

    # Compute diversity for k=2,3,...,n
    try:
        scores = diversity_convergence(trajectories, metric='vendi')
    except ImportError:
        print("Vendi score not available, skipping convergence plot")
        return None

    k_values = list(range(2, len(trajectories) + 1))

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot convergence
    ax.plot(k_values, scores, marker='o', linewidth=2, markersize=8,
           color='steelblue', label='Trajectory Vendi Score')

    # Reference lines
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5,
              label='Min Diversity (all identical)')
    ax.axhline(y=len(trajectories), color='gray', linestyle='--', alpha=0.5,
              label='Max Diversity (all unique)')

    # Styling
    ax.set_xlabel('Number of Trajectories (k)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Vendi Score\n(Effective Unique Trajectories)', fontsize=12, fontweight='bold')
    ax.set_title('Diversity vs. Sample Size\n(Plateauing = Sufficient Samples)',
                fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xticks(k_values)

    # Highlight if plateaued
    if len(scores) >= 3:
        # Check if last 3 values are within 10% of each other
        recent = scores[-3:]
        if max(recent) - min(recent) < 0.1 * np.mean(recent):
            ax.axvspan(k_values[-3], k_values[-1], alpha=0.2, color='green',
                      label='Plateaued (stable)')
            ax.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved convergence plot to {save_path}")

    return fig


def plot_diversity_summary(
    trajectories: list[list[dict]],
    queries: Optional[list[str]] = None,
    save_path: Optional[str] = None
):
    """Create a comprehensive 2x2 summary dashboard.

    Combines multiple visualizations into one figure.
    """
    report = compute_diversity_report(trajectories, queries=queries)
    n = len(trajectories)

    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # 1. Similarity heatmap (top left)
    ax1 = fig.add_subplot(gs[0, 0])
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            matrix[i, j] = trajectory_jaccard(trajectories[i], trajectories[j])
    labels = [f"T{i+1}" for i in range(n)]
    sns.heatmap(matrix, annot=True, fmt='.2f', cmap='RdYlGn',
               xticklabels=labels, yticklabels=labels,
               vmin=0, vmax=1, ax=ax1, cbar_kws={'label': 'Jaccard'})
    ax1.set_title('Pairwise Similarity', fontsize=12, fontweight='bold')

    # 2. Per-iteration diversity (top right)
    ax2 = fig.add_subplot(gs[0, 1])
    max_len = max(len(t) for t in trajectories)
    diversities = [iteration_diversity(trajectories, i) for i in range(max_len)]
    colors = plt.cm.RdYlGn(diversities)
    ax2.bar(range(max_len), diversities, color=colors, edgecolor='black')
    ax2.axhline(y=0.5, color='red', linestyle='--', linewidth=2, alpha=0.7)
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Diversity')
    ax2.set_title('Per-Iteration Diversity', fontsize=12, fontweight='bold')
    ax2.set_ylim(0, 1.1)
    ax2.grid(axis='y', alpha=0.3)

    # 3. Metric summary (middle, spans both columns)
    ax3 = fig.add_subplot(gs[1, :])
    ax3.axis('off')

    summary_text = f"""
DIVERSITY REPORT SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTCOME DIVERSITY (What did we get?)
  • SPARQL Vendi Score:        {report.sparql_vendi_score:.2f} effective queries (out of {len(queries) if queries else 'N/A'})
  • Unique query patterns:      {report.unique_query_patterns}
  • Answer overlap (Jaccard):   {report.answer_jaccard:.2f}

TRAJECTORY DIVERSITY (How did we get there?)
  • Trajectory Vendi Score:     {report.trajectory_vendi_score:.2f} effective trajectories (out of {n})
  • Mean pairwise Jaccard:      {report.mean_pairwise_jaccard:.2f}  (1.0 = identical, 0.0 = disjoint)
  • Mean edit distance:         {report.mean_edit_distance:.1f} operations

DECISION POINTS (Where is uncertainty?)
  • Forking iterations:         {report.forking_points}
  • Mean divergence iteration:  {report.mean_divergence_iteration:.1f}

SAMPLING EFFICIENCY (Redundancy?)
  • Effective trajectory count: {report.effective_trajectory_count:.2f}
  • Sampling efficiency:        {report.sampling_efficiency:.1%}  ({(1-report.sampling_efficiency):.1%} redundancy)
"""

    ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
            fontsize=11, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    # 4. Divergence points visualization (bottom left)
    ax4 = fig.add_subplot(gs[2, 0])
    divergence_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            divergence_matrix[i, j] = find_divergence_point(trajectories[i], trajectories[j])
    sns.heatmap(divergence_matrix, annot=True, fmt='.0f', cmap='viridis',
               xticklabels=labels, yticklabels=labels, ax=ax4,
               cbar_kws={'label': 'Divergence Point'})
    ax4.set_title('Divergence Point Heatmap', fontsize=12, fontweight='bold')

    # 5. Efficiency pie chart (bottom right)
    ax5 = fig.add_subplot(gs[2, 1])
    sizes = [report.effective_trajectory_count,
            n - report.effective_trajectory_count]
    labels_pie = ['Unique\nTrajectories', 'Redundant\nTrajectories']
    colors_pie = ['#90EE90', '#FFB6C6']
    explode = (0.1, 0)

    wedges, texts, autotexts = ax5.pie(sizes, labels=labels_pie, autopct='%1.1f%%',
                                        colors=colors_pie, explode=explode,
                                        startangle=90, textprops={'fontsize': 11, 'fontweight': 'bold'})
    ax5.set_title(f'Sampling Efficiency\n({report.sampling_efficiency:.1%} Unique)',
                 fontsize=12, fontweight='bold')

    # Overall title
    fig.suptitle('Trajectory Diversity Analysis Dashboard',
                fontsize=16, fontweight='bold', y=0.98)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved summary dashboard to {save_path}")

    return fig


def visualize_scenario(
    name: str,
    trajectories: list[list[dict]],
    queries: Optional[list[str]] = None,
    output_dir: str = '.'
):
    """Generate all visualizations for a scenario.

    Args:
        name: Scenario name (used for filenames)
        trajectories: List of trajectories
        queries: Optional SPARQL queries
        output_dir: Directory to save plots
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    name_safe = name.replace(' ', '_').lower()

    print(f"\nGenerating visualizations for: {name}")
    print("=" * 70)

    # 1. Summary dashboard
    plot_diversity_summary(
        trajectories, queries,
        save_path=f"{output_dir}/{name_safe}_summary.png"
    )

    # 2. Similarity heatmap
    plot_similarity_heatmap(
        trajectories,
        save_path=f"{output_dir}/{name_safe}_similarity.png"
    )

    # 3. Iteration diversity
    plot_iteration_diversity(
        trajectories,
        save_path=f"{output_dir}/{name_safe}_iterations.png"
    )

    # 4. Trajectory flows
    plot_trajectory_flows(
        trajectories,
        save_path=f"{output_dir}/{name_safe}_flows.png"
    )

    # 5. Convergence (if enough trajectories)
    if len(trajectories) >= 3:
        plot_diversity_convergence(
            trajectories,
            save_path=f"{output_dir}/{name_safe}_convergence.png"
        )

    print(f"✓ Saved all visualizations to {output_dir}/")
    plt.close('all')  # Clean up


if __name__ == '__main__':
    # Quick test
    print("Diversity visualization tools loaded")
    print("Use visualize_scenario() to generate plots for your trajectories")
