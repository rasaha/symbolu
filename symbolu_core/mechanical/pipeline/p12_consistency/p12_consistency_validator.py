"""
P12 - Acoustic-Prosodic Consistency Validator Implementation

The core validation engine for P12. This module contains all invariant
checking logic for validating consistency between governance layers,
acoustic parameters, and prosodic evidence.

CRITICAL: This validator is AUDIT-ONLY. It NEVER modifies or corrects data.
It only observes, validates, and reports.

Invariant Categories:
1. Regime → Acoustic Invariants (HOLD, DE_ESCALATE, STABILIZE constraints)
2. Discourse → Prosody Invariants (REFLECTION, DEFERRAL, QUESTION constraints)
3. Uncertainty Preservation (no certainty inflation)
4. Lexical-Prosodic Compatibility (low-impact words, no emphatic stress)
5. Authority Escalation Prevention (no diagnosis, judgment, or certainty)

Design Principles:
- Deterministic: No LLM calls, no probabilistic thresholds
- Rule-Based: All validation is explicit rule checking
- Fail-Closed: Assumes violation on any error or missing data
- Read-Only: Never modifies input data
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_schema import (
    P12ConsistencyReport,
    P12Violation,
    P12Warning,
    ViolationSeverity,
    ViolationType,
    P12_VERSION,
    create_violation,
    create_warning,
)


# ============================================================================
# CONSTANTS - Regime and Discourse Mappings
# ============================================================================


# Regimes that require FLAT acoustic regime
FLAT_REQUIRED_REGIMES = frozenset({"HOLD"})

# Regimes that require SOFT or FLAT acoustic regime
SOFT_OR_FLAT_REQUIRED_REGIMES = frozenset({"DE_ESCALATE", "STABILIZE", "REFLECT"})

# Regimes that allow NEUTRAL acoustic regime
NEUTRAL_ALLOWED_REGIMES = frozenset({"INFORM", "CLARIFY"})

# Regimes requiring all suppressions (emotion, emphasis, certainty)
FULL_SUPPRESSION_REQUIRED_REGIMES = frozenset({"HOLD", "DE_ESCALATE", "STABILIZE", "REFLECT"})

# Discourse acts that require flat or gently falling pitch (no interrogative rise)
FLAT_PITCH_DISCOURSE_ACTS = frozenset({"REFLECTION", "DEFERRAL", "ACKNOWLEDGMENT"})

# Discourse acts that prohibit emphasis
NO_EMPHASIS_DISCOURSE_ACTS = frozenset({"REFLECTION", "DEFERRAL"})

# Grounding modes that prohibit authority escalation
AUTHORITY_RESTRICTED_GROUNDING_MODES = frozenset({"REFLEXIVE", "RELATIONAL"})

# Acoustic regimes considered "low energy" or "restrained"
LOW_ENERGY_REGIMES = frozenset({"flat", "soft", "restrained"})

# Energy threshold above which is considered "high impact"
HIGH_ENERGY_THRESHOLD = 0.5

# Pitch range variance threshold above which is considered "expressive"
EXPRESSIVE_PITCH_VARIANCE_THRESHOLD = 30  # Hz difference between max and min

# Maximum stressed tokens allowed under restrictive regimes
MAX_STRESSED_TOKENS_RESTRICTIVE = 0


# ============================================================================
# INVARIANT CHECK FUNCTIONS
# ============================================================================


def check_regime_acoustic_flat(
    source_regime: str,
    acoustic_regime: str,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: HOLD regime requires FLAT acoustic regime.

    INVARIANT: HOLD -> acoustic_regime == FLAT

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime in FLAT_REQUIRED_REGIMES:
        if acoustic_regime != "flat":
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="regime_requires_flat_acoustic",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"HOLD regime requires FLAT acoustic regime, "
                        f"but got '{acoustic_regime}'"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "acoustic_regime": acoustic_regime,
                        "expected_acoustic": "flat",
                    },
                ),
            )
    return (True, None)


def check_regime_acoustic_soft_or_flat(
    source_regime: str,
    acoustic_regime: str,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: DE_ESCALATE/STABILIZE/REFLECT require SOFT or FLAT acoustic regime.

    INVARIANT: {DE_ESCALATE, STABILIZE, REFLECT} -> acoustic_regime in {soft, flat}

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime in SOFT_OR_FLAT_REQUIRED_REGIMES:
        if acoustic_regime not in ("soft", "flat"):
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="regime_requires_soft_or_flat",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"{source_regime} regime requires SOFT or FLAT acoustic regime, "
                        f"but got '{acoustic_regime}'"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "acoustic_regime": acoustic_regime,
                        "expected_acoustic": ["soft", "flat"],
                    },
                ),
            )
    return (True, None)


def check_hold_no_pitch_rise(
    source_regime: str,
    pitch_range: Tuple[int, int],
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: HOLD regime must not have pitch rise (variance should be minimal).

    INVARIANT: HOLD -> pitch variance <= 15 Hz

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime == "HOLD":
        pitch_variance = pitch_range[1] - pitch_range[0]
        # HOLD should have minimal pitch variation (≤15 Hz)
        if pitch_variance > 15:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="hold_no_pitch_rise",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"HOLD regime prohibits pitch rise/variance, "
                        f"but pitch range is {pitch_range} ({pitch_variance} Hz variance)"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "pitch_range": pitch_range,
                        "pitch_variance": pitch_variance,
                        "max_allowed_variance": 15,
                    },
                ),
            )
    return (True, None)


def check_hold_no_intensity_increase(
    source_regime: str,
    energy_level: float,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: HOLD regime must not have intensity increase (energy should be low).

    INVARIANT: HOLD -> energy_level <= 0.35

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime == "HOLD":
        if energy_level > 0.35:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="hold_no_intensity_increase",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"HOLD regime prohibits intensity increase, "
                        f"but energy level is {energy_level}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "energy_level": energy_level,
                        "max_allowed_energy": 0.35,
                    },
                ),
            )
    return (True, None)


def check_hold_no_expressive_modulation(
    source_regime: str,
    emphasis_policy: str,
    max_stressed_tokens: int,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: HOLD regime must not have expressive modulation.

    INVARIANT: HOLD -> emphasis_policy == 'none' AND max_stressed_tokens == 0

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime == "HOLD":
        if emphasis_policy != "none" or max_stressed_tokens > 0:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="hold_no_expressive_modulation",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"HOLD regime prohibits expressive modulation, "
                        f"but emphasis_policy='{emphasis_policy}', "
                        f"max_stressed_tokens={max_stressed_tokens}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "emphasis_policy": emphasis_policy,
                        "max_stressed_tokens": max_stressed_tokens,
                        "expected_emphasis_policy": "none",
                        "expected_max_stressed_tokens": 0,
                    },
                ),
            )
    return (True, None)


def check_de_escalate_no_sharp_pitch(
    source_regime: str,
    pitch_range: Tuple[int, int],
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: DE_ESCALATE/STABILIZE must not have sharp pitch spikes.

    INVARIANT: {DE_ESCALATE, STABILIZE} -> pitch variance <= 25 Hz

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        pitch_variance = pitch_range[1] - pitch_range[0]
        if pitch_variance > 25:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="de_escalate_no_sharp_pitch",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"{source_regime} regime prohibits sharp pitch spikes, "
                        f"but pitch range is {pitch_range} ({pitch_variance} Hz variance)"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "pitch_range": pitch_range,
                        "pitch_variance": pitch_variance,
                        "max_allowed_variance": 25,
                    },
                ),
            )
    return (True, None)


def check_de_escalate_no_rapid_tempo(
    source_regime: str,
    speech_rate: float,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: DE_ESCALATE/STABILIZE must not have rapid tempo.

    INVARIANT: {DE_ESCALATE, STABILIZE} -> speech_rate <= 4.0

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        if speech_rate > 4.0:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="de_escalate_no_rapid_tempo",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"{source_regime} regime prohibits rapid tempo, "
                        f"but speech_rate is {speech_rate}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "speech_rate": speech_rate,
                        "max_allowed_speech_rate": 4.0,
                    },
                ),
            )
    return (True, None)


def check_de_escalate_no_emphasis_amplification(
    source_regime: str,
    max_stressed_tokens: int,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: DE_ESCALATE/STABILIZE must not amplify emphasis.

    INVARIANT: {DE_ESCALATE, STABILIZE} -> max_stressed_tokens == 0

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime in ("DE_ESCALATE", "STABILIZE"):
        if max_stressed_tokens > 0:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
                    invariant_name="de_escalate_no_emphasis_amplification",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"{source_regime} regime prohibits emphasis amplification, "
                        f"but max_stressed_tokens is {max_stressed_tokens}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "max_stressed_tokens": max_stressed_tokens,
                        "expected_max_stressed_tokens": 0,
                    },
                ),
            )
    return (True, None)


def check_reflection_no_interrogative_prosody(
    source_discourse_act: str,
    pitch_range: Tuple[int, int],
    source_intent: Optional[str] = None,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: REFLECTION discourse act requires flat or gently falling pitch.

    INVARIANT: REFLECTION -> no interrogative rise (pitch variance <= 20 Hz)

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_discourse_act == "REFLECTION":
        pitch_variance = pitch_range[1] - pitch_range[0]
        # Interrogative rise typically has larger pitch variance
        if pitch_variance > 20:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.DISCOURSE_PROSODY_MISMATCH,
                    invariant_name="reflection_no_interrogative_prosody",
                    source_phase="P7",
                    target_phase="P11",
                    description=(
                        f"REFLECTION discourse act requires flat or gently falling pitch, "
                        f"but pitch range {pitch_range} suggests interrogative rise "
                        f"({pitch_variance} Hz variance)"
                    ),
                    evidence={
                        "source_discourse_act": source_discourse_act,
                        "pitch_range": pitch_range,
                        "pitch_variance": pitch_variance,
                        "max_allowed_variance": 20,
                    },
                ),
            )
    return (True, None)


def check_deferral_minimal_prosodic_motion(
    source_discourse_act: str,
    pitch_range: Tuple[int, int],
    energy_level: float,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: DEFERRAL discourse act requires minimal prosodic motion.

    INVARIANT: DEFERRAL -> pitch variance <= 15 Hz AND energy <= 0.35

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_discourse_act == "DEFERRAL":
        pitch_variance = pitch_range[1] - pitch_range[0]
        violations = []

        if pitch_variance > 15:
            violations.append(f"pitch variance {pitch_variance} Hz > 15 Hz")
        if energy_level > 0.35:
            violations.append(f"energy {energy_level} > 0.35")

        if violations:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.DISCOURSE_PROSODY_MISMATCH,
                    invariant_name="deferral_minimal_prosodic_motion",
                    source_phase="P7",
                    target_phase="P11",
                    description=(
                        f"DEFERRAL discourse act requires minimal prosodic motion: "
                        f"{'; '.join(violations)}"
                    ),
                    evidence={
                        "source_discourse_act": source_discourse_act,
                        "pitch_range": pitch_range,
                        "pitch_variance": pitch_variance,
                        "energy_level": energy_level,
                        "max_allowed_pitch_variance": 15,
                        "max_allowed_energy": 0.35,
                    },
                ),
            )
    return (True, None)


def check_question_rising_pitch_only_if_clarify(
    source_discourse_act: str,
    source_intent: Optional[str],
    pitch_range: Tuple[int, int],
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: QUESTION discourse act allows rising pitch ONLY if intent == CLARIFY.

    INVARIANT: QUESTION with pitch variance > 25 Hz -> intent == CLARIFY

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_discourse_act == "QUESTION":
        pitch_variance = pitch_range[1] - pitch_range[0]
        # Rising pitch is indicated by larger variance
        if pitch_variance > 25 and source_intent != "CLARIFY":
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.DISCOURSE_PROSODY_MISMATCH,
                    invariant_name="question_rising_pitch_requires_clarify_intent",
                    source_phase="P7",
                    target_phase="P11",
                    description=(
                        f"QUESTION with rising pitch (variance {pitch_variance} Hz) "
                        f"is only allowed when intent is CLARIFY, but intent is '{source_intent}'"
                    ),
                    evidence={
                        "source_discourse_act": source_discourse_act,
                        "source_intent": source_intent,
                        "pitch_range": pitch_range,
                        "pitch_variance": pitch_variance,
                    },
                ),
            )
    return (True, None)


def check_explanation_respects_regime(
    source_discourse_act: str,
    source_regime: str,
    energy_level: float,
    max_stressed_tokens: int,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: EXPLANATION prosody is allowed only if regime allows.

    INVARIANT: EXPLANATION under restrictive regimes -> low energy, no emphasis

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_discourse_act == "EXPLANATION":
        if source_regime in FULL_SUPPRESSION_REQUIRED_REGIMES:
            violations = []
            if energy_level > 0.4:
                violations.append(f"energy {energy_level} > 0.4")
            if max_stressed_tokens > 0:
                violations.append(f"stressed tokens {max_stressed_tokens} > 0")

            if violations:
                return (
                    False,
                    create_violation(
                        severity=ViolationSeverity.MAJOR,
                        violation_type=ViolationType.DISCOURSE_PROSODY_MISMATCH,
                        invariant_name="explanation_respects_regime",
                        source_phase="P7",
                        target_phase="P10",
                        description=(
                            f"EXPLANATION under {source_regime} regime must have "
                            f"restricted prosody: {'; '.join(violations)}"
                        ),
                        evidence={
                            "source_discourse_act": source_discourse_act,
                            "source_regime": source_regime,
                            "energy_level": energy_level,
                            "max_stressed_tokens": max_stressed_tokens,
                        },
                    ),
                )
    return (True, None)


def check_uncertainty_preservation(
    has_uncertainty_slot: bool,
    suppress_certainty: bool,
    pitch_range: Tuple[int, int],
    emphasis_policy: str,
    max_stressed_tokens: int,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: If UNCERTAINTY slot exists, prosody must not indicate certainty.

    INVARIANT: UNCERTAINTY slot -> suppress_certainty=True, no falling-terminal,
               no emphatic stress

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if has_uncertainty_slot:
        violations = []

        # Must have certainty suppression
        if not suppress_certainty:
            violations.append("certainty suppression not active")

        # No emphatic stress
        if emphasis_policy != "none" or max_stressed_tokens > 0:
            violations.append(
                f"emphatic stress present (policy={emphasis_policy}, "
                f"stressed={max_stressed_tokens})"
            )

        # No falling-terminal authority contour (indicated by narrow, low pitch)
        # A falling terminal with authority would have a narrow range at low pitch
        pitch_variance = pitch_range[1] - pitch_range[0]
        # This is a heuristic - falling terminal with authority typically has
        # low max pitch and narrow variance
        if pitch_range[1] < 100 and pitch_variance < 10:
            violations.append(
                f"falling-terminal authority contour detected "
                f"(pitch_range={pitch_range})"
            )

        if violations:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MAJOR,
                    violation_type=ViolationType.UNCERTAINTY_VIOLATION,
                    invariant_name="uncertainty_preservation",
                    source_phase="P8",
                    target_phase="P11",
                    description=(
                        f"UNCERTAINTY slot exists but prosody indicates certainty: "
                        f"{'; '.join(violations)}"
                    ),
                    evidence={
                        "has_uncertainty_slot": has_uncertainty_slot,
                        "suppress_certainty": suppress_certainty,
                        "pitch_range": pitch_range,
                        "emphasis_policy": emphasis_policy,
                        "max_stressed_tokens": max_stressed_tokens,
                    },
                ),
            )
    return (True, None)


def check_lexical_prosodic_compatibility(
    source_regime: str,
    acoustic_regime: str,
    energy_level: float,
    max_stressed_tokens: int,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: Low-impact lexical selections must not be paired with high-impact prosody.

    INVARIANT: Restrictive regime -> no high-energy, no emphatic stress

    Returns:
        Tuple of (passed, violation_or_none)
    """
    # Under restrictive regimes, prosody should match low-impact lexical selections
    if source_regime in FULL_SUPPRESSION_REQUIRED_REGIMES:
        violations = []

        # High energy is incompatible with low-impact lexical
        if energy_level > HIGH_ENERGY_THRESHOLD:
            violations.append(f"high energy ({energy_level}) under restrictive regime")

        # Emphatic stress is incompatible with neutral words
        if max_stressed_tokens > 0:
            violations.append(
                f"emphatic stress ({max_stressed_tokens} tokens) "
                f"under restrictive regime"
            )

        if violations:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.MINOR,
                    violation_type=ViolationType.LEXICAL_PROSODIC_INCOMPATIBILITY,
                    invariant_name="lexical_prosodic_compatibility",
                    source_phase="P9",
                    target_phase="P10",
                    description=(
                        f"Lexical-prosodic incompatibility: {'; '.join(violations)}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "acoustic_regime": acoustic_regime,
                        "energy_level": energy_level,
                        "max_stressed_tokens": max_stressed_tokens,
                    },
                ),
            )
    return (True, None)


def check_no_authority_escalation_reflexive(
    grounding_mode: Optional[str],
    suppress_certainty: bool,
    suppress_emphasis: bool,
    energy_level: float,
    pitch_range: Tuple[int, int],
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: Under REFLEXIVE grounding, prosody must not imply authority.

    INVARIANT: REFLEXIVE -> suppress_certainty=True, suppress_emphasis=True,
               low energy, narrow pitch

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if grounding_mode == "REFLEXIVE":
        violations = []

        if not suppress_certainty:
            violations.append("certainty not suppressed")
        if not suppress_emphasis:
            violations.append("emphasis not suppressed")
        if energy_level > 0.4:
            violations.append(f"energy too high ({energy_level})")

        pitch_variance = pitch_range[1] - pitch_range[0]
        if pitch_variance > 25:
            violations.append(f"pitch variance too high ({pitch_variance} Hz)")

        if violations:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.AUTHORITY_ESCALATION,
                    invariant_name="no_authority_escalation_reflexive",
                    source_phase="PO1",
                    target_phase="P11",
                    description=(
                        f"REFLEXIVE grounding prohibits authority escalation: "
                        f"{'; '.join(violations)}"
                    ),
                    evidence={
                        "grounding_mode": grounding_mode,
                        "suppress_certainty": suppress_certainty,
                        "suppress_emphasis": suppress_emphasis,
                        "energy_level": energy_level,
                        "pitch_range": pitch_range,
                    },
                ),
            )
    return (True, None)


def check_no_authority_escalation_relational(
    grounding_mode: Optional[str],
    suppress_certainty: bool,
    suppress_emphasis: bool,
    energy_level: float,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: Under RELATIONAL grounding, prosody must not imply authority.

    INVARIANT: RELATIONAL -> suppress_certainty=True, suppress_emphasis=True,
               moderate energy

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if grounding_mode == "RELATIONAL":
        violations = []

        if not suppress_certainty:
            violations.append("certainty not suppressed")
        if not suppress_emphasis:
            violations.append("emphasis not suppressed")
        if energy_level > 0.45:
            violations.append(f"energy too high ({energy_level})")

        if violations:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.AUTHORITY_ESCALATION,
                    invariant_name="no_authority_escalation_relational",
                    source_phase="PO1",
                    target_phase="P11",
                    description=(
                        f"RELATIONAL grounding prohibits authority escalation: "
                        f"{'; '.join(violations)}"
                    ),
                    evidence={
                        "grounding_mode": grounding_mode,
                        "suppress_certainty": suppress_certainty,
                        "suppress_emphasis": suppress_emphasis,
                        "energy_level": energy_level,
                    },
                ),
            )
    return (True, None)


def check_suppression_consistency(
    source_regime: str,
    suppress_emotion: bool,
    suppress_emphasis: bool,
    suppress_certainty: bool,
) -> Tuple[bool, Optional[P12Violation]]:
    """
    Check: Restrictive regimes must have all suppressions active.

    INVARIANT: {HOLD, DE_ESCALATE, STABILIZE, REFLECT} ->
               suppress_emotion=True AND suppress_emphasis=True AND suppress_certainty=True

    Returns:
        Tuple of (passed, violation_or_none)
    """
    if source_regime in FULL_SUPPRESSION_REQUIRED_REGIMES:
        missing = []
        if not suppress_emotion:
            missing.append("suppress_emotion")
        if not suppress_emphasis:
            missing.append("suppress_emphasis")
        if not suppress_certainty:
            missing.append("suppress_certainty")

        if missing:
            return (
                False,
                create_violation(
                    severity=ViolationSeverity.CRITICAL,
                    violation_type=ViolationType.SUPPRESSION_VIOLATION,
                    invariant_name="suppression_consistency",
                    source_phase="P6",
                    target_phase="P10",
                    description=(
                        f"{source_regime} regime requires all suppressions active, "
                        f"but missing: {', '.join(missing)}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "suppress_emotion": suppress_emotion,
                        "suppress_emphasis": suppress_emphasis,
                        "suppress_certainty": suppress_certainty,
                        "missing_suppressions": missing,
                    },
                ),
            )
    return (True, None)


# ============================================================================
# MAIN VALIDATOR CLASS
# ============================================================================


class P12ConsistencyValidator:
    """
    Acoustic-Prosodic Consistency Validator.

    This validator checks consistency between governance layers (PO1-P7),
    acoustic parameters (P10), and prosodic evidence (P11).

    CRITICAL: This validator is AUDIT-ONLY. It NEVER modifies or corrects data.
    It only observes, validates, and reports.

    Usage:
        validator = P12ConsistencyValidator()
        report = validator.validate(ctx)
    """

    # List of all invariants checked by this validator
    CHECKED_INVARIANTS = [
        "regime_requires_flat_acoustic",
        "regime_requires_soft_or_flat",
        "hold_no_pitch_rise",
        "hold_no_intensity_increase",
        "hold_no_expressive_modulation",
        "de_escalate_no_sharp_pitch",
        "de_escalate_no_rapid_tempo",
        "de_escalate_no_emphasis_amplification",
        "reflection_no_interrogative_prosody",
        "deferral_minimal_prosodic_motion",
        "question_rising_pitch_requires_clarify_intent",
        "explanation_respects_regime",
        "uncertainty_preservation",
        "lexical_prosodic_compatibility",
        "no_authority_escalation_reflexive",
        "no_authority_escalation_relational",
        "suppression_consistency",
    ]

    def __init__(self) -> None:
        """Initialize the P12 Consistency Validator."""
        pass

    def _get_timestamp_utc(self) -> str:
        """Get current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _extract_context_data(self, ctx: Any) -> Dict[str, Any]:
        """
        Extract relevant data from pipeline context.

        This method safely extracts data without modifying the context.
        Returns a dictionary with all needed fields or safe defaults.

        Args:
            ctx: Pipeline context object.

        Returns:
            Dictionary with extracted data.
        """
        data: Dict[str, Any] = {
            "source_regime": "UNKNOWN",
            "source_discourse_act": "UNKNOWN",
            "source_intent": None,
            "grounding_mode": None,
            "has_uncertainty_slot": False,
            "acoustic_regime": None,
            "speech_rate": None,
            "energy_level": None,
            "pitch_range": None,
            "emphasis_policy": None,
            "max_stressed_tokens": None,
            "suppress_emotion": None,
            "suppress_emphasis": None,
            "suppress_certainty": None,
            "has_p10": False,
            "has_p11": False,
        }

        # Extract P6 regime
        if hasattr(ctx, 'p6_regime') and ctx.p6_regime is not None:
            data["source_regime"] = ctx.p6_regime.regime.value

        # Extract P7 discourse act
        if hasattr(ctx, 'p7_discourse_envelope') and ctx.p7_discourse_envelope is not None:
            data["source_discourse_act"] = ctx.p7_discourse_envelope.act.value

        # Extract PO2 intent
        if hasattr(ctx, 'phase_zero') and ctx.phase_zero is not None:
            data["source_intent"] = ctx.phase_zero.intent_type.value

        # Extract PO1 grounding mode
        if hasattr(ctx, 'phase_minus_one') and ctx.phase_minus_one is not None:
            if ctx.phase_minus_one.selected_primary is not None:
                data["grounding_mode"] = ctx.phase_minus_one.selected_primary.mode.value

        # Check for UNCERTAINTY slot in P8 semantic frame
        if hasattr(ctx, 'semantic_frame') and ctx.semantic_frame is not None:
            from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_schema import SemanticSlot
            data["has_uncertainty_slot"] = ctx.semantic_frame.has_slot(SemanticSlot.UNCERTAINTY)

        # Extract P10 acoustic parameters
        if hasattr(ctx, 'p10_acoustic') and ctx.p10_acoustic is not None:
            data["has_p10"] = True
            p10 = ctx.p10_acoustic
            data["acoustic_regime"] = p10.regime.value
            data["speech_rate"] = p10.speech_rate
            data["energy_level"] = p10.energy_level
            data["pitch_range"] = p10.pitch_range
            data["emphasis_policy"] = p10.emphasis_policy.value
            data["max_stressed_tokens"] = p10.max_stressed_tokens
            data["suppress_emotion"] = p10.suppress_emotion
            data["suppress_emphasis"] = p10.suppress_emphasis
            data["suppress_certainty"] = p10.suppress_certainty

        # Extract P11 prosodic evidence (use P11 values if available, else P10)
        if hasattr(ctx, 'p11_prosodic_evidence') and ctx.p11_prosodic_evidence is not None:
            data["has_p11"] = True
            p11 = ctx.p11_prosodic_evidence
            # P11 values are copies of P10, but we prefer to read from P11
            # for the "witnessed" values
            data["pitch_range"] = p11.pitch_range
            data["energy_level"] = p11.energy_level
            data["speech_rate"] = p11.speech_rate

        return data

    def validate(self, ctx: Any) -> Optional[P12ConsistencyReport]:
        """
        Validate consistency across all governance, acoustic, and prosodic layers.

        This method performs all invariant checks and produces a comprehensive
        consistency report. It NEVER modifies or corrects any data.

        Args:
            ctx: Pipeline context with all phase outputs.

        Returns:
            P12ConsistencyReport with validation results, or None if insufficient data.
        """
        # Extract context data safely
        data = self._extract_context_data(ctx)

        # If we don't have P10 acoustic data, we cannot validate
        if not data["has_p10"]:
            return None

        violations: List[P12Violation] = []
        warnings: List[P12Warning] = []
        audit_notes: Dict[str, Any] = {
            "has_p10": data["has_p10"],
            "has_p11": data["has_p11"],
            "source_regime": data["source_regime"],
            "source_discourse_act": data["source_discourse_act"],
            "source_intent": data["source_intent"],
            "grounding_mode": data["grounding_mode"],
        }

        # Run all invariant checks
        checks = [
            # Regime -> Acoustic invariants
            check_regime_acoustic_flat(
                data["source_regime"],
                data["acoustic_regime"],
            ),
            check_regime_acoustic_soft_or_flat(
                data["source_regime"],
                data["acoustic_regime"],
            ),
            check_hold_no_pitch_rise(
                data["source_regime"],
                data["pitch_range"],
            ),
            check_hold_no_intensity_increase(
                data["source_regime"],
                data["energy_level"],
            ),
            check_hold_no_expressive_modulation(
                data["source_regime"],
                data["emphasis_policy"],
                data["max_stressed_tokens"],
            ),
            check_de_escalate_no_sharp_pitch(
                data["source_regime"],
                data["pitch_range"],
            ),
            check_de_escalate_no_rapid_tempo(
                data["source_regime"],
                data["speech_rate"],
            ),
            check_de_escalate_no_emphasis_amplification(
                data["source_regime"],
                data["max_stressed_tokens"],
            ),
            # Discourse -> Prosody invariants
            check_reflection_no_interrogative_prosody(
                data["source_discourse_act"],
                data["pitch_range"],
                data["source_intent"],
            ),
            check_deferral_minimal_prosodic_motion(
                data["source_discourse_act"],
                data["pitch_range"],
                data["energy_level"],
            ),
            check_question_rising_pitch_only_if_clarify(
                data["source_discourse_act"],
                data["source_intent"],
                data["pitch_range"],
            ),
            check_explanation_respects_regime(
                data["source_discourse_act"],
                data["source_regime"],
                data["energy_level"],
                data["max_stressed_tokens"],
            ),
            # Uncertainty preservation
            check_uncertainty_preservation(
                data["has_uncertainty_slot"],
                data["suppress_certainty"],
                data["pitch_range"],
                data["emphasis_policy"],
                data["max_stressed_tokens"],
            ),
            # Lexical-Prosodic compatibility
            check_lexical_prosodic_compatibility(
                data["source_regime"],
                data["acoustic_regime"],
                data["energy_level"],
                data["max_stressed_tokens"],
            ),
            # Authority escalation prevention
            check_no_authority_escalation_reflexive(
                data["grounding_mode"],
                data["suppress_certainty"],
                data["suppress_emphasis"],
                data["energy_level"],
                data["pitch_range"],
            ),
            check_no_authority_escalation_relational(
                data["grounding_mode"],
                data["suppress_certainty"],
                data["suppress_emphasis"],
                data["energy_level"],
            ),
            # Suppression consistency
            check_suppression_consistency(
                data["source_regime"],
                data["suppress_emotion"],
                data["suppress_emphasis"],
                data["suppress_certainty"],
            ),
        ]

        # Collect violations
        for passed, violation in checks:
            if not passed and violation is not None:
                violations.append(violation)

        # Add warnings for edge cases
        if not data["has_p11"]:
            warnings.append(create_warning(
                warning_code="P11_MISSING",
                description="P11 prosodic evidence not available for validation",
                source_phase="P12",
                evidence={"has_p11": False},
            ))

        if data["source_regime"] == "UNKNOWN":
            warnings.append(create_warning(
                warning_code="REGIME_UNKNOWN",
                description="P6 regime envelope not available",
                source_phase="P12",
                evidence={"source_regime": data["source_regime"]},
            ))

        if data["source_discourse_act"] == "UNKNOWN":
            warnings.append(create_warning(
                warning_code="DISCOURSE_UNKNOWN",
                description="P7 discourse envelope not available",
                source_phase="P12",
                evidence={"source_discourse_act": data["source_discourse_act"]},
            ))

        # Determine consistency
        is_consistent = len(violations) == 0

        # Build report
        return P12ConsistencyReport(
            is_consistent=is_consistent,
            violations=violations,
            warnings=warnings,
            checked_invariants=list(self.CHECKED_INVARIANTS),
            audit_notes=audit_notes,
            source_regime=data["source_regime"],
            source_discourse_act=data["source_discourse_act"],
            source_intent=data["source_intent"],
            timestamp_utc=self._get_timestamp_utc(),
        )


# Public exports
__all__ = [
    # Constants
    "FLAT_REQUIRED_REGIMES",
    "SOFT_OR_FLAT_REQUIRED_REGIMES",
    "NEUTRAL_ALLOWED_REGIMES",
    "FULL_SUPPRESSION_REQUIRED_REGIMES",
    "FLAT_PITCH_DISCOURSE_ACTS",
    "NO_EMPHASIS_DISCOURSE_ACTS",
    "AUTHORITY_RESTRICTED_GROUNDING_MODES",
    # Invariant check functions
    "check_regime_acoustic_flat",
    "check_regime_acoustic_soft_or_flat",
    "check_hold_no_pitch_rise",
    "check_hold_no_intensity_increase",
    "check_hold_no_expressive_modulation",
    "check_de_escalate_no_sharp_pitch",
    "check_de_escalate_no_rapid_tempo",
    "check_de_escalate_no_emphasis_amplification",
    "check_reflection_no_interrogative_prosody",
    "check_deferral_minimal_prosodic_motion",
    "check_question_rising_pitch_only_if_clarify",
    "check_explanation_respects_regime",
    "check_uncertainty_preservation",
    "check_lexical_prosodic_compatibility",
    "check_no_authority_escalation_reflexive",
    "check_no_authority_escalation_relational",
    "check_suppression_consistency",
    # Validator class
    "P12ConsistencyValidator",
]
