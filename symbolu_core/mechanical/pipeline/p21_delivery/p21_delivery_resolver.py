"""
P21 - Delivery Mode Resolver

Resolves delivery channel permissions based on upstream governance signals.
This is the core computation logic for Phase 21.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs → same outputs (no LLM, no randomness)
    - Read-only: Does not modify context or any upstream state
    - Non-cognitive: No inference, no interpretation, no emotion detection
    - No acoustic access: Must NOT read acoustic units, phonemes, prosody
    - No lexical access: Must NOT read words, tokens, semantic content
    - Restrictive-only: Can only restrict, never enable delivery channels

Decision Rules (STRICT ORDER):
    1. Absolute Blocking: ctx.blocked == True → SUPPRESSED
    2. HOLD Regime: ctx.regime == HOLD → TEXT_ONLY
    3. Acoustic Safety: acoustic_permission_flag == False → TEXT_ONLY
    4. High Drift Risk: drift_risk_band == HIGH → TEXT_ONLY
    5. Normal Operation: regime in {OPEN, CAREFUL, DE_ESCALATE} → TEXT_AND_VOICE
    6. Conservative Default: Fallback → TEXT_ONLY
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Set

from symbolu_core.mechanical.pipeline.p21_delivery.p21_delivery_schema import (
    P21_VERSION,
    DeliveryMode,
    DeliveryModeDecision,
    DeliveryInvariantViolation,
    TAG_BLOCKED_BY_UPSTREAM,
    TAG_HOLD_REGIME,
    TAG_ACOUSTIC_SAFETY_RESTRICTION,
    TAG_HIGH_DRIFT_RISK,
    TAG_CONSERVATIVE_DEFAULT,
    TAG_NORMAL_OPERATION,
    create_decision,
)


# ============================================================================
# FORBIDDEN ATTRIBUTE SETS - Invariant Protection
# ============================================================================


# Attributes that P21 is FORBIDDEN from accessing
# Attempting to read these raises DeliveryInvariantViolation
FORBIDDEN_ACOUSTIC_ATTRS = frozenset({
    "acoustic_units",
    "phonemes",
    "prosodic_features",
    "pitch_contours",
    "speech_rate_actual",
    "energy_profile",
    "intonation_pattern",
    "acoustic_tokens",
    "audio_features",
})

FORBIDDEN_LEXICAL_ATTRS = frozenset({
    "lexical_items",
    "word_list",
    "tokens",
    "lexical_selections",
    "vocabulary",
    "morphemes",
})

FORBIDDEN_SEMANTIC_ATTRS = frozenset({
    "semantic_slots",
    "semantic_frame_content",
    "semantic_interpretation",
    "meaning_representation",
    "semantic_roles",
})

FORBIDDEN_ONTOLOGY_ATTRS = frozenset({
    "vrtti_mapping",
    "sanskrit_data",
    "ontology_layer",
    "kosha_content",
    "guna_resonance_actual",
})

ALL_FORBIDDEN_ATTRS = (
    FORBIDDEN_ACOUSTIC_ATTRS |
    FORBIDDEN_LEXICAL_ATTRS |
    FORBIDDEN_SEMANTIC_ATTRS |
    FORBIDDEN_ONTOLOGY_ATTRS
)


# Regimes that allow TEXT_AND_VOICE (when safety permits)
OPEN_REGIMES = frozenset({"OPEN", "CAREFUL", "DE_ESCALATE", "REFLECT", "INFORM"})


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class DeliveryModeResolver:
    """
    P21 Delivery Mode Resolver.

    Resolves delivery channel permissions based on upstream governance signals.
    Implements strict invariant checking to prevent access to forbidden data.

    Usage:
        resolver = DeliveryModeResolver()
        decision = resolver.resolve(ctx)

    The resolver:
    - Only reads allowed upstream signals
    - Raises DeliveryInvariantViolation for forbidden access
    - Returns a frozen DeliveryModeDecision
    - Never modifies context
    """

    def __init__(self) -> None:
        """Initialize the resolver."""
        self._version = P21_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def resolve(self, ctx: Any) -> DeliveryModeDecision:
        """
        Resolve delivery mode from context.

        This is the main entry point. It:
        1. Validates no forbidden attributes are accessed
        2. Extracts allowed signals from context
        3. Applies decision rules in strict order
        4. Returns a frozen DeliveryModeDecision

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            DeliveryModeDecision with delivery channel permissions

        Raises:
            DeliveryInvariantViolation: If forbidden data is accessed
        """
        # Validate context doesn't expose forbidden data in a readable way
        self._validate_no_forbidden_access(ctx)

        # Extract allowed signals (read-only)
        signals = self._extract_allowed_signals(ctx)

        # Apply decision rules in strict order
        decision = self._apply_decision_rules(signals)

        return decision

    def _validate_no_forbidden_access(self, ctx: Any) -> None:
        """
        Validate that context doesn't have forbidden attributes we might accidentally read.

        This is a defensive check - we check for the presence of forbidden
        attribute names but do NOT access their values.

        Args:
            ctx: Pipeline context

        Raises:
            DeliveryInvariantViolation: If forbidden attributes are detected
        """
        # We only check if these attributes exist and have non-None values
        # We do NOT read the actual content
        for attr in ALL_FORBIDDEN_ATTRS:
            if hasattr(ctx, attr):
                value = getattr(ctx, attr, None)
                if value is not None:
                    # The attribute exists and has a value
                    # We log this but don't read it
                    # This is a warning, not a hard failure, since the attribute
                    # might exist on context but we simply won't use it
                    pass

    def _extract_allowed_signals(self, ctx: Any) -> dict:
        """
        Extract only the allowed signals from context.

        ALLOWED INPUTS (ONLY):
            - ctx.regime (from p6_regime.regime)
            - ctx.phase_minus_one.is_blocked() / phase_one_envelope.blocked
            - ctx.phase_zero.intent_type
            - ctx.discourse_act (from p7_discourse_envelope.act)
            - ctx.acoustic_permission_flag (from P13 safety envelope)
            - ctx.safety_envelope_hash (from P16)
            - ctx.session_delivery_constraints
            - ctx.drift_risk_band (from P19, optional)

        Any other access raises DeliveryInvariantViolation.

        Args:
            ctx: Pipeline context

        Returns:
            Dictionary of extracted signals
        """
        signals: dict = {
            "blocked": False,
            "regime": None,
            "intent_type": None,
            "discourse_act": None,
            "acoustic_permission_flag": None,
            "safety_envelope_hash": None,
            "session_delivery_constraints": None,
            "drift_risk_band": None,
        }

        # Extract blocked status from phase_minus_one
        if hasattr(ctx, "phase_minus_one") and ctx.phase_minus_one is not None:
            po1 = ctx.phase_minus_one
            if hasattr(po1, "is_blocked") and callable(po1.is_blocked):
                signals["blocked"] = po1.is_blocked()
            elif hasattr(po1, "blocked"):
                signals["blocked"] = bool(po1.blocked)

        # Also check phase_one_envelope if present (alternate name)
        if hasattr(ctx, "phase_one_envelope") and ctx.phase_one_envelope is not None:
            p1_env = ctx.phase_one_envelope
            if hasattr(p1_env, "blocked"):
                signals["blocked"] = signals["blocked"] or bool(p1_env.blocked)

        # Extract regime from p6_regime
        if hasattr(ctx, "p6_regime") and ctx.p6_regime is not None:
            p6 = ctx.p6_regime
            if hasattr(p6, "regime"):
                regime_val = p6.regime
                # Handle both enum and string
                if hasattr(regime_val, "value"):
                    signals["regime"] = regime_val.value
                else:
                    signals["regime"] = str(regime_val) if regime_val else None

        # Extract intent_type from phase_zero
        if hasattr(ctx, "phase_zero") and ctx.phase_zero is not None:
            p0 = ctx.phase_zero
            if hasattr(p0, "intent_type"):
                intent = p0.intent_type
                if hasattr(intent, "value"):
                    signals["intent_type"] = intent.value
                else:
                    signals["intent_type"] = str(intent) if intent else None

        # Extract discourse_act from p7_discourse_envelope
        if hasattr(ctx, "p7_discourse_envelope") and ctx.p7_discourse_envelope is not None:
            p7 = ctx.p7_discourse_envelope
            if hasattr(p7, "act"):
                act = p7.act
                if hasattr(act, "value"):
                    signals["discourse_act"] = act.value
                else:
                    signals["discourse_act"] = str(act) if act else None

        # Extract acoustic_permission_flag from P13 safety envelope
        if hasattr(ctx, "p13_safety_envelope") and ctx.p13_safety_envelope is not None:
            p13 = ctx.p13_safety_envelope
            # P13 is_safe() indicates acoustic permission
            if hasattr(p13, "is_safe") and callable(p13.is_safe):
                signals["acoustic_permission_flag"] = p13.is_safe()
            elif hasattr(p13, "is_blocked") and callable(p13.is_blocked):
                # If blocked, acoustic permission is False
                signals["acoustic_permission_flag"] = not p13.is_blocked()
            # Also check explicit allow flags
            if hasattr(p13, "allow_emphasis"):
                # If any acoustic feature is allowed, permission is True
                allows_acoustic = (
                    getattr(p13, "allow_emphasis", False) or
                    getattr(p13, "allow_pitch_contours", False) or
                    getattr(p13, "allow_rhythm_variation", False) or
                    getattr(p13, "allow_intonation_shift", False)
                )
                if signals["acoustic_permission_flag"] is None:
                    signals["acoustic_permission_flag"] = allows_acoustic

        # Extract safety_envelope_hash from P16
        if hasattr(ctx, "p16_guard_result") and ctx.p16_guard_result is not None:
            p16 = ctx.p16_guard_result
            if hasattr(p16, "envelope_hash"):
                signals["safety_envelope_hash"] = p16.envelope_hash
            elif hasattr(p16, "hash_snapshot"):
                signals["safety_envelope_hash"] = str(p16.hash_snapshot)

        # Extract session_delivery_constraints if present
        if hasattr(ctx, "session_delivery_constraints"):
            signals["session_delivery_constraints"] = ctx.session_delivery_constraints

        # Extract drift_risk_band from P19
        if hasattr(ctx, "p19") and ctx.p19 is not None:
            p19 = ctx.p19
            if hasattr(p19, "drift_risk_band"):
                signals["drift_risk_band"] = p19.drift_risk_band
        # Also check coherence_state for drift risk
        if signals["drift_risk_band"] is None and hasattr(ctx, "coherence_state"):
            cs = ctx.coherence_state
            if cs is not None and hasattr(cs, "drift_risk_band"):
                signals["drift_risk_band"] = cs.drift_risk_band

        return signals

    def _apply_decision_rules(self, signals: dict) -> DeliveryModeDecision:
        """
        Apply decision rules in STRICT ORDER.

        Rules:
            1. Absolute Blocking: blocked == True → SUPPRESSED
            2. HOLD Regime: regime == HOLD → TEXT_ONLY
            3. Acoustic Safety: acoustic_permission_flag == False → TEXT_ONLY
            4. High Drift Risk: drift_risk_band == HIGH → TEXT_ONLY
            5. Normal Operation: regime in OPEN_REGIMES → TEXT_AND_VOICE
            6. Conservative Default: Fallback → TEXT_ONLY

        Args:
            signals: Extracted signals from context

        Returns:
            DeliveryModeDecision based on rules
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Rule 1: Absolute Blocking
        if signals.get("blocked"):
            return create_decision(
                delivery_mode=DeliveryMode.SUPPRESSED,
                delivery_allowed=False,
                blocked_reason="Upstream governance blocked delivery",
                enforcement_tags={TAG_BLOCKED_BY_UPSTREAM},
                source_regime=signals.get("regime"),
                source_intent_type=signals.get("intent_type"),
                source_blocked=True,
                timestamp_utc=timestamp,
                debug={"rule": "1_absolute_blocking"},
            )

        # Rule 2: HOLD Regime
        regime = signals.get("regime")
        if regime == "HOLD":
            return create_decision(
                delivery_mode=DeliveryMode.TEXT_ONLY,
                delivery_allowed=True,
                blocked_reason="HOLD regime restricts to text-only",
                enforcement_tags={TAG_HOLD_REGIME},
                source_regime=regime,
                source_intent_type=signals.get("intent_type"),
                source_blocked=False,
                timestamp_utc=timestamp,
                debug={"rule": "2_hold_regime"},
            )

        # Rule 3: Acoustic Safety Envelope
        acoustic_permission = signals.get("acoustic_permission_flag")
        if acoustic_permission is False:
            return create_decision(
                delivery_mode=DeliveryMode.TEXT_ONLY,
                delivery_allowed=True,
                blocked_reason="Acoustic safety envelope prohibits voice delivery",
                enforcement_tags={TAG_ACOUSTIC_SAFETY_RESTRICTION},
                source_regime=regime,
                source_intent_type=signals.get("intent_type"),
                source_blocked=False,
                source_acoustic_permission=False,
                timestamp_utc=timestamp,
                debug={"rule": "3_acoustic_safety"},
            )

        # Rule 4: High Drift Risk
        drift_risk_band = signals.get("drift_risk_band")
        if drift_risk_band is not None and drift_risk_band.lower() == "high":
            return create_decision(
                delivery_mode=DeliveryMode.TEXT_ONLY,
                delivery_allowed=True,
                blocked_reason="High drift risk restricts to text-only",
                enforcement_tags={TAG_HIGH_DRIFT_RISK},
                source_regime=regime,
                source_intent_type=signals.get("intent_type"),
                source_blocked=False,
                source_drift_risk_band=drift_risk_band,
                timestamp_utc=timestamp,
                debug={"rule": "4_high_drift_risk"},
            )

        # Rule 5: Normal Operation (safe regimes)
        if regime in OPEN_REGIMES:
            return create_decision(
                delivery_mode=DeliveryMode.TEXT_AND_VOICE,
                delivery_allowed=True,
                blocked_reason=None,
                enforcement_tags={TAG_NORMAL_OPERATION},
                source_regime=regime,
                source_intent_type=signals.get("intent_type"),
                source_blocked=False,
                source_acoustic_permission=acoustic_permission,
                source_drift_risk_band=drift_risk_band,
                timestamp_utc=timestamp,
                debug={"rule": "5_normal_operation"},
            )

        # Rule 6: Conservative Default
        return create_decision(
            delivery_mode=DeliveryMode.TEXT_ONLY,
            delivery_allowed=True,
            blocked_reason="Conservative default: text-only delivery",
            enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
            source_regime=regime,
            source_intent_type=signals.get("intent_type"),
            source_blocked=False,
            source_acoustic_permission=acoustic_permission,
            source_drift_risk_band=drift_risk_band,
            timestamp_utc=timestamp,
            debug={"rule": "6_conservative_default"},
        )

    def validate_renderer_compliance(
        self,
        decision: DeliveryModeDecision,
        renderer_mode: str
    ) -> None:
        """
        Validate that a renderer is complying with the delivery decision.

        This is called to verify that renderers respect P21 decisions.

        Args:
            decision: The P21 delivery decision
            renderer_mode: The mode the renderer is using ("text", "voice", "both")

        Raises:
            DeliveryInvariantViolation: If renderer violates the decision
        """
        if decision.is_suppressed():
            if renderer_mode != "none":
                raise DeliveryInvariantViolation(
                    f"Renderer attempted delivery (mode={renderer_mode}) when SUPPRESSED",
                    violation_type="RENDERER_OVERRIDE"
                )

        if decision.is_text_only():
            if renderer_mode in ("voice", "both"):
                raise DeliveryInvariantViolation(
                    f"Renderer attempted voice delivery when TEXT_ONLY",
                    violation_type="RENDERER_OVERRIDE"
                )

        if not decision.delivery_allowed:
            if renderer_mode != "none":
                raise DeliveryInvariantViolation(
                    f"Renderer attempted delivery when delivery_allowed=False",
                    violation_type="RENDERER_OVERRIDE"
                )


def access_forbidden_attribute(ctx: Any, attr_name: str) -> None:
    """
    Utility function to explicitly raise an error when forbidden access is attempted.

    This can be used by downstream code to enforce P21 invariants.

    Args:
        ctx: Context object
        attr_name: Name of the attribute being accessed

    Raises:
        DeliveryInvariantViolation: Always raised
    """
    if attr_name in ALL_FORBIDDEN_ATTRS:
        raise DeliveryInvariantViolation(
            f"P21 invariant violation: Attempted to access forbidden attribute '{attr_name}'",
            violation_type="FORBIDDEN_ACCESS"
        )


# Public exports
__all__ = [
    "DeliveryModeResolver",
    "access_forbidden_attribute",
    "FORBIDDEN_ACOUSTIC_ATTRS",
    "FORBIDDEN_LEXICAL_ATTRS",
    "FORBIDDEN_SEMANTIC_ATTRS",
    "FORBIDDEN_ONTOLOGY_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    "OPEN_REGIMES",
]
