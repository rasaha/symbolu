"""
P11 - Prosodic Evidence Capture Schema Definitions

P11 is a WITNESS-ONLY phase. It observes, records, and attests to
acoustic/prosodic parameters chosen by P10 — without modifying them.

P11's responsibility is to:
- Observe P10 output
- Record prosodic/acoustic evidence
- Validate invariants
- Expose violations (if any)
- Never change behavior
- Never influence upstream or downstream decisions

P11 does NOT:
- Generate speech
- Smooth prosody
- "Improve" expressiveness
- Modify P10 output
- Correct violations (only detect them)

Design Principles:
- Witness-Only: P11 cannot mutate P10 output
- Deterministic: No randomness, no ML, no LLM
- Read-Only: Acoustic parameters are copied verbatim
- Conservative: If P10 missing -> P11 returns None
- Audit-Ready: Suitable for compliance, debugging, regression testing
- Downstream-Only: P12+ may read P11; P10 and earlier may not

Authority Model:
- P11 receives AcousticParameterFrame from P10
- P11 copies all acoustic parameters verbatim (no modification)
- P11 validates invariants but does NOT correct them
- P11 produces ProsodicEvidenceFrame (read-only, non-actuating)

CRITICAL ARCHITECTURAL INVARIANT:
    P11 exists to observe, not to optimize.
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


# ============================================================================
# VERSION CONSTANT
# ============================================================================

P11_VERSION = "1.0.0"


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class ProsodicEvidenceFrame:
    """
    P11 output envelope: Prosodic evidence attestation.

    This envelope is read-only and captures a verbatim copy of P10's
    acoustic parameters along with invariant validation results.
    It is purely observational — it does NOT modify prosody or behavior.

    All acoustic parameters are COPIED EXACTLY from P10's AcousticParameterFrame.
    No smoothing, no enhancement, no optimization is performed.

    Invariants:
    - All acoustic parameters must be copied verbatim from P10
    - violations_detected is True if any invariant check is False
    - P11 never corrects violations — only detects them
    - timestamp_utc is for audit purposes only

    Attributes (Acoustic Snapshot - Copied EXACTLY from P10):
        speech_rate: Syllables per second (copied from P10)
        energy_level: Normalized energy (copied from P10)
        pitch_range: (min_hz, max_hz) tuple (copied from P10)
        pause_policy: Pause insertion policy string (copied from P10)
        pause_duration_ms: (min_ms, max_ms) tuple (copied from P10)
        emphasis_policy: Emphasis application policy string (copied from P10)
        max_stressed_tokens: Maximum tokens that can receive stress (copied from P10)
        suppress_emotion: Whether emotion inference is suppressed (copied from P10)
        suppress_certainty: Whether certainty collapse is suppressed (copied from P10)
        suppress_emphasis: Whether emphasis introduction is suppressed (copied from P10)

    Attributes (Provenance Metadata):
        source_regime: The operational regime from P6 (copied for tracing)
        source_discourse_act: The discourse act from P7 (copied for tracing)
        source_intent: The intent type (if available, for tracing)
        source_p10_version: Static P10 version string for provenance
        timestamp_utc: ISO-8601 timestamp for audit purposes

    Attributes (Invariant Attestation):
        invariant_checks: Dictionary of invariant name -> pass/fail status
        violations_detected: True if any invariant check failed

    Attributes (Metadata):
        architectural_phase: Identifier for this phase ("P11")
        debug: Additional debug/trace information
    """

    # === Acoustic Snapshot (Copied EXACTLY from P10) ===
    speech_rate: float
    energy_level: float
    pitch_range: Tuple[int, int]
    pause_policy: str
    pause_duration_ms: Tuple[int, int]
    emphasis_policy: str
    max_stressed_tokens: int
    suppress_emotion: bool
    suppress_certainty: bool
    suppress_emphasis: bool

    # === Provenance Metadata ===
    source_regime: str
    source_discourse_act: str
    source_intent: Optional[str]
    source_p10_version: str
    timestamp_utc: str

    # === Invariant Attestation ===
    invariant_checks: Dict[str, bool]
    violations_detected: bool

    # === Metadata ===
    architectural_phase: str = "P11"
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate ProsodicEvidenceFrame invariants."""
        # Validate speech_rate is numeric
        if not isinstance(self.speech_rate, (int, float)):
            raise ValueError(
                f"ProsodicEvidenceFrame.speech_rate must be numeric, "
                f"got {type(self.speech_rate).__name__}"
            )

        # Validate energy_level is numeric
        if not isinstance(self.energy_level, (int, float)):
            raise ValueError(
                f"ProsodicEvidenceFrame.energy_level must be numeric, "
                f"got {type(self.energy_level).__name__}"
            )

        # Validate pitch_range is a 2-tuple
        if not isinstance(self.pitch_range, tuple) or len(self.pitch_range) != 2:
            raise ValueError(
                f"ProsodicEvidenceFrame.pitch_range must be a 2-tuple, "
                f"got {type(self.pitch_range).__name__}"
            )

        # Validate pause_policy is string
        if not isinstance(self.pause_policy, str) or not self.pause_policy.strip():
            raise ValueError(
                "ProsodicEvidenceFrame.pause_policy must be a non-empty string"
            )

        # Validate pause_duration_ms is a 2-tuple
        if not isinstance(self.pause_duration_ms, tuple) or len(self.pause_duration_ms) != 2:
            raise ValueError(
                f"ProsodicEvidenceFrame.pause_duration_ms must be a 2-tuple, "
                f"got {type(self.pause_duration_ms).__name__}"
            )

        # Validate emphasis_policy is string
        if not isinstance(self.emphasis_policy, str) or not self.emphasis_policy.strip():
            raise ValueError(
                "ProsodicEvidenceFrame.emphasis_policy must be a non-empty string"
            )

        # Validate max_stressed_tokens is int
        if not isinstance(self.max_stressed_tokens, int):
            raise ValueError(
                f"ProsodicEvidenceFrame.max_stressed_tokens must be int, "
                f"got {type(self.max_stressed_tokens).__name__}"
            )

        # Validate boolean suppressions
        for attr_name in ('suppress_emotion', 'suppress_certainty', 'suppress_emphasis'):
            value = getattr(self, attr_name)
            if not isinstance(value, bool):
                raise ValueError(
                    f"ProsodicEvidenceFrame.{attr_name} must be bool, "
                    f"got {type(value).__name__}"
                )

        # Validate source strings
        if not isinstance(self.source_regime, str) or not self.source_regime.strip():
            raise ValueError(
                "ProsodicEvidenceFrame.source_regime must be a non-empty string"
            )
        if not isinstance(self.source_discourse_act, str) or not self.source_discourse_act.strip():
            raise ValueError(
                "ProsodicEvidenceFrame.source_discourse_act must be a non-empty string"
            )

        # source_intent can be None or a string
        if self.source_intent is not None and not isinstance(self.source_intent, str):
            raise ValueError(
                f"ProsodicEvidenceFrame.source_intent must be str or None, "
                f"got {type(self.source_intent).__name__}"
            )

        # Validate source_p10_version is string
        if not isinstance(self.source_p10_version, str) or not self.source_p10_version.strip():
            raise ValueError(
                "ProsodicEvidenceFrame.source_p10_version must be a non-empty string"
            )

        # Validate timestamp_utc is string
        if not isinstance(self.timestamp_utc, str) or not self.timestamp_utc.strip():
            raise ValueError(
                "ProsodicEvidenceFrame.timestamp_utc must be a non-empty string"
            )

        # Validate invariant_checks is dict
        if not isinstance(self.invariant_checks, dict):
            raise ValueError(
                f"ProsodicEvidenceFrame.invariant_checks must be dict, "
                f"got {type(self.invariant_checks).__name__}"
            )
        for key, value in self.invariant_checks.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"ProsodicEvidenceFrame.invariant_checks keys must be str, "
                    f"got {type(key).__name__}"
                )
            if not isinstance(value, bool):
                raise ValueError(
                    f"ProsodicEvidenceFrame.invariant_checks values must be bool, "
                    f"got {type(value).__name__}"
                )

        # Validate violations_detected is bool
        if not isinstance(self.violations_detected, bool):
            raise ValueError(
                f"ProsodicEvidenceFrame.violations_detected must be bool, "
                f"got {type(self.violations_detected).__name__}"
            )

    def has_violations(self) -> bool:
        """Check if any invariant violations were detected."""
        return self.violations_detected

    def get_failed_invariants(self) -> list:
        """Get list of invariant names that failed."""
        return [name for name, passed in self.invariant_checks.items() if not passed]

    def get_passed_invariants(self) -> list:
        """Get list of invariant names that passed."""
        return [name for name, passed in self.invariant_checks.items() if passed]

    def is_fully_suppressed(self) -> bool:
        """Check if all suppressions are active."""
        return self.suppress_emotion and self.suppress_emphasis and self.suppress_certainty

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            # Acoustic snapshot
            "speech_rate": self.speech_rate,
            "energy_level": self.energy_level,
            "pitch_range": list(self.pitch_range),
            "pause_policy": self.pause_policy,
            "pause_duration_ms": list(self.pause_duration_ms),
            "emphasis_policy": self.emphasis_policy,
            "max_stressed_tokens": self.max_stressed_tokens,
            "suppress_emotion": self.suppress_emotion,
            "suppress_certainty": self.suppress_certainty,
            "suppress_emphasis": self.suppress_emphasis,
            # Provenance
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "source_intent": self.source_intent,
            "source_p10_version": self.source_p10_version,
            "timestamp_utc": self.timestamp_utc,
            # Attestation
            "invariant_checks": self.invariant_checks,
            "violations_detected": self.violations_detected,
            "failed_invariants": self.get_failed_invariants(),
            # Metadata
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
            "is_fully_suppressed": self.is_fully_suppressed(),
        }


# Public exports
__all__ = [
    "ProsodicEvidenceFrame",
    "P11_VERSION",
]
