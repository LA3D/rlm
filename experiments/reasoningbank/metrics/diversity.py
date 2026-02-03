"""
Trajectory Diversity Metrics for MaTTS Evaluation

Provides quantitative measures of trajectory diversity analogous to
ensemble diagnostics in molecular dynamics simulations.

Metrics are organized in levels:
- Level 1: Outcome diversity (SPARQL queries, answers)
- Level 2: Trajectory diversity (tool sequences, embeddings)
- Level 3: Decision point analysis (forking points, iteration variance)
- Level 4: Convergence diagnostics (effective sample size)

Dependencies:
- vendi-score>=0.2.0 (for Vendi Score computation)
- sentence-transformers>=2.2 (for text embeddings)
- Optional: python-Levenshtein (faster edit distance, falls back to difflib)
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
import json
import re
import numpy as np

# Lazy imports for optional dependencies
_sentence_transformer = None
_vendi_score = None


def _get_encoder(model: str = 'all-MiniLM-L6-v2'):
    """Lazy-load sentence transformer encoder."""
    global _sentence_transformer
    if _sentence_transformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer = SentenceTransformer(model)
        except ImportError:
            raise ImportError(
                "sentence-transformers required for embedding-based metrics. "
                "Install with: pip install sentence-transformers"
            )
    return _sentence_transformer


def _get_vendi():
    """Lazy-load vendi score module."""
    global _vendi_score
    if _vendi_score is None:
        try:
            from vendi_score import vendi
            _vendi_score = vendi
        except ImportError:
            raise ImportError(
                "vendi-score required for Vendi Score computation. "
                "Install with: pip install vendi-score"
            )
    return _vendi_score


def _cosine_similarity(embeddings: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity matrix."""
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
    normalized = embeddings / norms
    # Compute similarity matrix
    return np.dot(normalized, normalized.T)


def _levenshtein_distance(seq1: list, seq2: list) -> int:
    """Compute Levenshtein edit distance between two sequences.

    This computes element-level edit distance (not character-level).
    Uses dynamic programming implementation for correctness.

    Args:
        seq1, seq2: Lists of elements (strings, ints, etc.)

    Returns:
        Minimum number of insertions, deletions, substitutions to transform seq1 → seq2
    """
    # Use dynamic programming for element-level distance
    # (python-Levenshtein library is character-level, not suitable for our use case)
    m, n = len(seq1), len(seq2)

    # Create DP table
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Base cases: transforming empty sequence
    for i in range(m + 1):
        dp[i][0] = i  # Delete all elements from seq1
    for j in range(n + 1):
        dp[0][j] = j  # Insert all elements into empty seq1

    # Fill DP table
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i-1] == seq2[j-1]:
                # Elements match, no operation needed
                dp[i][j] = dp[i-1][j-1]
            else:
                # Minimum of: delete, insert, substitute
                dp[i][j] = 1 + min(
                    dp[i-1][j],    # Delete from seq1
                    dp[i][j-1],    # Insert into seq1
                    dp[i-1][j-1]   # Substitute
                )

    return dp[m][n]


# =============================================================================
# Level 1: Outcome Diversity (What did we get?)
# =============================================================================

def sparql_vendi_score(queries: list[str], model: str = 'all-MiniLM-L6-v2') -> float:
    """Compute Vendi Score on SPARQL query embeddings.

    Returns: Effective number of unique query strategies.
    Higher values = more diverse queries.

    Args:
        queries: List of SPARQL query strings
        model: Sentence transformer model name

    Returns:
        Vendi Score (interpretable as effective number of unique queries)
    """
    if len(queries) < 2:
        return float(len(queries))

    # Filter out empty/None queries
    valid_queries = [q for q in queries if q and isinstance(q, str)]
    if len(valid_queries) < 2:
        return float(len(valid_queries))

    encoder = _get_encoder(model)
    vendi = _get_vendi()

    embeddings = encoder.encode(valid_queries)
    similarities = _cosine_similarity(embeddings)

    return vendi.score_K(similarities)


def extract_query_pattern(query: str) -> str:
    """Extract structural pattern from SPARQL query.

    Captures: predicates used, query shape (SELECT/CONSTRUCT/ASK),
    presence of FILTER, OPTIONAL, UNION, etc.
    """
    if not query:
        return "empty"

    pattern_parts = []

    # Query type
    query_upper = query.upper()
    if 'SELECT' in query_upper:
        pattern_parts.append('SELECT')
    elif 'CONSTRUCT' in query_upper:
        pattern_parts.append('CONSTRUCT')
    elif 'ASK' in query_upper:
        pattern_parts.append('ASK')
    elif 'DESCRIBE' in query_upper:
        pattern_parts.append('DESCRIBE')

    # Modifiers
    if 'FILTER' in query_upper:
        pattern_parts.append('FILTER')
    if 'OPTIONAL' in query_upper:
        pattern_parts.append('OPTIONAL')
    if 'UNION' in query_upper:
        pattern_parts.append('UNION')
    if 'GROUP BY' in query_upper:
        pattern_parts.append('GROUP')
    if 'ORDER BY' in query_upper:
        pattern_parts.append('ORDER')
    if 'LIMIT' in query_upper:
        pattern_parts.append('LIMIT')

    # Extract predicates (simplified)
    predicate_pattern = r'<([^>]+)>|(\w+:\w+)'
    predicates = set()
    for match in re.finditer(predicate_pattern, query):
        pred = match.group(1) or match.group(2)
        if pred and not pred.startswith('http://www.w3.org/'):  # Skip common RDF predicates
            # Extract local name
            if '/' in pred:
                pred = pred.split('/')[-1]
            if '#' in pred:
                pred = pred.split('#')[-1]
            predicates.add(pred)

    if predicates:
        pattern_parts.append(f"PREDS:{','.join(sorted(predicates)[:5])}")  # Limit to 5

    return '|'.join(pattern_parts) if pattern_parts else 'unknown'


def count_unique_patterns(queries: list[str]) -> dict[str, int]:
    """Cluster SPARQL queries by structural patterns.

    Returns: {pattern_id: count, ...}
    """
    patterns = {}
    for q in queries:
        pattern = extract_query_pattern(q)
        patterns[pattern] = patterns.get(pattern, 0) + 1
    return patterns


def answer_jaccard(answers: list[set]) -> float:
    """Pairwise Jaccard similarity of answer sets.

    For queries returning URI sets, measures how much overlap there is.

    Args:
        answers: List of answer sets (each answer is a set of URIs/values)

    Returns:
        Mean pairwise Jaccard similarity (0.0 = no overlap, 1.0 = identical)
    """
    if len(answers) < 2:
        return 1.0

    pairwise = []
    for i, a1 in enumerate(answers):
        for a2 in answers[i+1:]:
            s1 = set(a1) if not isinstance(a1, set) else a1
            s2 = set(a2) if not isinstance(a2, set) else a2

            intersection = len(s1 & s2)
            union = len(s1 | s2)
            pairwise.append(intersection / union if union > 0 else 1.0)

    return float(np.mean(pairwise))


# =============================================================================
# Level 2: Trajectory Diversity (How did we get there?)
# =============================================================================

def _extract_operations(trajectory: list[dict]) -> set[str]:
    """Extract operations/function calls from a trajectory.

    For trajectory logs, extracts function names from code blocks.
    For tool-based trajectories, extracts tool names.

    Args:
        trajectory: List of trajectory steps

    Returns:
        Set of operation names (function calls, tool names, etc.)
    """
    import re

    operations = set()

    for step in trajectory:
        if not step:
            continue

        # Try to get explicit tool name first
        if 'tool' in step and step['tool']:
            operations.add(step['tool'])
            continue

        # Extract function calls from code
        data = step.get('data', step)
        if isinstance(data, dict) and 'code' in data:
            code = data['code']
            if code:
                # Extract function/method calls: func_name(...) or obj.method(...)
                func_calls = re.findall(r'([a-zA-Z_]\w*)\s*\(', code)
                operations.update(func_calls)

        # Fallback: use event_type if nothing else found
        if not operations and 'event_type' in step:
            # Only use event_type if we haven't found any functions yet
            pass  # Skip event_type to avoid false similarity

    return operations


def trajectory_jaccard(traj1: list[dict], traj2: list[dict]) -> float:
    """Jaccard similarity of operations between two trajectories.

    Extracts function calls from code blocks or tool names.

    Args:
        traj1, traj2: List of trajectory steps

    Returns:
        Jaccard similarity (0.0 = completely different, 1.0 = identical operations)
    """
    ops1 = _extract_operations(traj1)
    ops2 = _extract_operations(traj2)

    # If both empty, consider them identical
    if not ops1 and not ops2:
        return 1.0

    intersection = len(ops1 & ops2)
    union = len(ops1 | ops2)

    return intersection / union if union > 0 else 1.0


def trajectory_edit_distance(traj1: list[dict], traj2: list[dict]) -> int:
    """Levenshtein distance on operation sequences.

    More sensitive to ordering than Jaccard.
    Extracts primary operation from each step's code.

    Args:
        traj1, traj2: List of trajectory steps

    Returns:
        Edit distance (0 = identical, higher = more different)
    """
    import re

    def get_primary_operation(step: dict) -> str:
        """Get the primary operation from a step."""
        if not step:
            return 'unknown'

        # Explicit tool
        if 'tool' in step and step['tool']:
            return step['tool']

        # Extract first function call from code
        data = step.get('data', step)
        if isinstance(data, dict) and 'code' in data:
            code = data['code']
            if code:
                func_calls = re.findall(r'([a-zA-Z_]\w*)\s*\(', code)
                if func_calls:
                    return func_calls[0]  # Primary operation

        # Fallback
        return step.get('event_type', 'unknown')

    seq1 = [get_primary_operation(t) for t in traj1]
    seq2 = [get_primary_operation(t) for t in traj2]

    return _levenshtein_distance(seq1, seq2)


def serialize_trajectory(trajectory: list[dict]) -> str:
    """Serialize trajectory for embedding.

    Concatenates tool names, code snippets, and reasoning from each step.
    """
    parts = []
    for step in trajectory:
        if not step:
            continue

        # Get tool/event type
        tool = step.get('tool', step.get('event_type', ''))
        if tool:
            parts.append(f"[{tool}]")

        # Get code if present
        data = step.get('data', step)
        if isinstance(data, dict):
            code = data.get('code', '')
            if code:
                parts.append(code[:200])  # Limit code length

            reasoning = data.get('reasoning', '')
            if reasoning:
                parts.append(reasoning[:100])  # Limit reasoning length

    return ' '.join(parts)


def trajectory_vendi_score(
    trajectories: list[list[dict]],
    model: str = 'all-MiniLM-L6-v2'
) -> float:
    """Vendi Score on full trajectory embeddings.

    Embed each trajectory as concatenated (tool, code_snippet, reasoning).

    Args:
        trajectories: List of trajectories, each trajectory is a list of step dicts
        model: Sentence transformer model name

    Returns:
        Vendi Score (effective number of distinct trajectories)
    """
    if len(trajectories) < 2:
        return float(len(trajectories))

    # Serialize each trajectory to text
    texts = [serialize_trajectory(t) for t in trajectories]

    # Filter out empty texts
    valid_texts = [t for t in texts if t.strip()]
    if len(valid_texts) < 2:
        return float(len(valid_texts))

    encoder = _get_encoder(model)
    vendi = _get_vendi()

    embeddings = encoder.encode(valid_texts)
    similarities = _cosine_similarity(embeddings)

    return vendi.score_K(similarities)


def find_divergence_point(traj1: list[dict], traj2: list[dict]) -> int:
    """Find first iteration where trajectories diverge.

    Args:
        traj1, traj2: Two trajectories to compare

    Returns:
        Index of first different step (or min length if identical)
    """
    for i, (t1, t2) in enumerate(zip(traj1, traj2)):
        # Compare code blocks
        data1 = t1.get('data', t1) if t1 else {}
        data2 = t2.get('data', t2) if t2 else {}

        code1 = data1.get('code', '') if isinstance(data1, dict) else ''
        code2 = data2.get('code', '') if isinstance(data2, dict) else ''

        if code1 != code2:
            return i

    return min(len(traj1), len(traj2))


def mean_pairwise_jaccard(trajectories: list[list[dict]]) -> float:
    """Compute mean pairwise Jaccard similarity across all trajectories."""
    if len(trajectories) < 2:
        return 1.0

    pairwise = []
    for i, t1 in enumerate(trajectories):
        for t2 in trajectories[i+1:]:
            pairwise.append(trajectory_jaccard(t1, t2))

    return float(np.mean(pairwise))


def mean_edit_distance(trajectories: list[list[dict]]) -> float:
    """Compute mean pairwise edit distance across all trajectories."""
    if len(trajectories) < 2:
        return 0.0

    pairwise = []
    for i, t1 in enumerate(trajectories):
        for t2 in trajectories[i+1:]:
            pairwise.append(trajectory_edit_distance(t1, t2))

    return float(np.mean(pairwise))


# =============================================================================
# Level 3: Decision Point Analysis (Where is genuine uncertainty?)
# =============================================================================

def iteration_diversity(trajectories: list[list[dict]], iteration: int) -> float:
    """Measure diversity of code blocks at a specific iteration.

    High diversity = genuine decision point (like MD transition state).
    Low diversity = deterministic step.

    Args:
        trajectories: List of trajectories
        iteration: Iteration index to analyze

    Returns:
        Diversity score (0.0 = all identical, 1.0 = all different)
    """
    code_blocks = []
    for t in trajectories:
        if iteration < len(t):
            step = t[iteration]
            data = step.get('data', step) if step else {}
            code = data.get('code', '') if isinstance(data, dict) else ''
            code_blocks.append(code)

    if len(code_blocks) < 2:
        return 0.0

    # Compute fraction of unique blocks
    unique_blocks = len(set(code_blocks))
    return unique_blocks / len(code_blocks)


def identify_forking_points(
    trajectories: list[list[dict]],
    threshold: float = 0.5
) -> list[int]:
    """Find iterations where trajectories show high divergence.

    These are analogous to transition states in MD.

    Args:
        trajectories: List of trajectories
        threshold: Diversity threshold to consider a forking point

    Returns:
        List of iteration indices with high diversity
    """
    max_iter = max(len(t) for t in trajectories) if trajectories else 0
    forking_points = []

    for i in range(max_iter):
        diversity = iteration_diversity(trajectories, i)
        if diversity > threshold:
            forking_points.append(i)

    return forking_points


def divergence_statistics(trajectories: list[list[dict]]) -> dict:
    """Analyze where trajectories diverge from each other.

    Returns dict with:
        - mean_divergence_point: Average iteration of first difference
        - std_divergence_point: Standard deviation
        - early_divergers: Count of pairs diverging by iter 3
        - late_divergers: Count of pairs identical until iter 8+
        - never_diverge: Count of identical trajectory pairs
    """
    if len(trajectories) < 2:
        return {
            'mean_divergence_point': 0.0,
            'std_divergence_point': 0.0,
            'early_divergers': 0,
            'late_divergers': 0,
            'never_diverge': len(trajectories),
        }

    max_len = max(len(t) for t in trajectories)
    divergence_points = []

    for i, t1 in enumerate(trajectories):
        for t2 in trajectories[i+1:]:
            dp = find_divergence_point(t1, t2)
            divergence_points.append(dp)

    return {
        'mean_divergence_point': float(np.mean(divergence_points)),
        'std_divergence_point': float(np.std(divergence_points)),
        'early_divergers': sum(1 for d in divergence_points if d <= 3),
        'late_divergers': sum(1 for d in divergence_points if d >= 8),
        'never_diverge': sum(1 for d in divergence_points if d >= max_len),
    }


# =============================================================================
# Level 4: Convergence Diagnostics (Is k large enough?)
# =============================================================================

def diversity_convergence(
    trajectories: list[list[dict]],
    metric: str = 'vendi'
) -> list[float]:
    """Compute diversity as function of number of rollouts.

    Analogous to block averaging in MD - does the metric stabilize?

    Args:
        trajectories: List of trajectories
        metric: 'vendi' or 'unique_patterns'

    Returns:
        List of diversity scores for k=2,3,...,len(trajectories)
    """
    if len(trajectories) < 2:
        return []

    scores = []
    for k in range(2, len(trajectories) + 1):
        subset = trajectories[:k]

        if metric == 'vendi':
            try:
                score = trajectory_vendi_score(subset)
            except ImportError:
                score = float(k)  # Fallback if vendi not available
        elif metric == 'unique_patterns':
            queries = []
            for t in subset:
                # Find final SPARQL from trajectory
                sparql = None
                for step in reversed(t):
                    data = step.get('data', step) if step else {}
                    if isinstance(data, dict) and data.get('sparql'):
                        sparql = data['sparql']
                        break
                if sparql:
                    queries.append(sparql)
            score = float(len(count_unique_patterns(queries)))
        else:
            score = float(k)

        scores.append(score)

    return scores


def effective_trajectory_count(trajectories: list[list[dict]]) -> dict:
    """Vendi Score as effective sample size.

    If Vendi Score = 3.2 with k=10 rollouts, we have ~3.2 "effective"
    distinct trajectories (rest are redundant).

    Ratio effective/actual tells us sampling efficiency.

    Returns dict with:
        - effective_count: Vendi Score
        - actual_count: Number of trajectories
        - efficiency: Ratio (1.0 = all unique, 0.1 = highly redundant)
    """
    actual = len(trajectories)

    if actual < 2:
        return {
            'effective_count': float(actual),
            'actual_count': actual,
            'efficiency': 1.0,
        }

    try:
        vendi = trajectory_vendi_score(trajectories)
    except ImportError:
        vendi = float(actual)  # Fallback

    return {
        'effective_count': vendi,
        'actual_count': actual,
        'efficiency': vendi / actual if actual > 0 else 1.0,
    }


# =============================================================================
# Comprehensive Report
# =============================================================================

@dataclass
class DiversityReport:
    """Comprehensive diversity analysis for a set of trajectories."""

    # Level 1: Outcomes
    sparql_vendi_score: float = 0.0
    unique_query_patterns: int = 0
    answer_jaccard: float = 1.0

    # Level 2: Trajectories
    trajectory_vendi_score: float = 0.0
    mean_pairwise_jaccard: float = 1.0
    mean_edit_distance: float = 0.0

    # Level 3: Decision Points
    forking_points: list[int] = field(default_factory=list)
    mean_divergence_iteration: float = 0.0

    # Level 4: Convergence
    effective_trajectory_count: float = 0.0
    sampling_efficiency: float = 1.0

    # Metadata
    n_trajectories: int = 0

    def summary(self) -> str:
        """Human-readable summary."""
        return f"""
Diversity Report ({self.n_trajectories} trajectories)
{'=' * 50}
Outcome Diversity:
  - SPARQL Vendi Score: {self.sparql_vendi_score:.2f} effective queries
  - Unique patterns: {self.unique_query_patterns}
  - Answer overlap (Jaccard): {self.answer_jaccard:.2f}

Trajectory Diversity:
  - Trajectory Vendi Score: {self.trajectory_vendi_score:.2f} effective trajectories
  - Mean pairwise Jaccard: {self.mean_pairwise_jaccard:.2f}
  - Mean edit distance: {self.mean_edit_distance:.1f}

Decision Points:
  - Forking iterations: {self.forking_points}
  - Mean divergence at iteration: {self.mean_divergence_iteration:.1f}

Sampling Efficiency:
  - Effective count: {self.effective_trajectory_count:.2f}
  - Efficiency: {self.sampling_efficiency:.1%}
"""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'sparql_vendi_score': self.sparql_vendi_score,
            'unique_query_patterns': self.unique_query_patterns,
            'answer_jaccard': self.answer_jaccard,
            'trajectory_vendi_score': self.trajectory_vendi_score,
            'mean_pairwise_jaccard': self.mean_pairwise_jaccard,
            'mean_edit_distance': self.mean_edit_distance,
            'forking_points': self.forking_points,
            'mean_divergence_iteration': self.mean_divergence_iteration,
            'effective_trajectory_count': self.effective_trajectory_count,
            'sampling_efficiency': self.sampling_efficiency,
            'n_trajectories': self.n_trajectories,
        }


def compute_diversity_report(
    trajectories: list[list[dict]],
    queries: list[str] = None,
    answers: list[set] = None,
    forking_threshold: float = 0.5,
) -> DiversityReport:
    """Compute full diversity analysis for a set of trajectories.

    Args:
        trajectories: List of trajectories, each trajectory is a list of step dicts
        queries: Optional list of SPARQL queries (one per trajectory)
        answers: Optional list of answer sets (one per trajectory)
        forking_threshold: Threshold for identifying forking points

    Returns:
        DiversityReport with all metrics computed
    """
    n = len(trajectories)

    if n == 0:
        return DiversityReport(n_trajectories=0)

    if n == 1:
        return DiversityReport(
            n_trajectories=1,
            effective_trajectory_count=1.0,
            sampling_efficiency=1.0,
        )

    # Level 1: Outcomes
    if queries:
        valid_queries = [q for q in queries if q]
        try:
            sq_vendi = sparql_vendi_score(valid_queries) if len(valid_queries) >= 2 else float(len(valid_queries))
        except ImportError:
            sq_vendi = float(len(valid_queries))
        patterns = count_unique_patterns(valid_queries)
        unique_patterns = len(patterns)
    else:
        sq_vendi = 0.0
        unique_patterns = 0

    if answers:
        ans_jaccard = answer_jaccard(answers)
    else:
        ans_jaccard = 1.0

    # Level 2: Trajectories
    try:
        traj_vendi = trajectory_vendi_score(trajectories)
    except ImportError:
        traj_vendi = float(n)

    mpj = mean_pairwise_jaccard(trajectories)
    med = mean_edit_distance(trajectories)

    # Level 3: Decision Points
    fp = identify_forking_points(trajectories, threshold=forking_threshold)
    div_stats = divergence_statistics(trajectories)

    # Level 4: Convergence
    eff = effective_trajectory_count(trajectories)

    return DiversityReport(
        # Level 1
        sparql_vendi_score=sq_vendi,
        unique_query_patterns=unique_patterns,
        answer_jaccard=ans_jaccard,
        # Level 2
        trajectory_vendi_score=traj_vendi,
        mean_pairwise_jaccard=mpj,
        mean_edit_distance=med,
        # Level 3
        forking_points=fp,
        mean_divergence_iteration=div_stats['mean_divergence_point'],
        # Level 4
        effective_trajectory_count=eff['effective_count'],
        sampling_efficiency=eff['efficiency'],
        # Metadata
        n_trajectories=n,
    )


# =============================================================================
# Trajectory Loading Utilities
# =============================================================================

def load_trajectory(log_path: str) -> list[dict]:
    """Load trajectory from JSONL log file.

    Args:
        log_path: Path to .jsonl trajectory log file

    Returns:
        List of trajectory events (dicts)
    """
    events = []
    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def extract_iterations(trajectory: list[dict]) -> list[dict]:
    """Extract iteration events from a trajectory.

    Filters to only 'iteration' events which contain code/reasoning.
    """
    return [e for e in trajectory if e.get('event_type') == 'iteration']


def extract_sparql_from_trajectory(trajectory: list[dict]) -> str | None:
    """Extract final SPARQL query from trajectory."""
    for event in reversed(trajectory):
        if event.get('event_type') == 'run_complete':
            data = event.get('data', {})
            return data.get('sparql')
    return None


def extract_answer_from_trajectory(trajectory: list[dict]) -> str | None:
    """Extract final answer from trajectory."""
    for event in reversed(trajectory):
        if event.get('event_type') == 'run_complete':
            data = event.get('data', {})
            return data.get('answer_preview') or data.get('answer')
    return None
