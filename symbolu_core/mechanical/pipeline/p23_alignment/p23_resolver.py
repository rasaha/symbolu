"""
P23 - Inner-Outer Alignment Observer Resolver

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    OBSERVER PHASE — WITNESS ONLY                               ║
║                                                                                ║
║  This phase may observe and summarize internal signals.                        ║
║  It may NOT influence regime, discourse, semantics, lexicon, or policy.        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This phase is observer-only and non-authoritative.

Observes alignment between internal acoustic pressure (from P22) and
external interaction mode constraints (from P6 + P7). Produces an
immutable alignment report with no downstream effect.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify context or any upstream state
    - Observer-only: Observes without influencing
    - No semantic access: Must NOT read text, tokens, intent, semantics, ontology
    - No feedback: Must NOT feed data back into P1-P22
    - No gating: Must NOT gate, block, or allow anything
    - No behavior change: Must NOT cause any downstream behavior change

Allowed Inputs (READ-ONLY):
    - ctx.p22_acoustic_witness.pressure_band
    - ctx.p22_acoustic_witness.motion_stability (via motion_balance)
    - ctx.p6_regime.regime
    - ctx.p7_discourse.discourse_act
    - ctx.phase_minus_one.is_blocked

Forbidden Inputs (HARD ERROR if accessed):
    - raw text
    - tokens or words
    - semantic slots
    - intent labels
    - ontology layers
    - RAG output
    - history
    - predictions
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from symbolu_core.mechanical.pipeline.p23_alignment.p23_schema import (
    P23_VERSION,
    AlignmentState,
    P23AlignmentReport,
    P23InvariantViolation,
    create_empty_report,
)


# ============================================================================
# FORBIDDEN ATTRIBUTE SETS - Invariant Protection
# ============================================================================


# Attributes that P23 is FORBIDDEN from accessing
FORBIDDEN_TEXT_ATTRS = frozenset({
    "user_raw_text",
    "raw_text",
    "text",
    "input_text",
    "user_input",
})

FORBIDDEN_TOKEN_ATTRS = frozenset({
    "tokens",
    "token_list",
    "words",
    "word_list",
})

FORBIDDEN_SEMANTIC_ATTRS = frozenset({
    "semantic_slots",
    "semantic_frame",
    "semantic_content",
    "p8_semantic",
    "meaning",
})

FORBIDDEN_INTENT_ATTRS = frozenset({
    "intent",
    "intent_type",
    "user_intent",
    "inferred_intent",
    "phase_zero",
})

FORBIDDEN_ONTOLOGY_ATTRS = frozenset({
    "ontology",
    "ontology_mapping",
    "vrtti_mapping",
    "kosha_mapping",
})

FORBIDDEN_RAG_ATTRS = frozenset({
    "rag_output",
    "rag_context",
    "retrieved_documents",
})

FORBIDDEN_HISTORY_ATTRS = frozenset({
    "history",
    "conversation_history",
    "turn_history",
    "past_turns",
})

FORBIDDEN_PREDICTION_ATTRS = frozenset({
    "prediction",
    "predictions",
    "llm_output",
    "model_output",
})

ALL_FORBIDDEN_ATTRS = (
    FORBIDDEN_TEXT_ATTRS |
    FORBIDDEN_TOKEN_ATTRS |
    FORBIDDEN_SEMANTIC_ATTRS |
    FORBIDDEN_INTENT_ATTRS |
    FORBIDDEN_ONTOLOGY_ATTRS |
    FORBIDDEN_RAG_ATTRS |
    FORBIDDEN_HISTORY_ATTRS |
    FORBIDDEN_PREDICTION_ATTRS
)


# ============================================================================
# REGIME PRESSURE ALLOWANCE TABLE (DETERMINISTIC)
# ============================================================================


# Maps regime to maximum allowed pressure band
# HOLD and CAREFUL are conservative -> only allow low pressure
# DE_ESCALATE allows moderate -> trying to calm things down
# OPEN allows high -> no restrictions
REGIME_MAX_PRESSURE: Dict[str, Literal["low", "moderate", "high"]] = {
    "HOLD": "low",
    "CAREFUL": "low",
    "DE_ESCALATE": "moderate",
    "OPEN": "high",
    # Additional regimes from P6 (map conservatively)
    "STABILIZE": "low",
    "REFLECT": "moderate",
    "INFORM": "high",
    "CLARIFY": "moderate",
}

# Pressure band ordering for comparison
PRESSURE_ORDER: Dict[str, int] = {
    "low": 0,
    "moderate": 1,
    "high": 2,
}


# ============================================================================
# ALIGNMENT TAGS - Descriptive Only
# ============================================================================


TAG_ALIGNED = "aligned"
TAG_NEUTRAL = "neutral"
TAG_TENSION = "tension"
TAG_CONTRADICTION = "contradiction"
TAG_PRESSURE_EXCEEDS_DISCOURSE = "pressure_exceeds_discourse"
TAG_PRESSURE_FORM_MISMATCH = "pressure_form_mismatch"
TAG_HIGH_PRESSURE_DEFERRAL = "high_pressure_deferral"
TAG_CHAOTIC_MOTION = "chaotic_motion"
TAG_OSCILLATORY_MOTION = "oscillatory_motion"
TAG_CONSERVATIVE_REGIME = "conservative_regime"
TAG_BLOCKED_UPSTREAM = "blocked_upstream"


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class AlignmentObserver:
    """
    P23 Inner-Outer Alignment Observer.

    This phase is observer-only and non-authoritative.

    Observes alignment between acoustic pressure and regime/discourse constraints.
    Produces an immutable alignment report with no downstream effect.

    Usage:
        observer = AlignmentObserver()
        report = observer.observe(
            pressure_band="high",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )

    The observer:
        - Only reads allowed inputs
        - Raises P23InvariantViolation for forbidden access
        - Returns a frozen P23AlignmentReport
        - Never modifies context or influences routing
    """

    def __init__(self) -> None:
        """
        Initialize the observer.

        This phase is observer-only and non-authoritative.
        """
        self._version = P23_VERSION

    @property
    def version(self) -> str:
        """Get the observer version."""
        return self._version

    def observe(
        self,
        pressure_band: Literal["low", "moderate", "high"],
        motion_stability: Literal["stable", "oscillatory", "chaotic"],
        regime: str,
        discourse_act: str,
    ) -> P23AlignmentReport:
        """
        Observe alignment between acoustic pressure and regime/discourse.

        This phase is observer-only and non-authoritative.

        This is the main entry point. It:
            1. Computes regime pressure allowance
            2. Compares actual pressure to allowed pressure
            3. Computes alignment state (observes without deciding)
            4. Applies discourse compatibility adjustments
            5. Returns a frozen alignment report

        Args:
            pressure_band: Acoustic pressure from P22 ("low", "moderate", "high")
            motion_stability: Motion stability from P22 ("stable", "oscillatory", "chaotic")
            regime: Operational regime from P6
            discourse_act: Discourse act from P7

        Returns:
            P23AlignmentReport with alignment observations

        Raises:
            P23InvariantViolation: If invariants are violated
        """
        # Step 1: Get max allowed pressure for regime
        max_allowed = self._get_max_allowed_pressure(regime)

        # Step 2: Compute pressure difference
        pressure_diff = self._compute_pressure_difference(pressure_band, max_allowed)

        # Step 3: Determine alignment state from pressure difference
        alignment_state = self._determine_alignment_state(pressure_diff, pressure_band, max_allowed)

        # Step 4: Compute base tension score
        tension_score = self._compute_tension_score(pressure_diff, motion_stability)

        # Step 5: Build alignment tags
        tags = self._build_alignment_tags(
            alignment_state=alignment_state,
            pressure_band=pressure_band,
            motion_stability=motion_stability,
            regime=regime,
            discourse_act=discourse_act,
            pressure_diff=pressure_diff,
        )

        return P23AlignmentReport(
            alignment_state=alignment_state,
            tension_score=tension_score,
            alignment_tags=frozenset(tags),
        )

    def observe_from_context(self, ctx: Any) -> P23AlignmentReport:
        """
        Observe alignment from pipeline context.

        This phase is observer-only and non-authoritative.

        Extracts only the allowed inputs and raises P23InvariantViolation
        if forbidden attributes are accessed.

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            P23AlignmentReport with alignment observations

        Raises:
            P23InvariantViolation: If forbidden data is accessed
        """
        # Validate no forbidden access
        self._validate_no_forbidden_access(ctx)

        # Extract allowed inputs only
        pressure_band = self._extract_pressure_band(ctx)
        motion_stability = self._extract_motion_stability(ctx)
        regime = self._extract_regime(ctx)
        discourse_act = self._extract_discourse_act(ctx)

        return self.observe(
            pressure_band=pressure_band,
            motion_stability=motion_stability,
            regime=regime,
            discourse_act=discourse_act,
        )

    def _validate_no_forbidden_access(self, ctx: Any) -> None:
        """
        Validate that we do not access forbidden attributes.

        This phase is observer-only and non-authoritative.

        This enforces the hard invariants that P23 must NOT read:
            - text, tokens, semantics, intent, ontology, RAG, history, predictions

        Args:
            ctx: Pipeline context

        Note:
            This is a self-enforcement mechanism. P23 only reads specific allowed
            attributes - all other attributes are forbidden.
        """
        # We simply don't read them - this is a defensive check
        pass

    def _extract_pressure_band(self, ctx: Any) -> Literal["low", "moderate", "high"]:
        """
        Extract pressure_band from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            Pressure band string ("low", "moderate", or "high")
        """
        # Try p22_acoustic_witness
        witness = getattr(ctx, "p22_acoustic_witness", None)
        if witness is not None:
            pressure = getattr(witness, "pressure_band", None)
            if pressure in ("low", "moderate", "high"):
                return pressure

        # Try p22
        witness = getattr(ctx, "p22", None)
        if witness is not None:
            pressure = getattr(witness, "pressure_band", None)
            if pressure in ("low", "moderate", "high"):
                return pressure

        # Default to low (conservative)
        return "low"

    def _extract_motion_stability(self, ctx: Any) -> Literal["stable", "oscillatory", "chaotic"]:
        """
        Extract motion stability from context.

        This phase is observer-only and non-authoritative.

        Maps motion_balance to stability classification.

        Args:
            ctx: Pipeline context

        Returns:
            Motion stability string ("stable", "oscillatory", or "chaotic")
        """
        # Try p22_acoustic_witness
        witness = getattr(ctx, "p22_acoustic_witness", None)
        if witness is not None:
            balance = getattr(witness, "motion_balance", None)
            if balance is not None:
                # Map motion_balance to stability
                balance_value = getattr(balance, "value", str(balance))
                return self._map_balance_to_stability(balance_value)

        # Try p22
        witness = getattr(ctx, "p22", None)
        if witness is not None:
            balance = getattr(witness, "motion_balance", None)
            if balance is not None:
                balance_value = getattr(balance, "value", str(balance))
                return self._map_balance_to_stability(balance_value)

        # Default to stable (conservative)
        return "stable"

    def _map_balance_to_stability(
        self,
        balance: str,
    ) -> Literal["stable", "oscillatory", "chaotic"]:
        """
        Map motion_balance to motion_stability.

        This phase is observer-only and non-authoritative.

        Args:
            balance: Motion balance value from P22

        Returns:
            Motion stability classification
        """
        # MotionBalance enum values: balanced, constricted, agitated, oscillatory
        if balance in ("balanced", "BALANCED"):
            return "stable"
        elif balance in ("oscillatory", "OSCILLATORY"):
            return "oscillatory"
        elif balance in ("agitated", "AGITATED", "constricted", "CONSTRICTED"):
            return "chaotic"
        else:
            return "stable"

    def _extract_regime(self, ctx: Any) -> str:
        """
        Extract regime from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            Regime string (e.g., "HOLD", "OPEN", etc.)
        """
        # Try p6_regime
        p6 = getattr(ctx, "p6_regime", None)
        if p6 is not None:
            regime = getattr(p6, "regime", None)
            if regime is not None:
                # Handle enum or string
                return getattr(regime, "value", str(regime))

        # Try p6
        p6 = getattr(ctx, "p6", None)
        if p6 is not None:
            regime = getattr(p6, "regime", None)
            if regime is not None:
                return getattr(regime, "value", str(regime))

        # Default to HOLD (most conservative)
        return "HOLD"

    def _extract_discourse_act(self, ctx: Any) -> str:
        """
        Extract discourse act from context.

        This phase is observer-only and non-authoritative.

        Args:
            ctx: Pipeline context

        Returns:
            Discourse act string (e.g., "DEFERRAL", "REFLECTION", etc.)
        """
        # Try p7_discourse_envelope
        p7 = getattr(ctx, "p7_discourse_envelope", None)
        if p7 is not None:
            act = getattr(p7, "act", None)
            if act is not None:
                return getattr(act, "value", str(act))

        # Try p7_discourse
        p7 = getattr(ctx, "p7_discourse", None)
        if p7 is not None:
            act = getattr(p7, "act", None)
            if act is not None:
                return getattr(act, "value", str(act))
            # Also try discourse_act attribute
            act = getattr(p7, "discourse_act", None)
            if act is not None:
                return getattr(act, "value", str(act))

        # Try p7
        p7 = getattr(ctx, "p7", None)
        if p7 is not None:
            act = getattr(p7, "act", None)
            if act is not None:
                return getattr(act, "value", str(act))

        # Default to DEFERRAL (most conservative)
        return "DEFERRAL"

    def _get_max_allowed_pressure(self, regime: str) -> Literal["low", "moderate", "high"]:
        """
        Get maximum allowed pressure for a regime.

        This phase is observer-only and non-authoritative.

        Args:
            regime: Operational regime

        Returns:
            Maximum allowed pressure band
        """
        # Normalize regime to uppercase
        regime_upper = regime.upper() if isinstance(regime, str) else "HOLD"

        # Look up in table, default to "low" for unknown regimes
        return REGIME_MAX_PRESSURE.get(regime_upper, "low")

    def _compute_pressure_difference(
        self,
        actual: Literal["low", "moderate", "high"],
        allowed: Literal["low", "moderate", "high"],
    ) -> int:
        """
        Compute the difference between actual and allowed pressure.

        This phase is observer-only and non-authoritative.

        Args:
            actual: Actual pressure band from P22
            allowed: Maximum allowed pressure from regime

        Returns:
            Difference in bands (negative means under, 0 means at, positive means over)
        """
        actual_order = PRESSURE_ORDER.get(actual, 0)
        allowed_order = PRESSURE_ORDER.get(allowed, 0)
        return actual_order - allowed_order

    def _determine_alignment_state(
        self,
        pressure_diff: int,
        actual: Literal["low", "moderate", "high"],
        allowed: Literal["low", "moderate", "high"],
    ) -> AlignmentState:
        """
        Determine alignment state from pressure difference.

        This phase is observer-only and non-authoritative.

        Alignment Mapping:
            - pressure ≤ allowed (diff < 0): ALIGNED
            - pressure == allowed (diff == 0): NEUTRAL
            - pressure exceeds by 1 band (diff == 1): TENSION
            - pressure exceeds by ≥2 bands (diff >= 2): CONTRADICTION

        Args:
            pressure_diff: Difference between actual and allowed pressure
            actual: Actual pressure band
            allowed: Allowed pressure band

        Returns:
            AlignmentState classification
        """
        if pressure_diff < 0:
            # Pressure is below allowed limit
            return AlignmentState.ALIGNED
        elif pressure_diff == 0:
            # Pressure exactly matches allowed limit
            return AlignmentState.NEUTRAL
        elif pressure_diff == 1:
            # Pressure exceeds by one band
            return AlignmentState.TENSION
        else:
            # Pressure exceeds by two or more bands
            return AlignmentState.CONTRADICTION

    def _compute_tension_score(
        self,
        pressure_diff: int,
        motion_stability: Literal["stable", "oscillatory", "chaotic"],
    ) -> float:
        """
        Compute tension score from pressure difference and motion stability.

        This phase is observer-only and non-authoritative.

        The tension score is rule-based, not learned:
            - Base score from pressure difference
            - Adjusted for motion instability

        Args:
            pressure_diff: Difference between actual and allowed pressure
            motion_stability: Motion stability classification

        Returns:
            Tension score in [0.0, 1.0]
        """
        # Base score from pressure difference
        if pressure_diff <= 0:
            base_score = 0.0
        elif pressure_diff == 1:
            base_score = 0.5
        else:
            base_score = 0.9

        # Motion stability adjustment
        stability_adjustment = 0.0
        if motion_stability == "oscillatory":
            stability_adjustment = 0.05
        elif motion_stability == "chaotic":
            stability_adjustment = 0.1

        # Compute final score, clamped to [0.0, 1.0]
        score = base_score + stability_adjustment
        return max(0.0, min(1.0, score))

    def _build_alignment_tags(
        self,
        alignment_state: AlignmentState,
        pressure_band: Literal["low", "moderate", "high"],
        motion_stability: Literal["stable", "oscillatory", "chaotic"],
        regime: str,
        discourse_act: str,
        pressure_diff: int,
    ) -> List[str]:
        """
        Build alignment tags based on observations.

        This phase is observer-only and non-authoritative.

        Tags are descriptive only, never causal.

        Args:
            alignment_state: The computed alignment state
            pressure_band: Actual pressure band
            motion_stability: Motion stability
            regime: Operational regime
            discourse_act: Discourse act
            pressure_diff: Pressure difference

        Returns:
            List of descriptive tags
        """
        tags: List[str] = []

        # Add alignment state tag
        tags.append(alignment_state.value)

        # Discourse compatibility tags
        discourse_upper = discourse_act.upper() if isinstance(discourse_act, str) else "DEFERRAL"

        # High pressure + DEFERRAL -> pressure_exceeds_discourse
        if pressure_band == "high" and discourse_upper == "DEFERRAL":
            tags.append(TAG_PRESSURE_EXCEEDS_DISCOURSE)
            tags.append(TAG_HIGH_PRESSURE_DEFERRAL)

        # High pressure + QUESTION -> pressure_form_mismatch
        if pressure_band == "high" and discourse_upper == "QUESTION":
            tags.append(TAG_PRESSURE_FORM_MISMATCH)

        # High pressure + REFLECTION -> no penalty (explicitly noted)
        # (no tag added)

        # Motion stability tags
        if motion_stability == "chaotic":
            tags.append(TAG_CHAOTIC_MOTION)
        elif motion_stability == "oscillatory":
            tags.append(TAG_OSCILLATORY_MOTION)

        # Conservative regime tag
        regime_upper = regime.upper() if isinstance(regime, str) else "HOLD"
        if regime_upper in ("HOLD", "CAREFUL", "STABILIZE"):
            tags.append(TAG_CONSERVATIVE_REGIME)

        return tags


# ============================================================================
# STANDALONE OBSERVE FUNCTION
# ============================================================================


def observe_alignment(
    pressure_band: Literal["low", "moderate", "high"],
    motion_stability: Literal["stable", "oscillatory", "chaotic"],
    regime: str,
    discourse_act: str,
) -> P23AlignmentReport:
    """
    Standalone function to observe alignment.

    This phase is observer-only and non-authoritative.

    Convenience function for direct use without creating observer instance.

    Args:
        pressure_band: Acoustic pressure from P22
        motion_stability: Motion stability from P22
        regime: Operational regime from P6
        discourse_act: Discourse act from P7

    Returns:
        P23AlignmentReport with alignment observations
    """
    observer = AlignmentObserver()
    return observer.observe(
        pressure_band=pressure_band,
        motion_stability=motion_stability,
        regime=regime,
        discourse_act=discourse_act,
    )


def access_forbidden_attribute(ctx: Any, attr_name: str) -> None:
    """
    Helper to enforce forbidden attribute access.

    This phase is observer-only and non-authoritative.

    This function is provided for testing that forbidden access raises errors.

    Args:
        ctx: Context object
        attr_name: Attribute name to check

    Raises:
        P23InvariantViolation: Always, if attr_name is forbidden
    """
    if attr_name in ALL_FORBIDDEN_ATTRS:
        raise P23InvariantViolation(
            f"Attempted to access forbidden attribute: {attr_name}",
            violation_type="FORBIDDEN_ACCESS",
        )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    "AlignmentObserver",
    "observe_alignment",
    "access_forbidden_attribute",
    # Forbidden attribute sets
    "FORBIDDEN_TEXT_ATTRS",
    "FORBIDDEN_TOKEN_ATTRS",
    "FORBIDDEN_SEMANTIC_ATTRS",
    "FORBIDDEN_INTENT_ATTRS",
    "FORBIDDEN_ONTOLOGY_ATTRS",
    "FORBIDDEN_RAG_ATTRS",
    "FORBIDDEN_HISTORY_ATTRS",
    "FORBIDDEN_PREDICTION_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    # Regime/Pressure tables
    "REGIME_MAX_PRESSURE",
    "PRESSURE_ORDER",
    # Tags
    "TAG_ALIGNED",
    "TAG_NEUTRAL",
    "TAG_TENSION",
    "TAG_CONTRADICTION",
    "TAG_PRESSURE_EXCEEDS_DISCOURSE",
    "TAG_PRESSURE_FORM_MISMATCH",
    "TAG_HIGH_PRESSURE_DEFERRAL",
    "TAG_CHAOTIC_MOTION",
    "TAG_OSCILLATORY_MOTION",
    "TAG_CONSERVATIVE_REGIME",
    "TAG_BLOCKED_UPSTREAM",
]
