"""
Renderer Compliance Checker

This module implements the RendererComplianceChecker that validates
AcousticRenderIntent objects against AcousticSafetyEnvelope (P13).

The compliance checker:
- Takes: AcousticSafetyEnvelope + AcousticRenderIntent
- Produces: ComplianceResult (PASS/FAIL with violation list)

CRITICAL ARCHITECTURAL INVARIANT:
    Any renderer violating P13 constraints is detected and blocked.
    Violations map directly to P13 SafetyViolation types.

The checker is:
- Deterministic: Same input -> same output
- Strict: Any violation results in FAIL
- Comprehensive: Checks ALL P13 constraints
- Binding: Violations cannot be overridden
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from symbolu.mechanical.pipeline.renderer_compliance.renderer_contract import (
    AcousticRenderIntent,
    ComplianceResult,
    ComplianceVerdict,
    ComplianceViolation,
    ViolationCategory,
)


# ============================================================================
# VERSION CONSTANT
# ============================================================================


COMPLIANCE_CHECKER_VERSION = "1.0.0"


# ============================================================================
# COMPLIANCE CHECKER
# ============================================================================


class RendererComplianceChecker:
    """
    Validates renderer intents against P13 safety envelopes.

    This checker ensures no renderer can violate P13 without being
    detected and blocked. All checks are deterministic and binding.

    Usage:
        checker = RendererComplianceChecker()
        result = checker.check(envelope, intent)
        if result.failed():
            # Block the renderer
            pass
    """

    def __init__(self) -> None:
        """Initialize the compliance checker."""
        self._version = COMPLIANCE_CHECKER_VERSION

    @property
    def version(self) -> str:
        """Get checker version."""
        return self._version

    def check(
        self,
        envelope: Any,  # AcousticSafetyEnvelope
        intent: AcousticRenderIntent,
    ) -> ComplianceResult:
        """
        Check render intent against P13 safety envelope.

        Args:
            envelope: The AcousticSafetyEnvelope (P13)
            intent: The AcousticRenderIntent from a renderer

        Returns:
            ComplianceResult with PASS/FAIL verdict and violations
        """
        violations: List[ComplianceViolation] = []
        checked_constraints: List[str] = []

        # Get envelope properties
        risk_level = self._get_risk_level(envelope)
        is_blocked = self._is_blocked(envelope)

        # === ABSOLUTE BLOCKING CHECKS ===

        # Check 1: BLOCKED envelope
        checked_constraints.append("BLOCKED_ENVELOPE_CHECK")
        if is_blocked:
            # Under BLOCKED, no render intent is allowed except fully silent
            violation = self._check_blocked_envelope(envelope, intent)
            if violation:
                violations.append(violation)

        # Check 2: HOLD regime (implies BLOCKED)
        checked_constraints.append("HOLD_REGIME_CHECK")
        hold_violation = self._check_hold_regime(envelope, intent)
        if hold_violation:
            violations.append(hold_violation)

        # === PITCH BOUND CHECKS ===

        # Check 3: Pitch minimum bound
        checked_constraints.append("PITCH_MIN_BOUND")
        pitch_min_violation = self._check_pitch_min(envelope, intent)
        if pitch_min_violation:
            violations.append(pitch_min_violation)

        # Check 4: Pitch maximum bound
        checked_constraints.append("PITCH_MAX_BOUND")
        pitch_max_violation = self._check_pitch_max(envelope, intent)
        if pitch_max_violation:
            violations.append(pitch_max_violation)

        # Check 5: Pitch variance bound
        checked_constraints.append("PITCH_VARIANCE_BOUND")
        variance_violation = self._check_pitch_variance(envelope, intent)
        if variance_violation:
            violations.append(variance_violation)

        # === ENERGY BOUND CHECKS ===

        # Check 6: Energy minimum bound
        checked_constraints.append("ENERGY_MIN_BOUND")
        energy_min_violation = self._check_energy_min(envelope, intent)
        if energy_min_violation:
            violations.append(energy_min_violation)

        # Check 7: Energy maximum bound
        checked_constraints.append("ENERGY_MAX_BOUND")
        energy_max_violation = self._check_energy_max(envelope, intent)
        if energy_max_violation:
            violations.append(energy_max_violation)

        # === EXPRESSION FLAG CHECKS ===

        # Check 8: Emphasis flag
        checked_constraints.append("EMPHASIS_FLAG_CHECK")
        emphasis_violation = self._check_emphasis_flag(envelope, intent)
        if emphasis_violation:
            violations.append(emphasis_violation)

        # Check 9: Pitch contours flag
        checked_constraints.append("PITCH_CONTOURS_FLAG_CHECK")
        contour_violation = self._check_pitch_contours_flag(envelope, intent)
        if contour_violation:
            violations.append(contour_violation)

        # Check 10: Rhythm variation flag
        checked_constraints.append("RHYTHM_VARIATION_FLAG_CHECK")
        rhythm_violation = self._check_rhythm_variation_flag(envelope, intent)
        if rhythm_violation:
            violations.append(rhythm_violation)

        # Check 11: Intonation shift flag
        checked_constraints.append("INTONATION_SHIFT_FLAG_CHECK")
        intonation_violation = self._check_intonation_shift_flag(envelope, intent)
        if intonation_violation:
            violations.append(intonation_violation)

        # === AMPLIFICATION CHECKS ===

        # Check 12: Emotion amplification
        checked_constraints.append("EMOTION_AMPLIFICATION_CHECK")
        emotion_violation = self._check_emotion_amplification(envelope, intent)
        if emotion_violation:
            violations.append(emotion_violation)

        # Check 13: Certainty escalation
        checked_constraints.append("CERTAINTY_ESCALATION_CHECK")
        certainty_violation = self._check_certainty_escalation(envelope, intent)
        if certainty_violation:
            violations.append(certainty_violation)

        # Check 14: Authority signaling
        checked_constraints.append("AUTHORITY_SIGNALING_CHECK")
        authority_violation = self._check_authority_signaling(envelope, intent)
        if authority_violation:
            violations.append(authority_violation)

        # Check 15: Excessive variance
        checked_constraints.append("EXCESSIVE_VARIANCE_CHECK")
        excessive_variance_violation = self._check_excessive_variance(envelope, intent)
        if excessive_variance_violation:
            violations.append(excessive_variance_violation)

        # Check 16: Prosodic manipulation
        checked_constraints.append("PROSODIC_MANIPULATION_CHECK")
        prosodic_violation = self._check_prosodic_manipulation(envelope, intent)
        if prosodic_violation:
            violations.append(prosodic_violation)

        # Check 17: Stressed tokens count
        checked_constraints.append("STRESSED_TOKENS_CHECK")
        stress_violation = self._check_stressed_tokens(envelope, intent)
        if stress_violation:
            violations.append(stress_violation)

        # === BUILD RESULT ===

        verdict = ComplianceVerdict.FAIL if violations else ComplianceVerdict.PASS

        return ComplianceResult(
            verdict=verdict,
            violations=tuple(violations),
            checked_constraints=tuple(checked_constraints),
            renderer_id=intent.renderer_id,
            envelope_risk_level=risk_level,
            debug={
                "checker_version": self._version,
                "envelope_blocked": is_blocked,
                "envelope_regime": self._get_source_regime(envelope),
                "intent_category": intent.intent_category.value,
            },
        )

    # ========================================================================
    # HELPER METHODS - Envelope property access
    # ========================================================================

    def _get_risk_level(self, envelope: Any) -> str:
        """Get risk level from envelope."""
        if hasattr(envelope, 'risk_level'):
            return envelope.risk_level.value if hasattr(envelope.risk_level, 'value') else str(envelope.risk_level)
        return "UNKNOWN"

    def _is_blocked(self, envelope: Any) -> bool:
        """Check if envelope is BLOCKED."""
        if hasattr(envelope, 'is_blocked'):
            return envelope.is_blocked()
        if hasattr(envelope, 'risk_level'):
            return str(envelope.risk_level).upper() == "BLOCKED"
        return False

    def _get_source_regime(self, envelope: Any) -> str:
        """Get source regime from envelope."""
        return getattr(envelope, 'source_regime', 'UNKNOWN')

    def _get_allowed_pitch_range(self, envelope: Any) -> Tuple[int, int]:
        """Get allowed pitch range from envelope."""
        return getattr(envelope, 'allowed_pitch_range', (90, 140))

    def _get_allowed_energy_range(self, envelope: Any) -> Tuple[float, float]:
        """Get allowed energy range from envelope."""
        return getattr(envelope, 'allowed_energy_range', (0.2, 0.6))

    def _get_allowed_variance_range(self, envelope: Any) -> Tuple[int, int]:
        """Get allowed variance range from envelope."""
        return getattr(envelope, 'allowed_variance_range', (0, 30))

    def _get_allow_emphasis(self, envelope: Any) -> bool:
        """Get allow_emphasis flag from envelope."""
        return getattr(envelope, 'allow_emphasis', False)

    def _get_allow_pitch_contours(self, envelope: Any) -> bool:
        """Get allow_pitch_contours flag from envelope."""
        return getattr(envelope, 'allow_pitch_contours', False)

    def _get_allow_rhythm_variation(self, envelope: Any) -> bool:
        """Get allow_rhythm_variation flag from envelope."""
        return getattr(envelope, 'allow_rhythm_variation', False)

    def _get_allow_intonation_shift(self, envelope: Any) -> bool:
        """Get allow_intonation_shift flag from envelope."""
        return getattr(envelope, 'allow_intonation_shift', False)

    def _is_fully_restricted(self, envelope: Any) -> bool:
        """Check if envelope is fully restricted."""
        if hasattr(envelope, 'is_fully_restricted'):
            return envelope.is_fully_restricted()
        return not (
            self._get_allow_emphasis(envelope) or
            self._get_allow_pitch_contours(envelope) or
            self._get_allow_rhythm_variation(envelope) or
            self._get_allow_intonation_shift(envelope)
        )

    # ========================================================================
    # VIOLATION CHECK METHODS
    # ========================================================================

    def _check_blocked_envelope(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check if render intent violates BLOCKED envelope."""
        if not self._is_blocked(envelope):
            return None

        # Under BLOCKED, ANY expression is a violation
        if intent.uses_any_expression():
            return ComplianceViolation(
                category=ViolationCategory.BLOCKED_OVERRIDE,
                description=(
                    "Renderer attempted expression under BLOCKED envelope. "
                    "BLOCKED requires zero acoustic expression."
                ),
                evidence={
                    "envelope_blocked": True,
                    "will_use_emphasis": intent.will_use_emphasis,
                    "will_use_pitch_contours": intent.will_use_pitch_contours,
                    "will_use_rhythm_variation": intent.will_use_rhythm_variation,
                    "will_use_intonation_shift": intent.will_use_intonation_shift,
                },
            )
        return None

    def _check_hold_regime(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check if render intent violates HOLD regime."""
        source_regime = self._get_source_regime(envelope)
        if source_regime != "HOLD":
            return None

        # Under HOLD, ANY expression is a violation
        if intent.uses_any_expression():
            return ComplianceViolation(
                category=ViolationCategory.HOLD_OVERRIDE,
                description=(
                    "Renderer attempted expression under HOLD regime. "
                    "HOLD requires fully flat, expressionless output."
                ),
                evidence={
                    "source_regime": source_regime,
                    "will_use_emphasis": intent.will_use_emphasis,
                    "will_use_pitch_contours": intent.will_use_pitch_contours,
                },
            )
        return None

    def _check_pitch_min(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check pitch minimum bound."""
        allowed_range = self._get_allowed_pitch_range(envelope)
        allowed_min = allowed_range[0]

        if intent.intended_pitch_min < allowed_min:
            return ComplianceViolation(
                category=ViolationCategory.PITCH_BOUND_VIOLATION,
                description=(
                    f"Renderer pitch minimum ({intent.intended_pitch_min} Hz) "
                    f"is below allowed minimum ({allowed_min} Hz)"
                ),
                evidence={
                    "allowed_pitch_min": allowed_min,
                    "intended_pitch_min": intent.intended_pitch_min,
                    "violation_amount": allowed_min - intent.intended_pitch_min,
                },
            )
        return None

    def _check_pitch_max(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check pitch maximum bound."""
        allowed_range = self._get_allowed_pitch_range(envelope)
        allowed_max = allowed_range[1]

        if intent.intended_pitch_max > allowed_max:
            return ComplianceViolation(
                category=ViolationCategory.PITCH_BOUND_VIOLATION,
                description=(
                    f"Renderer pitch maximum ({intent.intended_pitch_max} Hz) "
                    f"exceeds allowed maximum ({allowed_max} Hz)"
                ),
                evidence={
                    "allowed_pitch_max": allowed_max,
                    "intended_pitch_max": intent.intended_pitch_max,
                    "violation_amount": intent.intended_pitch_max - allowed_max,
                },
            )
        return None

    def _check_pitch_variance(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check pitch variance bound."""
        allowed_range = self._get_allowed_variance_range(envelope)
        allowed_max_variance = allowed_range[1]

        if intent.intended_pitch_variance > allowed_max_variance:
            return ComplianceViolation(
                category=ViolationCategory.VARIANCE_BOUND_VIOLATION,
                description=(
                    f"Renderer pitch variance ({intent.intended_pitch_variance} Hz) "
                    f"exceeds allowed maximum ({allowed_max_variance} Hz)"
                ),
                evidence={
                    "allowed_max_variance": allowed_max_variance,
                    "intended_variance": intent.intended_pitch_variance,
                    "violation_amount": intent.intended_pitch_variance - allowed_max_variance,
                },
            )
        return None

    def _check_energy_min(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check energy minimum bound."""
        allowed_range = self._get_allowed_energy_range(envelope)
        allowed_min = allowed_range[0]

        if intent.intended_energy_min < allowed_min:
            return ComplianceViolation(
                category=ViolationCategory.ENERGY_BOUND_VIOLATION,
                description=(
                    f"Renderer energy minimum ({intent.intended_energy_min}) "
                    f"is below allowed minimum ({allowed_min})"
                ),
                evidence={
                    "allowed_energy_min": allowed_min,
                    "intended_energy_min": intent.intended_energy_min,
                    "violation_amount": allowed_min - intent.intended_energy_min,
                },
            )
        return None

    def _check_energy_max(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check energy maximum bound."""
        allowed_range = self._get_allowed_energy_range(envelope)
        allowed_max = allowed_range[1]

        if intent.intended_energy_max > allowed_max:
            return ComplianceViolation(
                category=ViolationCategory.ENERGY_BOUND_VIOLATION,
                description=(
                    f"Renderer energy maximum ({intent.intended_energy_max}) "
                    f"exceeds allowed maximum ({allowed_max})"
                ),
                evidence={
                    "allowed_energy_max": allowed_max,
                    "intended_energy_max": intent.intended_energy_max,
                    "violation_amount": intent.intended_energy_max - allowed_max,
                },
            )
        return None

    def _check_emphasis_flag(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check emphasis flag compliance."""
        allow_emphasis = self._get_allow_emphasis(envelope)

        if intent.will_use_emphasis and not allow_emphasis:
            return ComplianceViolation(
                category=ViolationCategory.EMPHASIS_VIOLATION,
                description=(
                    "Renderer will use emphasis but envelope prohibits emphasis "
                    "(allow_emphasis=False)"
                ),
                evidence={
                    "allow_emphasis": allow_emphasis,
                    "will_use_emphasis": intent.will_use_emphasis,
                },
            )
        return None

    def _check_pitch_contours_flag(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check pitch contours flag compliance."""
        allow_contours = self._get_allow_pitch_contours(envelope)

        if intent.will_use_pitch_contours and not allow_contours:
            return ComplianceViolation(
                category=ViolationCategory.CONTOUR_VIOLATION,
                description=(
                    "Renderer will use pitch contours but envelope prohibits contours "
                    "(allow_pitch_contours=False)"
                ),
                evidence={
                    "allow_pitch_contours": allow_contours,
                    "will_use_pitch_contours": intent.will_use_pitch_contours,
                },
            )
        return None

    def _check_rhythm_variation_flag(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check rhythm variation flag compliance."""
        allow_rhythm = self._get_allow_rhythm_variation(envelope)

        if intent.will_use_rhythm_variation and not allow_rhythm:
            return ComplianceViolation(
                category=ViolationCategory.RHYTHM_VIOLATION,
                description=(
                    "Renderer will use rhythm variation but envelope prohibits rhythm variation "
                    "(allow_rhythm_variation=False)"
                ),
                evidence={
                    "allow_rhythm_variation": allow_rhythm,
                    "will_use_rhythm_variation": intent.will_use_rhythm_variation,
                },
            )
        return None

    def _check_intonation_shift_flag(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check intonation shift flag compliance."""
        allow_intonation = self._get_allow_intonation_shift(envelope)

        if intent.will_use_intonation_shift and not allow_intonation:
            return ComplianceViolation(
                category=ViolationCategory.INTONATION_VIOLATION,
                description=(
                    "Renderer will use intonation shift but envelope prohibits intonation shift "
                    "(allow_intonation_shift=False)"
                ),
                evidence={
                    "allow_intonation_shift": allow_intonation,
                    "will_use_intonation_shift": intent.will_use_intonation_shift,
                },
            )
        return None

    def _check_emotion_amplification(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check for emotion amplification violation."""
        # Emotion amplification detected if:
        # - Using expression features that are NOT allowed by the envelope
        # - Using multiple DISALLOWED expression features together
        # Note: Using features that ARE allowed is not emotion amplification

        source_regime = self._get_source_regime(envelope)
        restricted_regimes = {"HOLD", "DE_ESCALATE", "STABILIZE", "REFLECT"}

        if source_regime in restricted_regimes:
            # Count DISALLOWED expression features being used
            # Only flag features that are both used AND not allowed
            disallowed_expressions = []

            if intent.will_use_emphasis and not self._get_allow_emphasis(envelope):
                disallowed_expressions.append("emphasis")
            if intent.will_use_pitch_contours and not self._get_allow_pitch_contours(envelope):
                disallowed_expressions.append("contours")
            if intent.will_use_rhythm_variation and not self._get_allow_rhythm_variation(envelope):
                disallowed_expressions.append("rhythm")
            if intent.will_use_intonation_shift and not self._get_allow_intonation_shift(envelope):
                disallowed_expressions.append("intonation")

            # Multiple disallowed expressions = emotion amplification
            if len(disallowed_expressions) >= 2:
                return ComplianceViolation(
                    category=ViolationCategory.EMOTION_AMPLIFICATION,
                    description=(
                        f"Renderer is amplifying emotion under {source_regime} regime "
                        f"with {len(disallowed_expressions)} disallowed expression features: "
                        f"{', '.join(disallowed_expressions)}"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "disallowed_expression_count": len(disallowed_expressions),
                        "disallowed_expressions": disallowed_expressions,
                        "expressions_used": {
                            "emphasis": intent.will_use_emphasis,
                            "contours": intent.will_use_pitch_contours,
                            "rhythm": intent.will_use_rhythm_variation,
                            "intonation": intent.will_use_intonation_shift,
                        },
                        "expressions_allowed": {
                            "emphasis": self._get_allow_emphasis(envelope),
                            "contours": self._get_allow_pitch_contours(envelope),
                            "rhythm": self._get_allow_rhythm_variation(envelope),
                            "intonation": self._get_allow_intonation_shift(envelope),
                        },
                    },
                )
        return None

    def _check_certainty_escalation(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check for certainty escalation violation."""
        # Certainty escalation detected if:
        # - Using emphatic stress under uncertainty-preserving regimes
        # - High stressed token count

        source_regime = self._get_source_regime(envelope)
        uncertainty_regimes = {"REFLECT", "STABILIZE", "DE_ESCALATE"}

        if source_regime in uncertainty_regimes:
            if intent.intended_stressed_tokens > 1 or (
                intent.will_use_emphasis and intent.intended_stressed_tokens > 0
            ):
                return ComplianceViolation(
                    category=ViolationCategory.CERTAINTY_ESCALATION,
                    description=(
                        f"Renderer is escalating certainty under {source_regime} regime "
                        f"with {intent.intended_stressed_tokens} stressed tokens"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "stressed_tokens": intent.intended_stressed_tokens,
                        "will_use_emphasis": intent.will_use_emphasis,
                    },
                )
        return None

    def _check_authority_signaling(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check for authority signaling violation."""
        # Authority signaling detected if:
        # - Using assertive prosody (high energy + emphasis + contours)
        # - Under regimes that prohibit authority

        source_regime = self._get_source_regime(envelope)
        no_authority_regimes = {"HOLD", "REFLECT", "DE_ESCALATE"}

        if source_regime in no_authority_regimes:
            energy_range = self._get_allowed_energy_range(envelope)
            max_allowed_energy = energy_range[1]

            # Authority signaling: high energy + emphasis + contours
            is_assertive = (
                intent.intended_energy_max >= max_allowed_energy * 0.9 and
                intent.will_use_emphasis and
                intent.will_use_pitch_contours
            )

            if is_assertive:
                return ComplianceViolation(
                    category=ViolationCategory.AUTHORITY_SIGNALING,
                    description=(
                        f"Renderer is signaling authority under {source_regime} regime "
                        "with assertive prosodic pattern (high energy + emphasis + contours)"
                    ),
                    evidence={
                        "source_regime": source_regime,
                        "intended_energy_max": intent.intended_energy_max,
                        "max_allowed_energy": max_allowed_energy,
                        "will_use_emphasis": intent.will_use_emphasis,
                        "will_use_pitch_contours": intent.will_use_pitch_contours,
                    },
                )
        return None

    def _check_excessive_variance(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check for excessive variance violation."""
        # This is a semantic check beyond just bound checking
        # Excessive variance when envelope is restrictive

        if self._is_fully_restricted(envelope):
            allowed_variance = self._get_allowed_variance_range(envelope)[1]
            # Under full restriction, even at-limit variance may be excessive
            if intent.intended_pitch_variance > allowed_variance * 0.5:
                return ComplianceViolation(
                    category=ViolationCategory.EXCESSIVE_VARIANCE,
                    description=(
                        f"Renderer has excessive variance ({intent.intended_pitch_variance} Hz) "
                        f"under fully restricted envelope (50% of {allowed_variance} Hz recommended)"
                    ),
                    evidence={
                        "intended_variance": intent.intended_pitch_variance,
                        "allowed_variance": allowed_variance,
                        "recommended_max": allowed_variance * 0.5,
                        "is_fully_restricted": True,
                    },
                )
        return None

    def _check_prosodic_manipulation(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check for prosodic manipulation violation."""
        # Prosodic manipulation detected if:
        # - Combining multiple prosodic features for effect
        # - High energy + high variance + stress together

        allowed_energy_max = self._get_allowed_energy_range(envelope)[1]
        allowed_variance_max = self._get_allowed_variance_range(envelope)[1]

        # Check for manipulative combination
        high_energy = intent.intended_energy_max >= allowed_energy_max * 0.85
        high_variance = intent.intended_pitch_variance >= allowed_variance_max * 0.85
        using_stress = intent.intended_stressed_tokens >= 2

        if high_energy and high_variance and using_stress:
            return ComplianceViolation(
                category=ViolationCategory.PROSODIC_MANIPULATION,
                description=(
                    "Renderer is using prosodic manipulation "
                    "(high energy + high variance + multiple stressed tokens)"
                ),
                evidence={
                    "intended_energy_max": intent.intended_energy_max,
                    "allowed_energy_max": allowed_energy_max,
                    "intended_variance": intent.intended_pitch_variance,
                    "allowed_variance": allowed_variance_max,
                    "stressed_tokens": intent.intended_stressed_tokens,
                },
            )
        return None

    def _check_stressed_tokens(
        self, envelope: Any, intent: AcousticRenderIntent
    ) -> Optional[ComplianceViolation]:
        """Check stressed tokens count."""
        allow_emphasis = self._get_allow_emphasis(envelope)

        # If emphasis not allowed, stressed tokens must be 0
        if not allow_emphasis and intent.intended_stressed_tokens > 0:
            return ComplianceViolation(
                category=ViolationCategory.EMPHASIS_VIOLATION,
                description=(
                    f"Renderer intends to stress {intent.intended_stressed_tokens} tokens "
                    "but emphasis is prohibited (allow_emphasis=False)"
                ),
                evidence={
                    "allow_emphasis": allow_emphasis,
                    "intended_stressed_tokens": intent.intended_stressed_tokens,
                },
            )

        # Even if emphasis allowed, limit to reasonable count
        # P10 max is 1, so >1 is always suspicious
        if intent.intended_stressed_tokens > 1 and allow_emphasis:
            return ComplianceViolation(
                category=ViolationCategory.EMPHASIS_VIOLATION,
                description=(
                    f"Renderer intends to stress {intent.intended_stressed_tokens} tokens "
                    "which exceeds reasonable emphasis limit (max 1)"
                ),
                evidence={
                    "allow_emphasis": allow_emphasis,
                    "intended_stressed_tokens": intent.intended_stressed_tokens,
                    "max_reasonable": 1,
                },
            )
        return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def check_compliance(
    envelope: Any,
    intent: AcousticRenderIntent,
) -> ComplianceResult:
    """
    Convenience function to check compliance.

    Args:
        envelope: The AcousticSafetyEnvelope (P13)
        intent: The AcousticRenderIntent from a renderer

    Returns:
        ComplianceResult with PASS/FAIL verdict and violations
    """
    checker = RendererComplianceChecker()
    return checker.check(envelope, intent)


def is_compliant(envelope: Any, intent: AcousticRenderIntent) -> bool:
    """
    Quick check if intent is compliant.

    Args:
        envelope: The AcousticSafetyEnvelope (P13)
        intent: The AcousticRenderIntent from a renderer

    Returns:
        True if compliant, False otherwise
    """
    result = check_compliance(envelope, intent)
    return result.passed()


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Version
    "COMPLIANCE_CHECKER_VERSION",
    # Classes
    "RendererComplianceChecker",
    # Functions
    "check_compliance",
    "is_compliant",
]
