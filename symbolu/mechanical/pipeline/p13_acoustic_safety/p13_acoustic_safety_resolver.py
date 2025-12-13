"""
P13 - Acoustic Safety Envelope Resolver Implementation

The core resolution engine for P13. This module contains all safety
constraint computation logic for producing the AcousticSafetyEnvelope.

CRITICAL: This resolver ONLY CAPS, CONSTRAINS, and VETOES.
It NEVER amplifies, generates, or infers.

Resolution Rules (Deterministic):
1. P13 may only reduce or clamp, never amplify
2. If P12 reports mismatch -> risk_level = CAUTION
3. If regime = HOLD -> risk_level = BLOCKED
4. REFLEXIVE + emotional discourse -> block emphasis
5. Any detected attempt at certainty escalation -> violation

Design Principles:
- Deterministic: No LLM calls, no probabilistic thresholds
- Capping-Only: May only reduce, never amplify
- Binding: Output is binding on all downstream phases
- Conservative: BLOCKED is always safe
- No Inference: No emotion detection, no prosody interpretation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from symbolu.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_schema import (
    AcousticRiskLevel,
    AcousticSafetyEnvelope,
    SafetyViolation,
    P13_VERSION,
    get_blocked_envelope,
    # Absolute bounds
    ABSOLUTE_PITCH_MIN,
    ABSOLUTE_PITCH_MAX,
    ABSOLUTE_ENERGY_MIN,
    ABSOLUTE_ENERGY_MAX,
    ABSOLUTE_VARIANCE_MIN,
    ABSOLUTE_VARIANCE_MAX,
    # Regime-specific bounds
    HOLD_PITCH_MIN,
    HOLD_PITCH_MAX,
    HOLD_ENERGY_MIN,
    HOLD_ENERGY_MAX,
    HOLD_VARIANCE_MAX,
    DE_ESCALATE_PITCH_MIN,
    DE_ESCALATE_PITCH_MAX,
    DE_ESCALATE_ENERGY_MIN,
    DE_ESCALATE_ENERGY_MAX,
    DE_ESCALATE_VARIANCE_MAX,
    REFLEXIVE_ENERGY_MAX,
    REFLEXIVE_VARIANCE_MAX,
)


# ============================================================================
# CONSTANTS - Regime and Discourse Mappings
# ============================================================================


# Regimes that require BLOCKED risk level
BLOCKED_REGIMES = frozenset({"HOLD"})

# Regimes that require restrictive bounds (no emphasis, no contours)
RESTRICTIVE_REGIMES = frozenset({
    "HOLD", "DE_ESCALATE", "STABILIZE", "REFLECT"
})

# Discourse acts that indicate emotional content
EMOTIONAL_DISCOURSE_ACTS = frozenset({
    "REFLECTION",  # Mirroring user's emotional state
})

# Discourse acts that should have minimal prosodic motion
MINIMAL_MOTION_DISCOURSE_ACTS = frozenset({
    "DEFERRAL",
    "ACKNOWLEDGMENT",
})

# Grounding modes that prohibit emphasis and authority signaling
AUTHORITY_RESTRICTED_GROUNDING_MODES = frozenset({
    "REFLEXIVE",
    "RELATIONAL",
})

# Energy threshold above which is considered potentially manipulative
MANIPULATION_ENERGY_THRESHOLD = 0.55

# Variance threshold above which is considered potentially manipulative
MANIPULATION_VARIANCE_THRESHOLD = 35


# ============================================================================
# SAFETY CHECK FUNCTIONS
# ============================================================================


def detect_emotion_amplification(
    source_regime: str,
    p10_energy: float,
    p10_emphasis_policy: str,
    p10_suppress_emotion: bool,
) -> Optional[SafetyViolation]:
    """
    Detect attempts to amplify emotional expression beyond safe bounds.

    RULE: Restrictive regimes with non-suppressed emotion OR high energy
          indicate emotion amplification attempt.

    Returns:
        SafetyViolation.EMOTION_AMPLIFICATION if detected, None otherwise.
    """
    if source_regime in RESTRICTIVE_REGIMES:
        # Under restrictive regimes, emotion should be suppressed
        if not p10_suppress_emotion:
            return SafetyViolation.EMOTION_AMPLIFICATION
        # High energy in restrictive regime indicates amplification attempt
        if p10_energy > HOLD_ENERGY_MAX:
            return SafetyViolation.EMOTION_AMPLIFICATION
    return None


def detect_certainty_escalation(
    source_regime: str,
    p10_suppress_certainty: bool,
    p10_emphasis_policy: str,
    p10_max_stressed_tokens: int,
    grounding_mode: Optional[str],
) -> Optional[SafetyViolation]:
    """
    Detect attempts to signal unwarranted certainty.

    RULE: Certainty escalation detected if:
    - Restrictive regime without certainty suppression
    - REFLEXIVE/RELATIONAL grounding without certainty suppression
    - Emphasis under authority-restricted grounding

    Returns:
        SafetyViolation.CERTAINTY_ESCALATION if detected, None otherwise.
    """
    # Check regime-based certainty requirements
    if source_regime in RESTRICTIVE_REGIMES:
        if not p10_suppress_certainty:
            return SafetyViolation.CERTAINTY_ESCALATION

    # Check grounding-based certainty requirements
    if grounding_mode in AUTHORITY_RESTRICTED_GROUNDING_MODES:
        if not p10_suppress_certainty:
            return SafetyViolation.CERTAINTY_ESCALATION
        # Emphasis under authority-restricted grounding = certainty signal
        if p10_emphasis_policy != "none" or p10_max_stressed_tokens > 0:
            return SafetyViolation.CERTAINTY_ESCALATION

    return None


def detect_authority_signaling(
    source_regime: str,
    source_discourse_act: str,
    grounding_mode: Optional[str],
    p10_suppress_emphasis: bool,
    p10_emphasis_policy: str,
    p10_max_stressed_tokens: int,
    p10_energy: float,
) -> Optional[SafetyViolation]:
    """
    Detect attempts to signal dominance or authority.

    RULE: Authority signaling detected if:
    - Emphasis under authority-restricted grounding
    - High energy under REFLEXIVE/RELATIONAL grounding
    - Emphasis during REFLECTION discourse

    Returns:
        SafetyViolation.AUTHORITY_SIGNALING if detected, None otherwise.
    """
    # Authority-restricted grounding modes
    if grounding_mode in AUTHORITY_RESTRICTED_GROUNDING_MODES:
        if not p10_suppress_emphasis:
            return SafetyViolation.AUTHORITY_SIGNALING
        if p10_emphasis_policy != "none" or p10_max_stressed_tokens > 0:
            return SafetyViolation.AUTHORITY_SIGNALING
        if p10_energy > REFLEXIVE_ENERGY_MAX:
            return SafetyViolation.AUTHORITY_SIGNALING

    # REFLECTION discourse should not have emphasis (would signal authority)
    if source_discourse_act == "REFLECTION":
        if p10_emphasis_policy != "none" or p10_max_stressed_tokens > 0:
            return SafetyViolation.AUTHORITY_SIGNALING

    return None


def detect_excessive_variance(
    source_regime: str,
    p10_pitch_range: Tuple[int, int],
    p10_energy: float,
) -> Optional[SafetyViolation]:
    """
    Detect excessive acoustic variance beyond safe bounds.

    RULE: Excessive variance detected if:
    - Pitch variance exceeds regime-specific limit
    - Energy exceeds regime-specific limit

    Returns:
        SafetyViolation.EXCESSIVE_VARIANCE if detected, None otherwise.
    """
    pitch_variance = p10_pitch_range[1] - p10_pitch_range[0]

    # HOLD regime has strictest variance requirements
    if source_regime == "HOLD":
        if pitch_variance > HOLD_VARIANCE_MAX:
            return SafetyViolation.EXCESSIVE_VARIANCE
        if p10_energy > HOLD_ENERGY_MAX:
            return SafetyViolation.EXCESSIVE_VARIANCE

    # DE_ESCALATE/STABILIZE have moderate variance requirements
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        if pitch_variance > DE_ESCALATE_VARIANCE_MAX:
            return SafetyViolation.EXCESSIVE_VARIANCE
        if p10_energy > DE_ESCALATE_ENERGY_MAX:
            return SafetyViolation.EXCESSIVE_VARIANCE

    # Absolute variance limits
    if pitch_variance > MANIPULATION_VARIANCE_THRESHOLD:
        return SafetyViolation.EXCESSIVE_VARIANCE

    return None


def detect_prosodic_manipulation(
    source_regime: str,
    source_discourse_act: str,
    p10_pitch_range: Tuple[int, int],
    p10_energy: float,
    p10_emphasis_policy: str,
    p10_max_stressed_tokens: int,
) -> Optional[SafetyViolation]:
    """
    Detect attempts to manipulate through prosodic features.

    RULE: Prosodic manipulation detected if:
    - High energy + high variance (persuasion pattern)
    - Multiple stressed tokens under restrictive discourse
    - Energy exceeds absolute manipulation threshold

    Returns:
        SafetyViolation.PROSODIC_MANIPULATION if detected, None otherwise.
    """
    pitch_variance = p10_pitch_range[1] - p10_pitch_range[0]

    # High energy + high variance = persuasion pattern
    if p10_energy > MANIPULATION_ENERGY_THRESHOLD:
        if pitch_variance > ABSOLUTE_VARIANCE_MAX:
            return SafetyViolation.PROSODIC_MANIPULATION

    # Multiple stressed tokens under minimal-motion discourse
    if source_discourse_act in MINIMAL_MOTION_DISCOURSE_ACTS:
        if p10_max_stressed_tokens > 0:
            return SafetyViolation.PROSODIC_MANIPULATION
        if pitch_variance > 15:  # DEFERRAL/ACKNOWLEDGMENT should be very flat
            return SafetyViolation.PROSODIC_MANIPULATION

    return None


# ============================================================================
# BOUNDS COMPUTATION FUNCTIONS
# ============================================================================


def compute_pitch_bounds(
    source_regime: str,
    p10_pitch_range: Tuple[int, int],
    risk_level: AcousticRiskLevel,
) -> Tuple[int, int]:
    """
    Compute allowed pitch bounds (capping only, never amplifying).

    The computed bounds are always <= P10 bounds.
    """
    p10_low, p10_high = p10_pitch_range

    # BLOCKED -> most restrictive
    if risk_level == AcousticRiskLevel.BLOCKED or source_regime == "HOLD":
        return (
            max(HOLD_PITCH_MIN, p10_low),
            min(HOLD_PITCH_MAX, p10_high),
        )

    # DE_ESCALATE/STABILIZE -> moderately restrictive
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        return (
            max(DE_ESCALATE_PITCH_MIN, p10_low),
            min(DE_ESCALATE_PITCH_MAX, p10_high),
        )

    # CAUTION -> cap to absolute bounds
    if risk_level == AcousticRiskLevel.CAUTION:
        return (
            max(ABSOLUTE_PITCH_MIN, p10_low),
            min(ABSOLUTE_PITCH_MAX, p10_high),
        )

    # SAFE -> use P10 bounds (clamped to absolute)
    return (
        max(ABSOLUTE_PITCH_MIN, p10_low),
        min(ABSOLUTE_PITCH_MAX, p10_high),
    )


def compute_energy_bounds(
    source_regime: str,
    p10_energy: float,
    grounding_mode: Optional[str],
    risk_level: AcousticRiskLevel,
) -> Tuple[float, float]:
    """
    Compute allowed energy bounds (capping only, never amplifying).

    The max energy is always <= P10 energy.
    """
    # Start with P10's energy as max
    max_energy = p10_energy

    # BLOCKED -> most restrictive
    if risk_level == AcousticRiskLevel.BLOCKED or source_regime == "HOLD":
        max_energy = min(max_energy, HOLD_ENERGY_MAX)
        return (HOLD_ENERGY_MIN, max_energy)

    # DE_ESCALATE/STABILIZE -> moderately restrictive
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        max_energy = min(max_energy, DE_ESCALATE_ENERGY_MAX)
        return (DE_ESCALATE_ENERGY_MIN, max_energy)

    # REFLEXIVE/RELATIONAL grounding -> energy cap
    if grounding_mode in AUTHORITY_RESTRICTED_GROUNDING_MODES:
        max_energy = min(max_energy, REFLEXIVE_ENERGY_MAX)
        return (ABSOLUTE_ENERGY_MIN, max_energy)

    # CAUTION or SAFE -> cap to absolute
    max_energy = min(max_energy, ABSOLUTE_ENERGY_MAX)
    return (ABSOLUTE_ENERGY_MIN, max_energy)


def compute_variance_bounds(
    source_regime: str,
    p10_pitch_range: Tuple[int, int],
    grounding_mode: Optional[str],
    risk_level: AcousticRiskLevel,
) -> Tuple[int, int]:
    """
    Compute allowed variance bounds (capping only, never amplifying).

    The max variance is always <= P10's pitch variance.
    """
    p10_variance = p10_pitch_range[1] - p10_pitch_range[0]

    # BLOCKED -> most restrictive
    if risk_level == AcousticRiskLevel.BLOCKED or source_regime == "HOLD":
        return (0, min(p10_variance, HOLD_VARIANCE_MAX))

    # DE_ESCALATE/STABILIZE -> moderately restrictive
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        return (0, min(p10_variance, DE_ESCALATE_VARIANCE_MAX))

    # REFLEXIVE/RELATIONAL grounding -> variance cap
    if grounding_mode in AUTHORITY_RESTRICTED_GROUNDING_MODES:
        return (0, min(p10_variance, REFLEXIVE_VARIANCE_MAX))

    # CAUTION or SAFE -> cap to absolute
    return (0, min(p10_variance, ABSOLUTE_VARIANCE_MAX))


def compute_expression_flags(
    source_regime: str,
    source_discourse_act: str,
    grounding_mode: Optional[str],
    p10_emphasis_policy: str,
    p10_suppress_emphasis: bool,
    risk_level: AcousticRiskLevel,
) -> Dict[str, bool]:
    """
    Compute allowed expression flags (disabling only, never enabling).

    Returns dict with allow_emphasis, allow_pitch_contours,
    allow_rhythm_variation, allow_intonation_shift.
    """
    # Start with P10's state
    allow_emphasis = (
        p10_emphasis_policy != "none" and
        not p10_suppress_emphasis
    )
    allow_pitch_contours = True
    allow_rhythm_variation = True
    allow_intonation_shift = True

    # BLOCKED or HOLD -> disable all
    if risk_level == AcousticRiskLevel.BLOCKED or source_regime == "HOLD":
        return {
            "allow_emphasis": False,
            "allow_pitch_contours": False,
            "allow_rhythm_variation": False,
            "allow_intonation_shift": False,
        }

    # DE_ESCALATE/STABILIZE -> disable emphasis and contours
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        allow_emphasis = False
        allow_pitch_contours = False

    # REFLECTION discourse -> no emphasis (would signal authority)
    if source_discourse_act == "REFLECTION":
        allow_emphasis = False

    # REFLEXIVE/RELATIONAL grounding -> no emphasis
    if grounding_mode in AUTHORITY_RESTRICTED_GROUNDING_MODES:
        allow_emphasis = False

    # DEFERRAL/ACKNOWLEDGMENT -> minimal motion
    if source_discourse_act in MINIMAL_MOTION_DISCOURSE_ACTS:
        allow_emphasis = False
        allow_pitch_contours = False

    # CAUTION -> reduce expressiveness
    if risk_level == AcousticRiskLevel.CAUTION:
        allow_emphasis = False

    return {
        "allow_emphasis": allow_emphasis,
        "allow_pitch_contours": allow_pitch_contours,
        "allow_rhythm_variation": allow_rhythm_variation,
        "allow_intonation_shift": allow_intonation_shift,
    }


# ============================================================================
# MAIN RESOLVER CLASS
# ============================================================================


class P13AcousticSafetyResolver:
    """
    Acoustic Safety Envelope Resolver.

    This resolver computes the absolute safety bounds for acoustic expression.
    It ONLY caps, constrains, and vetoes - it NEVER amplifies.

    CRITICAL: P13 is the last safety lock before sound.
    Phase 1 (acoustic tokenization) must consume P13 verbatim.
    Renderers violating P13 are considered unsafe by design.

    Usage:
        resolver = P13AcousticSafetyResolver()
        envelope = resolver.resolve(ctx)
    """

    def __init__(self) -> None:
        """Initialize the P13 Acoustic Safety Resolver."""
        pass

    def _get_timestamp_utc(self) -> str:
        """Get current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _extract_context_data(self, ctx: Any) -> Dict[str, Any]:
        """
        Extract relevant data from pipeline context.

        This method safely extracts data without modifying the context.
        Returns a dictionary with all needed fields or safe defaults.
        """
        data: Dict[str, Any] = {
            "source_regime": "UNKNOWN",
            "source_discourse_act": "UNKNOWN",
            "grounding_mode": None,
            "p10_version": "P10-unknown",
            "p12_consistent": False,
            "p12_has_critical": False,
            # P10 fields
            "p10_pitch_range": (95, 105),  # Safe default
            "p10_energy": 0.25,
            "p10_emphasis_policy": "none",
            "p10_max_stressed_tokens": 0,
            "p10_suppress_emotion": True,
            "p10_suppress_emphasis": True,
            "p10_suppress_certainty": True,
            "has_p10": False,
        }

        # Extract P6 regime
        if hasattr(ctx, 'p6_regime') and ctx.p6_regime is not None:
            data["source_regime"] = ctx.p6_regime.regime.value

        # Extract P7 discourse act
        if hasattr(ctx, 'p7_discourse_envelope') and ctx.p7_discourse_envelope is not None:
            data["source_discourse_act"] = ctx.p7_discourse_envelope.act.value

        # Extract PO1 grounding mode
        if hasattr(ctx, 'phase_minus_one') and ctx.phase_minus_one is not None:
            if ctx.phase_minus_one.selected_primary is not None:
                data["grounding_mode"] = ctx.phase_minus_one.selected_primary.mode.value

        # Extract P12 consistency
        if hasattr(ctx, 'p12_consistency') and ctx.p12_consistency is not None:
            data["p12_consistent"] = ctx.p12_consistency.is_consistent
            data["p12_has_critical"] = ctx.p12_consistency.has_critical_violations()

        # Extract P10 acoustic parameters
        if hasattr(ctx, 'p10_acoustic') and ctx.p10_acoustic is not None:
            data["has_p10"] = True
            p10 = ctx.p10_acoustic
            data["p10_version"] = f"P10-{p10.architectural_phase}"
            data["p10_pitch_range"] = p10.pitch_range
            data["p10_energy"] = p10.energy_level
            data["p10_emphasis_policy"] = p10.emphasis_policy.value
            data["p10_max_stressed_tokens"] = p10.max_stressed_tokens
            data["p10_suppress_emotion"] = p10.suppress_emotion
            data["p10_suppress_emphasis"] = p10.suppress_emphasis
            data["p10_suppress_certainty"] = p10.suppress_certainty

        return data

    def _determine_risk_level(
        self,
        source_regime: str,
        p12_consistent: bool,
        p12_has_critical: bool,
        violations: List[SafetyViolation],
    ) -> AcousticRiskLevel:
        """
        Determine the risk level based on regime and violations.

        RULES:
        - HOLD regime -> BLOCKED
        - P12 inconsistent with critical violations -> BLOCKED
        - P12 inconsistent -> CAUTION
        - Any violations -> CAUTION
        - Otherwise -> SAFE
        """
        # HOLD regime always BLOCKED
        if source_regime == "HOLD":
            return AcousticRiskLevel.BLOCKED

        # P12 critical violations -> BLOCKED
        if not p12_consistent and p12_has_critical:
            return AcousticRiskLevel.BLOCKED

        # P12 mismatch -> CAUTION
        if not p12_consistent:
            return AcousticRiskLevel.CAUTION

        # Any safety violations -> CAUTION
        if violations:
            return AcousticRiskLevel.CAUTION

        return AcousticRiskLevel.SAFE

    def resolve(self, ctx: Any) -> Optional[AcousticSafetyEnvelope]:
        """
        Resolve the acoustic safety envelope from pipeline context.

        This method computes the absolute safety bounds for acoustic
        expression. It ONLY caps, constrains, and vetoes - NEVER amplifies.

        CRITICAL: P13 is binding. Downstream renderers must respect
        the envelope. Violating the envelope is considered unsafe.

        Args:
            ctx: Pipeline context with all phase outputs.

        Returns:
            AcousticSafetyEnvelope with safety bounds, or None if P10 missing.
        """
        # Extract context data
        data = self._extract_context_data(ctx)
        timestamp = self._get_timestamp_utc()

        # If P10 is missing, return BLOCKED envelope
        if not data["has_p10"]:
            return get_blocked_envelope(
                source_regime=data["source_regime"],
                source_discourse_act=data["source_discourse_act"],
                source_p10_version=data["p10_version"],
                source_p12_consistent=data["p12_consistent"],
                timestamp_utc=timestamp,
            )

        # Detect safety violations
        violations: List[SafetyViolation] = []

        emotion_amp = detect_emotion_amplification(
            data["source_regime"],
            data["p10_energy"],
            data["p10_emphasis_policy"],
            data["p10_suppress_emotion"],
        )
        if emotion_amp:
            violations.append(emotion_amp)

        certainty_esc = detect_certainty_escalation(
            data["source_regime"],
            data["p10_suppress_certainty"],
            data["p10_emphasis_policy"],
            data["p10_max_stressed_tokens"],
            data["grounding_mode"],
        )
        if certainty_esc:
            violations.append(certainty_esc)

        authority_sig = detect_authority_signaling(
            data["source_regime"],
            data["source_discourse_act"],
            data["grounding_mode"],
            data["p10_suppress_emphasis"],
            data["p10_emphasis_policy"],
            data["p10_max_stressed_tokens"],
            data["p10_energy"],
        )
        if authority_sig:
            violations.append(authority_sig)

        excessive_var = detect_excessive_variance(
            data["source_regime"],
            data["p10_pitch_range"],
            data["p10_energy"],
        )
        if excessive_var:
            violations.append(excessive_var)

        prosodic_manip = detect_prosodic_manipulation(
            data["source_regime"],
            data["source_discourse_act"],
            data["p10_pitch_range"],
            data["p10_energy"],
            data["p10_emphasis_policy"],
            data["p10_max_stressed_tokens"],
        )
        if prosodic_manip:
            violations.append(prosodic_manip)

        # Determine risk level
        risk_level = self._determine_risk_level(
            data["source_regime"],
            data["p12_consistent"],
            data["p12_has_critical"],
            violations,
        )

        # For BLOCKED, return blocked envelope
        if risk_level == AcousticRiskLevel.BLOCKED:
            return get_blocked_envelope(
                source_regime=data["source_regime"],
                source_discourse_act=data["source_discourse_act"],
                source_p10_version=data["p10_version"],
                source_p12_consistent=data["p12_consistent"],
                violations=tuple(violations),
                timestamp_utc=timestamp,
            )

        # Compute bounds (capping only)
        pitch_bounds = compute_pitch_bounds(
            data["source_regime"],
            data["p10_pitch_range"],
            risk_level,
        )

        energy_bounds = compute_energy_bounds(
            data["source_regime"],
            data["p10_energy"],
            data["grounding_mode"],
            risk_level,
        )

        variance_bounds = compute_variance_bounds(
            data["source_regime"],
            data["p10_pitch_range"],
            data["grounding_mode"],
            risk_level,
        )

        # Compute expression flags
        expression_flags = compute_expression_flags(
            data["source_regime"],
            data["source_discourse_act"],
            data["grounding_mode"],
            data["p10_emphasis_policy"],
            data["p10_suppress_emphasis"],
            risk_level,
        )

        # Build envelope
        return AcousticSafetyEnvelope(
            allowed_pitch_range=pitch_bounds,
            allowed_energy_range=energy_bounds,
            allowed_variance_range=variance_bounds,
            allow_emphasis=expression_flags["allow_emphasis"],
            allow_pitch_contours=expression_flags["allow_pitch_contours"],
            allow_rhythm_variation=expression_flags["allow_rhythm_variation"],
            allow_intonation_shift=expression_flags["allow_intonation_shift"],
            risk_level=risk_level,
            violations=tuple(violations),
            source_regime=data["source_regime"],
            source_discourse_act=data["source_discourse_act"],
            source_p10_version=data["p10_version"],
            source_p12_consistent=data["p12_consistent"],
            timestamp_utc=timestamp,
        )


# Public exports
__all__ = [
    # Constants
    "BLOCKED_REGIMES",
    "RESTRICTIVE_REGIMES",
    "EMOTIONAL_DISCOURSE_ACTS",
    "MINIMAL_MOTION_DISCOURSE_ACTS",
    "AUTHORITY_RESTRICTED_GROUNDING_MODES",
    "MANIPULATION_ENERGY_THRESHOLD",
    "MANIPULATION_VARIANCE_THRESHOLD",
    # Safety check functions
    "detect_emotion_amplification",
    "detect_certainty_escalation",
    "detect_authority_signaling",
    "detect_excessive_variance",
    "detect_prosodic_manipulation",
    # Bounds computation functions
    "compute_pitch_bounds",
    "compute_energy_bounds",
    "compute_variance_bounds",
    "compute_expression_flags",
    # Resolver class
    "P13AcousticSafetyResolver",
]
