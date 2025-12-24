"""
PO1.1 — Ambiguity Resolver (ARL)
(Implemented as phase_minus_one_ambiguity for backward compatibility)

Resolves multiple grounding candidates into a single selection or
determines that clarification is needed.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Resolution Rules:
1. If top.confidence >= CONFIDENCE_THRESHOLD → CONFIDENT, select top
2. If top - second < DELTA_THRESHOLD → AMBIGUOUS, ASK_CLARIFY
3. Else → AMBIGUOUS, SAFE_DEFAULT with conservative constraints

Safety Invariants:
- If projection_risk == HIGH and would allow analysis → force analysis_allowed = False
- Never select a candidate that would enable unsafe analytical operations
- Prefer ASK_CLARIFY over potentially unsafe defaults

Fuzzy Logic Integration (v2):
- Accepts FuzzyQuerySignals to adjust confidence thresholds
- Uses intent hints to tip borderline cases
- Subject clarity can boost/reduce confidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING

from .phase_minus_one_schema import (
    GroundingCandidate,
    GroundingStatus,
    ProjectionRisk,
    ResolutionPolicy,
)

if TYPE_CHECKING:
    from .phase_minus_one_fuzzy import FuzzyQuerySignals


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
        fuzzy_adjustment_applied: Confidence adjustment from fuzzy signals
        fuzzy_hints: Hints from fuzzy classifier for downstream
    """
    selected: Optional[GroundingCandidate]
    status: GroundingStatus
    policy: ResolutionPolicy
    top_candidates: List[GroundingCandidate]
    confidence_delta: float
    safety_override_applied: bool = False
    fuzzy_adjustment_applied: float = 0.0
    fuzzy_hints: List[str] = None

    def __post_init__(self):
        if self.fuzzy_hints is None:
            self.fuzzy_hints = []


class AmbiguityResolver:
    """
    PO1.1: Ambiguity Resolution Engine.

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
        self,
        candidates: List[GroundingCandidate],
        fuzzy_signals: Optional["FuzzyQuerySignals"] = None,
    ) -> AmbiguityResolution:
        """
        Resolve multiple candidates into a single selection or clarification request.

        Args:
            candidates: List of candidates sorted by confidence (desc).
            fuzzy_signals: Optional fuzzy signals to adjust thresholds.

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

        # Apply fuzzy adjustment to effective confidence
        fuzzy_adjustment = 0.0
        fuzzy_hints: List[str] = []

        if fuzzy_signals is not None:
            fuzzy_adjustment = fuzzy_signals.confidence_adjustment
            fuzzy_hints = fuzzy_signals.hints.copy()

        effective_confidence = top.confidence + fuzzy_adjustment

        # Apply resolution rules with fuzzy-adjusted confidence
        if effective_confidence >= self.CONFIDENCE_THRESHOLD:
            # Rule 1: High effective confidence → CONFIDENT
            resolution = self._resolve_confident(top, top_candidates, delta)
            resolution.fuzzy_adjustment_applied = fuzzy_adjustment
            resolution.fuzzy_hints = fuzzy_hints
            return resolution

        elif second and delta < self.DELTA_THRESHOLD:
            # Rule 2: Close candidates → Check if fuzzy can help
            # If fuzzy signals strongly favor one intent, reduce delta threshold
            if fuzzy_signals and self._fuzzy_can_disambiguate(fuzzy_signals, top, second):
                # Fuzzy signals tip the balance - allow SAFE_DEFAULT
                resolution = self._resolve_safe_default(top, top_candidates, delta)
                resolution.fuzzy_adjustment_applied = fuzzy_adjustment
                resolution.fuzzy_hints = fuzzy_hints + ["fuzzy_disambiguation_applied"]
                return resolution
            # Otherwise ASK_CLARIFY
            resolution = self._resolve_ambiguous_close(top_candidates, delta)
            resolution.fuzzy_hints = fuzzy_hints
            return resolution

        elif effective_confidence >= self.SAFE_DEFAULT_MIN_CONFIDENCE:
            # Rule 3: Moderate confidence → SAFE_DEFAULT with safety checks
            resolution = self._resolve_safe_default(top, top_candidates, delta)
            resolution.fuzzy_adjustment_applied = fuzzy_adjustment
            resolution.fuzzy_hints = fuzzy_hints
            return resolution

        else:
            # Rule 4: Low confidence → ASK_CLARIFY
            resolution = self._resolve_ambiguous_low(top_candidates, delta)
            resolution.fuzzy_hints = fuzzy_hints
            return resolution

    def _fuzzy_can_disambiguate(
        self,
        fuzzy_signals: "FuzzyQuerySignals",
        top: GroundingCandidate,
        second: GroundingCandidate,
    ) -> bool:
        """
        Check if fuzzy signals can help disambiguate close candidates.

        Returns True if:
        - Subject clarity is high (>= 0.7)
        - Primary intent aligns with top candidate mode
        - No mixed pronoun warning
        """
        # Need good subject clarity
        if fuzzy_signals.subject_clarity < 0.7:
            return False

        # Check for mixed pronouns (ambiguity signal)
        if "mixed_pronouns" in fuzzy_signals.hints:
            return False

        # Check intent alignment with observation mode
        from .phase_minus_one_schema import ObservationMode
        from .phase_minus_one_fuzzy import QueryIntentHint

        intent_mode_alignment = {
            QueryIntentHint.EMOTIONAL: ObservationMode.REFLEXIVE,
            QueryIntentHint.REFLECTIVE: ObservationMode.REFLEXIVE,
            QueryIntentHint.RELATIONAL: ObservationMode.RELATIONAL,
            QueryIntentHint.INFORMATIONAL: ObservationMode.DETACHED,
        }

        expected_mode = intent_mode_alignment.get(fuzzy_signals.primary_intent)
        if expected_mode and top.mode == expected_mode:
            return True

        return False

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
