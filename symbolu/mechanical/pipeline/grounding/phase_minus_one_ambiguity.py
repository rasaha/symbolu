"""
Phase −1.1: Ambiguity Resolver (ARL)

Resolves multiple grounding candidates into a single selection or
determines that clarification is needed.

Resolution Rules:
1. If top.confidence >= CONFIDENCE_THRESHOLD → CONFIDENT, select top
2. If top - second < DELTA_THRESHOLD → AMBIGUOUS, ASK_CLARIFY
3. Else → AMBIGUOUS, SAFE_DEFAULT with conservative constraints

Safety Invariants:
- If projection_risk == HIGH and would allow analysis → force analysis_allowed = False
- Never select a candidate that would enable unsafe analytical operations
- Prefer ASK_CLARIFY over potentially unsafe defaults
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .phase_minus_one_schema import (
    GroundingCandidate,
    GroundingStatus,
    ProjectionRisk,
    ResolutionPolicy,
)


@dataclass
class AmbiguityResolution:
    """
    Result of ambiguity resolution.

    Attributes:
        selected: The selected candidate (may be None if ASK_CLARIFY)
        status: Resolution status (CONFIDENT/AMBIGUOUS/CONFLICTED)
        policy: Resolution policy (NONE/ASK_CLARIFY/SAFE_DEFAULT)
        top_candidates: Top 2 candidates considered
        confidence_delta: Difference between top 2 (if applicable)
        safety_override_applied: Whether a safety override was applied
    """
    selected: Optional[GroundingCandidate]
    status: GroundingStatus
    policy: ResolutionPolicy
    top_candidates: List[GroundingCandidate]
    confidence_delta: float
    safety_override_applied: bool = False


class AmbiguityResolver:
    """
    Phase −1.1: Ambiguity Resolution Engine.

    Resolves multiple grounding candidates using deterministic
    threshold-based rules with safety constraints.

    Usage:
        resolver = AmbiguityResolver()
        resolution = resolver.resolve(candidates)
        # resolution.selected may be None if ASK_CLARIFY
    """

    # Confidence threshold for CONFIDENT status
    CONFIDENCE_THRESHOLD: float = 0.70

    # Delta threshold for ambiguity detection
    # If top - second < DELTA_THRESHOLD, candidates are too close
    DELTA_THRESHOLD: float = 0.15

    # Minimum confidence to allow SAFE_DEFAULT
    # Below this, always ASK_CLARIFY
    SAFE_DEFAULT_MIN_CONFIDENCE: float = 0.55

    def __init__(
        self,
        confidence_threshold: float | None = None,
        delta_threshold: float | None = None,
    ) -> None:
        """
        Initialize the resolver with optional custom thresholds.

        Args:
            confidence_threshold: Override default confidence threshold.
            delta_threshold: Override default delta threshold.
        """
        if confidence_threshold is not None:
            self.CONFIDENCE_THRESHOLD = confidence_threshold
        if delta_threshold is not None:
            self.DELTA_THRESHOLD = delta_threshold

    def resolve(
        self, candidates: List[GroundingCandidate]
    ) -> AmbiguityResolution:
        """
        Resolve multiple candidates into a single selection or clarification request.

        Args:
            candidates: List of candidates sorted by confidence (desc).

        Returns:
            AmbiguityResolution with selected candidate and resolution metadata.
        """
        # Handle empty candidates
        if not candidates:
            return AmbiguityResolution(
                selected=None,
                status=GroundingStatus.AMBIGUOUS,
                policy=ResolutionPolicy.ASK_CLARIFY,
                top_candidates=[],
                confidence_delta=0.0,
            )

        # Get top candidates
        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        # Calculate delta
        delta = top.confidence - (second.confidence if second else 0.0)

        # Build top candidates list
        top_candidates = [top]
        if second:
            top_candidates.append(second)

        # Apply resolution rules
        if top.confidence >= self.CONFIDENCE_THRESHOLD:
            # Rule 1: High confidence → CONFIDENT
            return self._resolve_confident(top, top_candidates, delta)

        elif second and delta < self.DELTA_THRESHOLD:
            # Rule 2: Close candidates → ASK_CLARIFY
            return self._resolve_ambiguous_close(top_candidates, delta)

        elif top.confidence >= self.SAFE_DEFAULT_MIN_CONFIDENCE:
            # Rule 3: Moderate confidence → SAFE_DEFAULT with safety checks
            return self._resolve_safe_default(top, top_candidates, delta)

        else:
            # Rule 4: Low confidence → ASK_CLARIFY
            return self._resolve_ambiguous_low(top_candidates, delta)

    def _resolve_confident(
        self,
        top: GroundingCandidate,
        top_candidates: List[GroundingCandidate],
        delta: float,
    ) -> AmbiguityResolution:
        """
        Handle confident resolution (top confidence above threshold).

        Still applies safety checks for high projection risk.
        """
        selected = top
        safety_override = False

        # Safety check: if HIGH projection risk and analysis was allowed, override
        if top.projection_risk == ProjectionRisk.HIGH and top.analysis_allowed:
            # Create a safe copy with analysis_allowed = False
            selected = GroundingCandidate(
                observed=top.observed,
                mode=top.mode,
                projection_risk=top.projection_risk,
                analysis_allowed=False,  # Safety override
                confidence=top.confidence,
                evidence=top.evidence + ["safety_override:high_projection_risk"],
            )
            safety_override = True

        return AmbiguityResolution(
            selected=selected,
            status=GroundingStatus.CONFIDENT,
            policy=ResolutionPolicy.NONE,
            top_candidates=top_candidates,
            confidence_delta=delta,
            safety_override_applied=safety_override,
        )

    def _resolve_ambiguous_close(
        self,
        top_candidates: List[GroundingCandidate],
        delta: float,
    ) -> AmbiguityResolution:
        """
        Handle ambiguous case where top candidates are too close.

        Requests clarification rather than guessing.
        """
        return AmbiguityResolution(
            selected=None,
            status=GroundingStatus.AMBIGUOUS,
            policy=ResolutionPolicy.ASK_CLARIFY,
            top_candidates=top_candidates,
            confidence_delta=delta,
        )

    def _resolve_safe_default(
        self,
        top: GroundingCandidate,
        top_candidates: List[GroundingCandidate],
        delta: float,
    ) -> AmbiguityResolution:
        """
        Handle safe default case (moderate confidence, can proceed with caution).

        Applies conservative safety constraints.
        """
        selected = top
        safety_override = False

        # Always disable analysis for SAFE_DEFAULT policy
        # This is more conservative than the confident case
        if top.analysis_allowed:
            selected = GroundingCandidate(
                observed=top.observed,
                mode=top.mode,
                projection_risk=top.projection_risk,
                analysis_allowed=False,  # Conservative override
                confidence=top.confidence,
                evidence=top.evidence + ["safety_override:safe_default_policy"],
            )
            safety_override = True

        # If projection risk is HIGH, upgrade to ASK_CLARIFY instead
        if top.projection_risk == ProjectionRisk.HIGH:
            return AmbiguityResolution(
                selected=None,
                status=GroundingStatus.AMBIGUOUS,
                policy=ResolutionPolicy.ASK_CLARIFY,
                top_candidates=top_candidates,
                confidence_delta=delta,
                safety_override_applied=True,
            )

        return AmbiguityResolution(
            selected=selected,
            status=GroundingStatus.AMBIGUOUS,
            policy=ResolutionPolicy.SAFE_DEFAULT,
            top_candidates=top_candidates,
            confidence_delta=delta,
            safety_override_applied=safety_override,
        )

    def _resolve_ambiguous_low(
        self,
        top_candidates: List[GroundingCandidate],
        delta: float,
    ) -> AmbiguityResolution:
        """
        Handle low confidence case.

        Always requests clarification when confidence is too low.
        """
        return AmbiguityResolution(
            selected=None,
            status=GroundingStatus.AMBIGUOUS,
            policy=ResolutionPolicy.ASK_CLARIFY,
            top_candidates=top_candidates,
            confidence_delta=delta,
        )

    def is_confident(self, resolution: AmbiguityResolution) -> bool:
        """Check if resolution is confident."""
        return resolution.status == GroundingStatus.CONFIDENT

    def needs_clarification(self, resolution: AmbiguityResolution) -> bool:
        """Check if resolution requires user clarification."""
        return resolution.policy == ResolutionPolicy.ASK_CLARIFY


# Public exports
__all__ = ["AmbiguityResolver", "AmbiguityResolution"]
