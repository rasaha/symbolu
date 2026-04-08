"""
Candidate Pre-Filter
====================

Uses phoneme resonance to pre-filter candidates before expensive
transformer inference.

Key Insight:
    If phoneme similarity is low, semantic similarity is unlikely.
    Filter first with cheap 10D computation, then run transformer
    only on promising candidates.

Computational Savings:
    - 50,000 candidates × transformer inference = EXPENSIVE
    - 50,000 candidates × phoneme filter = CHEAP → 500 candidates
    - 500 candidates × transformer inference = 100x less work
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional, Callable, Iterator
import time

from symbolu_core.resonance import (
    analyze_word,
    compare_words,
    WordVector,
    ResonanceResult,
)


@dataclass(frozen=True)
class FilterResult:
    """Result of candidate filtering."""
    candidate: str
    phoneme_score: float
    passed: bool
    vector: Optional[WordVector] = None


@dataclass(frozen=True)
class FilterStats:
    """Statistics from a filtering operation."""
    total_candidates: int
    passed_candidates: int
    rejected_candidates: int
    filter_time_ms: float
    candidates_per_ms: float
    reduction_ratio: float  # passed / total


class CandidatePreFilter:
    """
    Pre-filters candidates using phoneme resonance.

    Use this before expensive transformer inference to reduce
    the candidate set by 10-100x.

    Attributes:
        threshold: Minimum phoneme similarity to pass (0.0 to 1.0)
        top_k: If set, keep only top K candidates by score
    """

    def __init__(
        self,
        threshold: float = 0.5,
        top_k: Optional[int] = None,
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        self.threshold = threshold
        self.top_k = top_k
        self._target_cache: dict = {}

    def filter(
        self,
        candidates: Tuple[str, ...],
        target: str,
        return_scores: bool = False,
    ) -> Tuple[str, ...]:
        """
        Filter candidates by phoneme similarity to target.

        Args:
            candidates: Candidate words/phrases to filter
            target: Target word/phrase to compare against
            return_scores: If True, return (candidate, score) tuples

        Returns:
            Filtered candidates that pass threshold
        """
        results = list(self._score_candidates(candidates, target))

        # Filter by threshold
        passed = [r for r in results if r.passed]

        # Apply top_k if set
        if self.top_k is not None and len(passed) > self.top_k:
            passed = sorted(passed, key=lambda r: r.phoneme_score, reverse=True)
            passed = passed[:self.top_k]

        if return_scores:
            return tuple((r.candidate, r.phoneme_score) for r in passed)
        return tuple(r.candidate for r in passed)

    def filter_with_stats(
        self,
        candidates: Tuple[str, ...],
        target: str,
    ) -> Tuple[Tuple[str, ...], FilterStats]:
        """
        Filter candidates and return statistics.

        Args:
            candidates: Candidate words/phrases to filter
            target: Target word/phrase to compare against

        Returns:
            Tuple of (filtered_candidates, statistics)
        """
        start_time = time.perf_counter()

        results = list(self._score_candidates(candidates, target))
        passed = [r for r in results if r.passed]

        if self.top_k is not None and len(passed) > self.top_k:
            passed = sorted(passed, key=lambda r: r.phoneme_score, reverse=True)
            passed = passed[:self.top_k]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        stats = FilterStats(
            total_candidates=len(candidates),
            passed_candidates=len(passed),
            rejected_candidates=len(candidates) - len(passed),
            filter_time_ms=elapsed_ms,
            candidates_per_ms=len(candidates) / elapsed_ms if elapsed_ms > 0 else 0,
            reduction_ratio=len(passed) / len(candidates) if candidates else 0,
        )

        return tuple(r.candidate for r in passed), stats

    def _score_candidates(
        self,
        candidates: Tuple[str, ...],
        target: str,
    ) -> Iterator[FilterResult]:
        """Score each candidate against target."""
        # Cache target vector
        if target not in self._target_cache:
            self._target_cache[target] = analyze_word(target)
        target_vec = self._target_cache[target]

        for candidate in candidates:
            candidate_vec = analyze_word(candidate)
            resonance = compare_words(candidate, target)

            yield FilterResult(
                candidate=candidate,
                phoneme_score=resonance.similarity,
                passed=resonance.similarity >= self.threshold,
                vector=candidate_vec,
            )

    def estimate_savings(
        self,
        num_candidates: int,
        transformer_ms_per_candidate: float = 10.0,
        expected_pass_rate: float = 0.1,
    ) -> dict:
        """
        Estimate computational savings from pre-filtering.

        Args:
            num_candidates: Number of candidates to filter
            transformer_ms_per_candidate: Transformer inference time per candidate
            expected_pass_rate: Expected fraction that will pass filter

        Returns:
            Dict with time savings estimates
        """
        # Without filter: run transformer on all
        without_filter_ms = num_candidates * transformer_ms_per_candidate

        # With filter: phoneme filter + transformer on passed
        # Phoneme filter is ~0.01ms per candidate
        filter_ms = num_candidates * 0.01
        passed = int(num_candidates * expected_pass_rate)
        transformer_ms = passed * transformer_ms_per_candidate
        with_filter_ms = filter_ms + transformer_ms

        return {
            "without_filter_ms": without_filter_ms,
            "with_filter_ms": with_filter_ms,
            "time_saved_ms": without_filter_ms - with_filter_ms,
            "speedup_factor": without_filter_ms / with_filter_ms if with_filter_ms > 0 else 0,
            "candidates_before": num_candidates,
            "candidates_after": passed,
            "transformer_calls_saved": num_candidates - passed,
        }


class BatchPreFilter:
    """
    Batch pre-filter for multiple targets.

    Useful when you have multiple queries and want to filter
    a shared candidate set for each.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        top_k_per_target: Optional[int] = None,
    ):
        self.base_filter = CandidatePreFilter(threshold=threshold, top_k=top_k_per_target)
        self._candidate_cache: dict = {}

    def precompute_candidates(self, candidates: Tuple[str, ...]):
        """
        Pre-compute vectors for all candidates.

        Call this once, then filter against multiple targets.
        """
        for candidate in candidates:
            if candidate not in self._candidate_cache:
                self._candidate_cache[candidate] = analyze_word(candidate)

    def filter_for_targets(
        self,
        candidates: Tuple[str, ...],
        targets: Tuple[str, ...],
    ) -> dict:
        """
        Filter candidates for multiple targets.

        Args:
            candidates: Shared candidate set
            targets: Multiple target words

        Returns:
            Dict mapping target → filtered candidates
        """
        # Precompute if not done
        self.precompute_candidates(candidates)

        results = {}
        for target in targets:
            filtered = self.base_filter.filter(candidates, target)
            results[target] = filtered

        return results


class ProgressiveFilter:
    """
    Progressive filtering with multiple thresholds.

    Applies increasingly strict filters to progressively
    reduce the candidate set.

    Stages:
    1. Loose filter (0.3) → 30% candidates
    2. Medium filter (0.5) → 10% candidates
    3. Strict filter (0.7) → 3% candidates
    4. Transformer on final 3%
    """

    def __init__(
        self,
        thresholds: Tuple[float, ...] = (0.3, 0.5, 0.7),
    ):
        self.thresholds = sorted(thresholds)
        self.filters = [
            CandidatePreFilter(threshold=t) for t in self.thresholds
        ]

    def filter_progressive(
        self,
        candidates: Tuple[str, ...],
        target: str,
    ) -> List[Tuple[int, Tuple[str, ...]]]:
        """
        Apply progressive filtering.

        Returns list of (stage, remaining_candidates) at each stage.
        """
        stages = [(0, candidates)]
        current = candidates

        for i, filt in enumerate(self.filters):
            current = filt.filter(current, target)
            stages.append((i + 1, current))
            if not current:
                break

        return stages
