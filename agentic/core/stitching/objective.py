"""
Stitching Objective Function
============================

Legacy wrapper for backwards compatibility.
The actual scoring is now implemented in stitching_engine.py.

Patent Reference:
    Claim [2] - Relevance scoring with resonance coupling
"""

from typing import Dict, Any, Optional


class StitchingObjective:
    """
    Defines the objective function for stitching optimization.

    This class provides backwards compatibility. The actual implementation
    is in StitchingEngine.score_candidates().

    The objective function is:
        Score(c) = Relevance(c) - Redundancy(c) - DomainJumpPenalty(c)
    """

    def __init__(self):
        """Initialize objective function."""
        # Import here to avoid circular imports
        from agentic.core.stitching.stitching_engine import StitchingEngine
        self._engine = StitchingEngine()

    def compute_objective(
        self,
        candidate: Any,
        context: Dict[str, Any],
    ) -> float:
        """
        Compute objective score for a candidate.

        Args:
            candidate: The candidate to score
            context: Dictionary with query context including:
                - text: Query text
                - domain: Query domain
                - aspect_vector: Query aspect vector (optional)

        Returns:
            Objective score for the candidate
        """
        from agentic.core.stitching.stitching_engine import QueryContext

        # Convert dict context to QueryContext
        query_context = QueryContext(
            text=context.get("text", ""),
            domain=context.get("domain", "generic"),
            aspect_vector=context.get("aspect_vector", {}),
        )

        # Score the single candidate
        scored = self._engine.score_candidates([candidate], query_context)

        if scored:
            return scored[0].final_score
        return 0.0


__all__ = ["StitchingObjective"]
