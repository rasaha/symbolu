"""
Stitching Penalties - Redundancy and Domain Jump Calculations
==============================================================

This module implements the penalty functions for the Stitching Encoder's
constrained optimization objective:

    maximize   Σ Relevance(c)
    minimize   Redundancy(c) + DomainJumpPenalty(c)

Patent Reference:
    - Redundancy Penalty: Prevents shallow analogies that restate same structure
    - Domain-Jump Penalty: Prices (not blocks) cross-domain transitions

Key Design Principle:
    Domain jumps are PRICED, not eliminated. This allows controlled
    cross-domain analogies while preventing runaway domain sprawl.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

from agentic.core.stitching.domain_distance import (
    get_domain_distance,
    get_domain_distance_with_context,
    get_aspect_overlap,
    is_cross_domain,
)


# =============================================================================
# Penalty Configuration
# =============================================================================

@dataclass
class PenaltyConfig:
    """Configuration for penalty calculations."""

    # Domain-jump penalty
    domain_jump_lambda: float = 0.30  # Weight for domain jump penalty

    # Redundancy penalty weights
    alpha_semantic: float = 0.50  # Semantic similarity weight
    alpha_aspect: float = 0.30    # Aspect overlap weight
    alpha_template: float = 0.20  # Template match weight

    # Thresholds
    min_redundancy_threshold: float = 0.70  # Above this = redundant
    max_domain_jumps: int = 3  # Hard cap on cross-domain candidates

    # Context adjustments
    enable_context_adjustment: bool = True
    confidence_floor: float = 0.3  # Min confidence for consideration


# Default configuration
DEFAULT_CONFIG = PenaltyConfig()


# =============================================================================
# Penalty Calculator
# =============================================================================

class PenaltyCalculator:
    """
    Calculates penalties for candidate scoring in the Stitching Encoder.

    This class implements two key penalty functions:
    1. Redundancy Penalty - prevents shallow analogies
    2. Domain-Jump Penalty - prices cross-domain transitions

    Both penalties contribute to the constrained optimization objective
    that selects optimal candidates while maintaining coherence.
    """

    def __init__(self, config: Optional[PenaltyConfig] = None):
        """Initialize with optional custom configuration."""
        self.config = config or DEFAULT_CONFIG

    def redundancy_penalty(
        self,
        candidate: Any,
        selected: List[Any],
    ) -> float:
        """
        Calculate redundancy penalty for a candidate against already-selected candidates.

        Formula:
            Redundancy(c, Selected) = max(
                α_sem × cosine_sim(c.embedding, s.embedding) +
                α_asp × aspect_overlap(c, s) +
                α_tmp × same_template(c, s)
            )

        This penalty:
        - Is GLOBAL across all selected candidates
        - Prevents shallow analogies that restate the same idea
        - Encourages structurally diverse selections

        Args:
            candidate: The candidate to evaluate
            selected: List of already-selected candidates

        Returns:
            Redundancy penalty in range [0, 1]
            - 0.0: Completely novel
            - 0.5: Moderately similar
            - 1.0: Highly redundant (same structure)
        """
        if not selected:
            return 0.0

        max_similarity = 0.0

        for sel in selected:
            similarity = self._compute_pairwise_redundancy(candidate, sel)
            max_similarity = max(max_similarity, similarity)

        return max_similarity

    def _compute_pairwise_redundancy(
        self,
        candidate_a: Any,
        candidate_b: Any,
    ) -> float:
        """
        Compute redundancy between two candidates.

        Combines three signals:
        1. Semantic similarity (via embeddings)
        2. Aspect overlap (via aspect vectors)
        3. Template match (via template IDs)
        """
        scores = []

        # 1. Semantic similarity from embeddings
        semantic_sim = self._compute_embedding_similarity(
            getattr(candidate_a, "embedding", None),
            getattr(candidate_b, "embedding", None),
        )
        scores.append(self.config.alpha_semantic * semantic_sim)

        # 2. Aspect overlap
        aspect_sim = get_aspect_overlap(
            getattr(candidate_a, "aspect_vector", {}),
            getattr(candidate_b, "aspect_vector", {}),
        )
        scores.append(self.config.alpha_aspect * aspect_sim)

        # 3. Template match
        template_match = self._compute_template_match(
            getattr(candidate_a, "template_id", None),
            getattr(candidate_b, "template_id", None),
        )
        scores.append(self.config.alpha_template * template_match)

        return sum(scores)

    def _compute_embedding_similarity(
        self,
        embedding_a: Optional[List[float]],
        embedding_b: Optional[List[float]],
    ) -> float:
        """Compute cosine similarity between embeddings."""
        if not embedding_a or not embedding_b:
            return 0.0

        if len(embedding_a) != len(embedding_b):
            return 0.0

        # Dot product
        dot = sum(a * b for a, b in zip(embedding_a, embedding_b))

        # Magnitudes
        mag_a = sum(a * a for a in embedding_a) ** 0.5
        mag_b = sum(b * b for b in embedding_b) ** 0.5

        if mag_a == 0 or mag_b == 0:
            return 0.0

        # Cosine similarity (can be negative, clamp to [0, 1])
        cosine = dot / (mag_a * mag_b)
        return max(0.0, cosine)

    def _compute_template_match(
        self,
        template_a: Optional[str],
        template_b: Optional[str],
    ) -> float:
        """Check if two candidates use the same template."""
        if not template_a or not template_b:
            return 0.0
        return 1.0 if template_a == template_b else 0.0

    def domain_jump_penalty(
        self,
        candidate: Any,
        query_domain: str,
    ) -> float:
        """
        Calculate domain-jump penalty for a candidate.

        Formula:
            DomainJumpPenalty(c) = λ × domain_distance(query_domain, candidate_domain)

        This penalty:
        - PRICES domain jumps, does NOT block them
        - Uses symbolic (not embedding) distance
        - Allows controlled cross-domain analogies

        Args:
            candidate: The candidate to evaluate
            query_domain: The domain of the original query

        Returns:
            Domain-jump penalty in range [0, λ]
            - 0.0: Same domain (no penalty)
            - λ × 0.3: Related domains (low penalty)
            - λ × 0.7: Distant domains (high penalty)
        """
        candidate_domain = getattr(candidate, "domain", "generic") or "generic"

        # Same domain = no penalty
        if not is_cross_domain(query_domain, candidate_domain):
            return 0.0

        # Get base distance
        base_distance = get_domain_distance(query_domain, candidate_domain)

        # Apply context adjustment if enabled
        if self.config.enable_context_adjustment:
            # Get aspect overlap and confidence for adjustment
            aspect_vector = getattr(candidate, "aspect_vector", {})
            confidence = getattr(candidate, "confidence", 1.0)

            # High aspect overlap can reduce penalty
            # (indicates structural similarity despite domain difference)
            if aspect_vector:
                # Assume query aspects would be similar - use candidate's as proxy
                # In practice, query aspect vector would be passed in
                base_distance = get_domain_distance_with_context(
                    query_domain,
                    candidate_domain,
                    aspect_overlap=0.0,  # Will be computed with actual query aspects
                    confidence=confidence,
                )

        # Apply lambda weight
        return self.config.domain_jump_lambda * base_distance

    def domain_jump_penalty_with_query_aspects(
        self,
        candidate: Any,
        query_domain: str,
        query_aspect_vector: Dict[str, float],
    ) -> float:
        """
        Calculate domain-jump penalty with query aspect consideration.

        This is the full implementation that considers aspect overlap
        between the query and candidate to adjust the penalty.

        High aspect overlap (structural similarity) reduces the penalty,
        allowing structurally-similar cross-domain transfers.

        Args:
            candidate: The candidate to evaluate
            query_domain: The domain of the original query
            query_aspect_vector: Aspect vector from query analysis

        Returns:
            Adjusted domain-jump penalty
        """
        candidate_domain = getattr(candidate, "domain", "generic") or "generic"

        # Same domain = no penalty
        if not is_cross_domain(query_domain, candidate_domain):
            return 0.0

        # Compute aspect overlap
        candidate_aspects = getattr(candidate, "aspect_vector", {})
        aspect_overlap = get_aspect_overlap(query_aspect_vector, candidate_aspects)

        # Get confidence
        confidence = getattr(candidate, "confidence", 1.0)

        # Get adjusted distance
        adjusted_distance = get_domain_distance_with_context(
            query_domain,
            candidate_domain,
            aspect_overlap=aspect_overlap,
            confidence=confidence,
        )

        # Apply lambda weight
        return self.config.domain_jump_lambda * adjusted_distance

    def compute_all_penalties(
        self,
        candidate: Any,
        selected: List[Any],
        query_domain: str,
        query_aspect_vector: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Compute all penalties for a candidate.

        Returns a breakdown for audit/explainability.

        Args:
            candidate: The candidate to evaluate
            selected: List of already-selected candidates
            query_domain: The domain of the original query
            query_aspect_vector: Optional aspect vector from query

        Returns:
            Dictionary with penalty breakdown:
            {
                "redundancy": float,
                "domain_jump": float,
                "total": float,
                "is_cross_domain": bool,
                "domain_distance": float,
            }
        """
        # Compute redundancy penalty
        redundancy = self.redundancy_penalty(candidate, selected)

        # Compute domain-jump penalty
        if query_aspect_vector:
            domain_jump = self.domain_jump_penalty_with_query_aspects(
                candidate, query_domain, query_aspect_vector
            )
        else:
            domain_jump = self.domain_jump_penalty(candidate, query_domain)

        # Get domain info for audit
        candidate_domain = getattr(candidate, "domain", "generic") or "generic"
        is_cross = is_cross_domain(query_domain, candidate_domain)
        distance = get_domain_distance(query_domain, candidate_domain)

        return {
            "redundancy": redundancy,
            "domain_jump": domain_jump,
            "total": redundancy + domain_jump,
            "is_cross_domain": is_cross,
            "domain_distance": distance,
            "candidate_domain": candidate_domain,
            "query_domain": query_domain,
        }

    def is_too_redundant(
        self,
        candidate: Any,
        selected: List[Any],
    ) -> bool:
        """Check if a candidate is too redundant to include."""
        redundancy = self.redundancy_penalty(candidate, selected)
        return redundancy >= self.config.min_redundancy_threshold


# =============================================================================
# Scoring Result for Audit Trail
# =============================================================================

@dataclass
class ScoredCandidate:
    """
    A candidate with computed scores and penalties.

    Used for audit trail and explainability.
    """
    candidate: Any
    relevance: float
    penalties: Dict[str, float]
    final_score: float
    rank: int = 0

    @property
    def is_cross_domain(self) -> bool:
        return self.penalties.get("is_cross_domain", False)

    @property
    def redundancy_penalty(self) -> float:
        return self.penalties.get("redundancy", 0.0)

    @property
    def domain_jump_penalty(self) -> float:
        return self.penalties.get("domain_jump", 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/audit."""
        return {
            "candidate_id": getattr(self.candidate, "id", "unknown"),
            "text_preview": getattr(self.candidate, "text", "")[:100],
            "domain": getattr(self.candidate, "domain", "generic"),
            "relevance": self.relevance,
            "penalties": self.penalties,
            "final_score": self.final_score,
            "rank": self.rank,
        }


# =============================================================================
# Constraint Definitions
# =============================================================================

@dataclass
class StitchingConstraints:
    """
    Constraints for the stitching optimization.

    These are hard constraints that filter candidates before scoring.
    """
    min_confidence: float = 0.3
    max_entropy: float = 0.9
    max_domain_jumps: int = 3
    min_score: float = 0.1
    max_candidates: int = 10

    def passes(self, candidate: Any, domain_jump_count: int) -> Tuple[bool, str]:
        """
        Check if a candidate passes all constraints.

        Returns:
            (passes, reason) tuple
        """
        # Confidence check
        confidence = getattr(candidate, "confidence", 1.0)
        if confidence < self.min_confidence:
            return False, f"confidence {confidence:.2f} < {self.min_confidence}"

        # Entropy check
        entropy = getattr(candidate, "entropy", 0.0)
        if entropy > self.max_entropy:
            return False, f"entropy {entropy:.2f} > {self.max_entropy}"

        # Domain jump cap
        if domain_jump_count >= self.max_domain_jumps:
            candidate_domain = getattr(candidate, "domain", "generic")
            return False, f"domain jump cap reached ({self.max_domain_jumps})"

        return True, "passed"


__all__ = [
    "PenaltyCalculator",
    "PenaltyConfig",
    "ScoredCandidate",
    "StitchingConstraints",
    "DEFAULT_CONFIG",
]
