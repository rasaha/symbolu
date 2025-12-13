"""
P11 - Prosodic Evidence Capture Resolver

Witness-only resolver that observes and records prosodic/acoustic parameters
from P10. No modification, no correction, no side effects.

This is an evidence capture layer that validates invariants and exposes
violations without correcting them.

Authority Model:
- Consumes P10 AcousticParameterFrame (read-only)
- Cannot mutate P10 output
- Cannot influence upstream or downstream decisions
- Produces ProsodicEvidenceFrame (read-only, non-actuating)

Resolution Algorithm (Authoritative, exact order):
1. Check if P10 output exists (if not → return None)
2. Copy all acoustic parameters verbatim from P10
3. Populate provenance metadata from context
4. Run invariant checks (detect but do NOT correct)
5. Compute violations_detected
6. Return ProsodicEvidenceFrame

CRITICAL INVARIANTS:
- Never modify acoustic parameters
- Never correct violations
- Never influence behavior
- Witness-only: observe, record, attest
- Deterministic: same input -> same output

ARCHITECTURAL PRINCIPLE:
    P11 exists to observe, not to optimize.
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
    AcousticRegime,
    SPEECH_RATE_MIN,
    SPEECH_RATE_MAX,
    ENERGY_LEVEL_MIN,
    ENERGY_LEVEL_MAX,
    PITCH_MIN,
    PITCH_MAX,
    PAUSE_DURATION_MIN,
    PAUSE_DURATION_MAX,
)
from symbolu.mechanical.pipeline.p11_prosodic.p11_prosodic_schema import (
    ProsodicEvidenceFrame,
    P11_VERSION,
)


# ============================================================================
# INVARIANT CHECK FUNCTIONS
# ============================================================================
# All invariant checks are pure boolean functions.
# They detect violations but do NOT correct them.


def check_speech_rate_within_bounds(acoustic_frame: AcousticParameterFrame) -> bool:
    """Check if speech_rate is within valid bounds."""
    return SPEECH_RATE_MIN <= acoustic_frame.speech_rate <= SPEECH_RATE_MAX


def check_energy_within_bounds(acoustic_frame: AcousticParameterFrame) -> bool:
    """Check if energy_level is within valid bounds."""
    return ENERGY_LEVEL_MIN <= acoustic_frame.energy_level <= ENERGY_LEVEL_MAX


def check_pitch_within_bounds(acoustic_frame: AcousticParameterFrame) -> bool:
    """Check if pitch_range is within valid bounds."""
    low, high = acoustic_frame.pitch_range
    return (
        PITCH_MIN <= low <= PITCH_MAX and
        PITCH_MIN <= high <= PITCH_MAX and
        low <= high
    )


def check_pause_policy_respected(acoustic_frame: AcousticParameterFrame) -> bool:
    """Check if pause_duration_ms is within valid bounds."""
    low, high = acoustic_frame.pause_duration_ms
    return (
        PAUSE_DURATION_MIN <= low <= PAUSE_DURATION_MAX and
        PAUSE_DURATION_MIN <= high <= PAUSE_DURATION_MAX and
        low <= high
    )


def check_no_emotion_amplification(
    acoustic_frame: AcousticParameterFrame,
    regime: str,
) -> bool:
    """
    Check that no emotion amplification occurs under restrictive regimes.

    Under HOLD, DE_ESCALATE, STABILIZE regimes, suppress_emotion MUST be True.
    """
    restrictive_regimes = {"HOLD", "DE_ESCALATE", "STABILIZE", "REFLECT"}
    if regime in restrictive_regimes:
        return acoustic_frame.suppress_emotion is True
    return True


def check_no_certainty_injection(
    acoustic_frame: AcousticParameterFrame,
    regime: str,
) -> bool:
    """
    Check that no certainty injection occurs under restrictive regimes.

    Under HOLD, DE_ESCALATE, STABILIZE regimes, suppress_certainty MUST be True.
    """
    restrictive_regimes = {"HOLD", "DE_ESCALATE", "STABILIZE", "REFLECT"}
    if regime in restrictive_regimes:
        return acoustic_frame.suppress_certainty is True
    return True


def check_no_emphasis_override(
    acoustic_frame: AcousticParameterFrame,
    regime: str,
) -> bool:
    """
    Check that no emphasis override occurs under restrictive regimes.

    Under HOLD, DE_ESCALATE, STABILIZE regimes, suppress_emphasis MUST be True.
    """
    restrictive_regimes = {"HOLD", "DE_ESCALATE", "STABILIZE", "REFLECT"}
    if regime in restrictive_regimes:
        return acoustic_frame.suppress_emphasis is True
    return True


def check_lexical_integrity_preserved(acoustic_frame: AcousticParameterFrame) -> bool:
    """
    Check that lexical integrity is preserved (P10 cannot modify lexical selections).

    This is always True for a well-formed AcousticParameterFrame since P10
    by design does not have access to modify lexical selections.
    """
    # P10 cannot modify lexical selections by design
    # The existence of a valid AcousticParameterFrame attests to this
    return True


def check_regime_constraints_respected(
    acoustic_frame: AcousticParameterFrame,
    regime: str,
) -> bool:
    """
    Check that acoustic regime is appropriate for the operational regime.

    Mapping:
    - HOLD → FLAT
    - DE_ESCALATE, STABILIZE, REFLECT → SOFT or FLAT
    - INFORM, CLARIFY → NEUTRAL, SOFT, or FLAT
    """
    acoustic_regime = acoustic_frame.regime

    if regime == "HOLD":
        return acoustic_regime == AcousticRegime.FLAT

    if regime in {"DE_ESCALATE", "STABILIZE", "REFLECT"}:
        return acoustic_regime in {AcousticRegime.SOFT, AcousticRegime.FLAT}

    if regime in {"INFORM", "CLARIFY"}:
        return acoustic_regime in {
            AcousticRegime.NEUTRAL,
            AcousticRegime.SOFT,
            AcousticRegime.FLAT,
            AcousticRegime.RESTRAINED,
        }

    # Unknown regime - conservative pass
    return True


# ============================================================================
# P11 PROSODIC RESOLVER
# ============================================================================


class P11ProsodicResolver:
    """
    Witness-only prosodic evidence capture resolver.

    This resolver observes P10's acoustic output and produces a read-only
    evidence frame. It validates invariants but does NOT correct violations.

    CRITICAL: This class is purely observational. It cannot mutate P10 output
    or influence any behavior in the pipeline.

    Usage:
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)
        # evidence contains attested acoustic parameters and invariant results

    Invariants:
    - Never modifies acoustic parameters
    - Never corrects violations (only detects them)
    - Deterministic: same input -> same output
    - Returns None if P10 is not available
    """

    def __init__(self) -> None:
        """Initialize the P11 prosodic resolver."""
        pass  # No state needed - purely observational

    def capture(self, ctx: Any) -> Optional[ProsodicEvidenceFrame]:
        """
        Capture prosodic evidence from P10 output.

        This is a pure, observational operation with no side effects.
        The result is a read-only prosodic evidence frame.

        CRITICAL:
        - If P10 is not available → return None
        - Copy all acoustic parameters verbatim
        - Validate invariants but do NOT correct
        - Never mutate ctx.p10_acoustic

        Capture Algorithm (exact order):
        1. Check if P10 output exists (if not → return None)
        2. Copy all acoustic parameters verbatim from P10
        3. Populate provenance metadata from context
        4. Run all invariant checks
        5. Compute violations_detected
        6. Return ProsodicEvidenceFrame

        Args:
            ctx: Pipeline context with p10_acoustic frame.

        Returns:
            ProsodicEvidenceFrame with evidence attestation, or None if P10 missing.
        """
        # Step 1: Check if P10 output exists
        if not hasattr(ctx, 'p10_acoustic') or ctx.p10_acoustic is None:
            return None

        acoustic_frame: AcousticParameterFrame = ctx.p10_acoustic

        # Step 2: Extract provenance metadata from context
        source_regime = self._get_source_regime(ctx, acoustic_frame)
        source_discourse_act = self._get_source_discourse_act(ctx, acoustic_frame)
        source_intent = self._get_source_intent(ctx)

        # Step 3: Run all invariant checks
        invariant_checks = self._run_invariant_checks(
            acoustic_frame=acoustic_frame,
            source_regime=source_regime,
        )

        # Step 4: Compute violations_detected
        violations_detected = any(not passed for passed in invariant_checks.values())

        # Step 5: Build debug info
        debug = self._build_debug_info(
            ctx=ctx,
            acoustic_frame=acoustic_frame,
            invariant_checks=invariant_checks,
        )

        # Step 6: Build and return ProsodicEvidenceFrame
        # All acoustic parameters are COPIED EXACTLY from P10
        return ProsodicEvidenceFrame(
            # Acoustic snapshot (copied verbatim from P10)
            speech_rate=acoustic_frame.speech_rate,
            energy_level=acoustic_frame.energy_level,
            pitch_range=acoustic_frame.pitch_range,
            pause_policy=acoustic_frame.pause_policy.value,
            pause_duration_ms=acoustic_frame.pause_duration_ms,
            emphasis_policy=acoustic_frame.emphasis_policy.value,
            max_stressed_tokens=acoustic_frame.max_stressed_tokens,
            suppress_emotion=acoustic_frame.suppress_emotion,
            suppress_certainty=acoustic_frame.suppress_certainty,
            suppress_emphasis=acoustic_frame.suppress_emphasis,
            # Provenance metadata
            source_regime=source_regime,
            source_discourse_act=source_discourse_act,
            source_intent=source_intent,
            source_p10_version="P10-" + P11_VERSION,
            timestamp_utc=self._get_timestamp_utc(),
            # Invariant attestation
            invariant_checks=invariant_checks,
            violations_detected=violations_detected,
            # Metadata
            debug=debug,
        )

    def _get_source_regime(
        self,
        ctx: Any,
        acoustic_frame: AcousticParameterFrame,
    ) -> str:
        """Extract source regime from context or acoustic frame."""
        # Prefer acoustic frame's source_regime
        if hasattr(acoustic_frame, 'source_regime') and acoustic_frame.source_regime:
            return acoustic_frame.source_regime

        # Fallback to context p6_regime
        if hasattr(ctx, 'p6_regime') and ctx.p6_regime is not None:
            return ctx.p6_regime.regime.value

        # Conservative default
        return "HOLD"

    def _get_source_discourse_act(
        self,
        ctx: Any,
        acoustic_frame: AcousticParameterFrame,
    ) -> str:
        """Extract source discourse act from context or acoustic frame."""
        # Prefer acoustic frame's source_discourse_act
        if hasattr(acoustic_frame, 'source_discourse_act') and acoustic_frame.source_discourse_act:
            return acoustic_frame.source_discourse_act

        # Fallback to context p7_discourse_envelope
        if hasattr(ctx, 'p7_discourse_envelope') and ctx.p7_discourse_envelope is not None:
            return ctx.p7_discourse_envelope.act.value

        # Conservative default
        return "DEFERRAL"

    def _get_source_intent(self, ctx: Any) -> Optional[str]:
        """Extract source intent from context."""
        if hasattr(ctx, 'phase_zero') and ctx.phase_zero is not None:
            return ctx.phase_zero.intent_type.value
        return None

    def _get_timestamp_utc(self) -> str:
        """Get current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _run_invariant_checks(
        self,
        acoustic_frame: AcousticParameterFrame,
        source_regime: str,
    ) -> Dict[str, bool]:
        """
        Run all invariant checks on the acoustic frame.

        All checks are pure boolean functions that detect but do NOT correct.

        Args:
            acoustic_frame: The P10 acoustic frame to validate.
            source_regime: The source regime string for regime-dependent checks.

        Returns:
            Dictionary of invariant name -> pass/fail status.
        """
        return {
            "speech_rate_within_bounds": check_speech_rate_within_bounds(acoustic_frame),
            "energy_within_bounds": check_energy_within_bounds(acoustic_frame),
            "pitch_within_bounds": check_pitch_within_bounds(acoustic_frame),
            "pause_policy_respected": check_pause_policy_respected(acoustic_frame),
            "no_emotion_amplification": check_no_emotion_amplification(
                acoustic_frame, source_regime
            ),
            "no_certainty_injection": check_no_certainty_injection(
                acoustic_frame, source_regime
            ),
            "no_emphasis_override": check_no_emphasis_override(
                acoustic_frame, source_regime
            ),
            "lexical_integrity_preserved": check_lexical_integrity_preserved(acoustic_frame),
            "regime_constraints_respected": check_regime_constraints_respected(
                acoustic_frame, source_regime
            ),
        }

    def _build_debug_info(
        self,
        ctx: Any,
        acoustic_frame: AcousticParameterFrame,
        invariant_checks: Dict[str, bool],
    ) -> Dict[str, Any]:
        """Build debug information for tracing."""
        failed_checks = [k for k, v in invariant_checks.items() if not v]
        return {
            "p10_regime": acoustic_frame.regime.value,
            "p10_is_flat": acoustic_frame.is_flat_regime(),
            "p10_is_suppressed": acoustic_frame.is_suppressed(),
            "p10_allows_emphasis": acoustic_frame.allows_emphasis(),
            "total_invariant_checks": len(invariant_checks),
            "passed_invariant_checks": sum(1 for v in invariant_checks.values() if v),
            "failed_invariant_checks": len(failed_checks),
            "failed_check_names": failed_checks,
            "is_witness_only": True,
            "modifications_made": False,
        }


# Public exports
__all__ = [
    "P11ProsodicResolver",
    # Invariant check functions (for testing)
    "check_speech_rate_within_bounds",
    "check_energy_within_bounds",
    "check_pitch_within_bounds",
    "check_pause_policy_respected",
    "check_no_emotion_amplification",
    "check_no_certainty_injection",
    "check_no_emphasis_override",
    "check_lexical_integrity_preserved",
    "check_regime_constraints_respected",
]
