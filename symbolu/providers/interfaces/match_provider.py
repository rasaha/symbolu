"""
Match Provider Interface
========================

Abstract interface for canonical matching (C × R × S framework).

Enterprise mode uses the canonical matcher from name_resonance.
This provides pairwise word/term matching with:
- C (Constraint): Phonemic → ontological feasibility
- R (Realization): Phonemic → experiential strength
- S (Referent): Non-phonemic referential coherence

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Dict, Any, List


class MatchMode(Enum):
    """Classification of canonical match based on C × R × S."""
    TRUE_MATCH = "true_match"           # High C, High R, High S
    LATENT = "latent"                   # High C, Low R, High S
    DISTORTED = "distorted"             # Low C, High R, High S
    NON_MATCH = "non_match"             # Low C, Low R, or Low S
    REFERENT_MISMATCH = "ref_mismatch"  # Any C/R, but Low S


@dataclass(frozen=True)
class MatchResult:
    """
    Result of canonical matching between two terms.

    The core formula: MATCH = C × R × S

    This structure provides:
    - Source independence (S is non-phonemic)
    - Full diagnostic visibility
    - Classification for downstream use

    Attributes:
        match_score: The C × R × S product (0.0 to 1.0)
        feasibility: C - constraint satisfaction score
        realization: R - manifestation strength score
        referent: S - referential coherence score
        mode: Classification of the match
        term_a: First term being matched
        term_b: Second term being matched
        confidence: Confidence based on C/R/S alignment
        diagnostics: Detailed analysis for auditing
    """
    match_score: float
    feasibility: float      # C
    realization: float      # R
    referent: float         # S
    mode: MatchMode
    term_a: str
    term_b: str
    confidence: float
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "match_score": self.match_score,
            "components": {
                "C": self.feasibility,
                "R": self.realization,
                "S": self.referent,
            },
            "mode": self.mode.value,
            "term_a": self.term_a,
            "term_b": self.term_b,
            "confidence": self.confidence,
            "diagnostics": self.diagnostics,
        }

    @property
    def is_match(self) -> bool:
        """True if mode indicates a valid match."""
        return self.mode in (MatchMode.TRUE_MATCH, MatchMode.LATENT)

    @property
    def is_referent_grounded(self) -> bool:
        """True if S is not based on UNKNOWN referent."""
        return self.mode != MatchMode.REFERENT_MISMATCH


@dataclass(frozen=True)
class BatchMatchResult:
    """
    Result of batch canonical matching.

    Contains multiple pairwise match results, sorted by score.

    Attributes:
        results: Tuple of MatchResult objects (sorted by score desc)
        stats: Batch-level statistics
    """
    results: Tuple[MatchResult, ...]
    stats: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "results": [r.to_dict() for r in self.results],
            "stats": self.stats,
        }

    @property
    def count(self) -> int:
        """Return number of match results."""
        return len(self.results)

    def top_k(self, k: int) -> "BatchMatchResult":
        """Return a new BatchMatchResult with only top k results."""
        if k >= len(self.results):
            return self
        return BatchMatchResult(
            results=self.results[:k],
            stats={**self.stats, "truncated_to": k},
        )

    def filter_by_mode(self, mode: MatchMode) -> "BatchMatchResult":
        """Return results filtered to a specific mode."""
        filtered = tuple(r for r in self.results if r.mode == mode)
        return BatchMatchResult(
            results=filtered,
            stats={**self.stats, "filtered_by_mode": mode.value},
        )

    def above_threshold(self, threshold: float) -> "BatchMatchResult":
        """Return results above a match score threshold."""
        filtered = tuple(r for r in self.results if r.match_score >= threshold)
        return BatchMatchResult(
            results=filtered,
            stats={**self.stats, "threshold": threshold},
        )


class MatchProvider(ABC):
    """
    Abstract interface for canonical matching.

    Match providers compute pairwise resonance between terms using
    the C × R × S framework. This enables:
    - Word-to-word semantic matching (full S discrimination)
    - Name-to-name phonetic matching (S neutral at 0.5)
    - Post-generation coherence auditing

    All implementations are Tier 1 with zero governance authority.
    """

    @abstractmethod
    def match(self, term_a: str, term_b: str) -> MatchResult:
        """
        Compute canonical match between two terms.

        MATCH = C × R × S

        Args:
            term_a: First term
            term_b: Second term

        Returns:
            MatchResult with score, components, and diagnostics
        """
        pass

    @abstractmethod
    def match_batch(
        self,
        pairs: List[Tuple[str, str]],
    ) -> BatchMatchResult:
        """
        Batch match multiple term pairs.

        Args:
            pairs: List of (term_a, term_b) tuples

        Returns:
            BatchMatchResult with all pairwise results
        """
        pass

    @abstractmethod
    def match_one_to_many(
        self,
        query: str,
        candidates: Tuple[str, ...],
        top_k: int = 10,
    ) -> BatchMatchResult:
        """
        Match a query term against multiple candidates.

        Args:
            query: The query term
            candidates: Tuple of candidate terms to match against
            top_k: Maximum number of results to return

        Returns:
            BatchMatchResult sorted by match score (descending)
        """
        pass

    def get_thresholds(self) -> Dict[str, float]:
        """
        Return the threshold configuration.

        Returns:
            Dict with C_THRESHOLD, R_THRESHOLD, S_THRESHOLD
        """
        return {
            "C_THRESHOLD": 0.6,
            "R_THRESHOLD": 0.5,
            "S_THRESHOLD": 0.2,
        }
