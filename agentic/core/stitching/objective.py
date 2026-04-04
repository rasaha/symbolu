"""
Stitching Objective Function
============================

STATUS: LEGACY COMPATIBILITY WRAPPER — DEPRECATED
==================================================
This module exists solely for backward compatibility.
The canonical implementation lives in
``agentic.core.stitching.stitching_engine.StitchingEngine``.

New code should import ``StitchingEngine`` directly::

    from agentic.core.stitching import StitchingEngine

This wrapper delegates all work to ``StitchingEngine`` internally.
It may be removed in a future release.

Patent Reference:
    Claim [2] - Relevance scoring with resonance coupling
"""

import warnings
from typing import Dict, Any, Optional


class StitchingObjective:
    """
    .. deprecated::
        Use ``StitchingEngine.score_candidates()`` directly instead.

    Legacy backward-compatibility wrapper around
    :class:`~agentic.core.stitching.stitching_engine.StitchingEngine`.
    """

    def __init__(self):
        """Initialize objective function."""
        warnings.warn(
            "StitchingObjective is deprecated. "
            "Use StitchingEngine.score_candidates() directly.",
            DeprecationWarning,
            stacklevel=2,
        )
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
