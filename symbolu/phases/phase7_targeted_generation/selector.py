"""
Phase-7 Targeted Generation - Result Selection

Ranks and selects final results deterministically.
"""

from typing import List, Tuple

from .types import (
    TrajectoryResult,
    RankedResult,
    SelectionConfig,
    ScoringMode,
)


def select_results(
    scored_results: List[Tuple[Tuple[str, ...], TrajectoryResult, float]],
    config: SelectionConfig,
) -> Tuple[RankedResult, ...]:
    """
    Rank and select final results.

    Args:
        scored_results: List of (sequence, trajectory, score) tuples
        config: Selection configuration

    Returns:
        Tuple of RankedResult (immutable, ordered)

    Notes:
        - Ordering is deterministic
        - Ties broken by lexicographic sequence order
        - Respects max_results and score_threshold
    """
    if not scored_results:
        return tuple()

    # Sort by score
    sorted_results = rank_by_score(scored_results, config.scoring_mode)

    # Apply score threshold filter
    if config.score_threshold is not None:
        if config.scoring_mode == ScoringMode.BINARY:
            # Binary: keep scores >= threshold
            sorted_results = [
                r for r in sorted_results if r[2] >= config.score_threshold
            ]
        else:
            # Distance: keep scores <= threshold (lower is better)
            sorted_results = [
                r for r in sorted_results if r[2] <= config.score_threshold
            ]

    # Apply max_results limit
    if config.max_results is not None and len(sorted_results) > config.max_results:
        sorted_results = sorted_results[:config.max_results]

    # Convert to RankedResult
    ranked = []
    for i, (sequence, trajectory, score) in enumerate(sorted_results):
        ranked.append(RankedResult(
            sequence=sequence,
            trajectory=trajectory,
            score=score,
            rank=i + 1,
        ))

    return tuple(ranked)


def rank_by_score(
    results: List[Tuple[Tuple[str, ...], TrajectoryResult, float]],
    mode: ScoringMode,
) -> List[Tuple[Tuple[str, ...], TrajectoryResult, float]]:
    """
    Sort results by score.

    Args:
        results: Unordered results
        mode: Scoring mode (determines sort direction)

    Returns:
        Sorted list:
        - Binary mode: descending (1.0 first)
        - Distance mode: ascending (0.0 first)
    """
    if mode == ScoringMode.BINARY:
        # Descending by score, then lexicographic by sequence for ties
        return sorted(
            results,
            key=lambda r: (-r[2], r[0]),  # -score for descending, sequence for tie-breaking
        )
    else:
        # Ascending by score (distance), then lexicographic by sequence for ties
        return sorted(
            results,
            key=lambda r: (r[2], r[0]),  # score ascending, sequence for tie-breaking
        )


def break_ties(
    tied_results: List[Tuple[Tuple[str, ...], TrajectoryResult, float]],
) -> List[Tuple[Tuple[str, ...], TrajectoryResult, float]]:
    """
    Deterministically order tied results.

    Args:
        tied_results: Results with equal scores

    Returns:
        Lexicographically ordered results
    """
    return sorted(tied_results, key=lambda r: r[0])
